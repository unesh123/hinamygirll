"""Integration bridge connecting HINAA Neural Lab custom models to the main model router."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator, Optional
import httpx

from ..telemetry.metrics import record_turn_metrics
from .adapters.manager import get_adapter_manager

logger = logging.getLogger("hinaa.neural_lab.router")


class LocalNeuralLabProvider:
    """OpenAI-compatible local inference bridge serving Hina's custom fine-tuned weights."""

    id = "hinaa-neural-lab"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434/v1",
        default_model: str = "hinaa-core:latest",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    async def is_available(self) -> bool:
        """Check if local inference engine (Ollama) is responding."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.base_url}/models")
                return res.status_code == 200
        except Exception:
            return False

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        trace_id: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream chat completions from local custom model with telemetry instrumentation."""
        active_model = model or self.default_model
        payload = {
            "model": active_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        url = f"{self.base_url}/chat/completions"
        t0 = time.perf_counter()
        first_token_time: Optional[float] = None
        total_chars = 0
        success = False

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", url, json=payload) as resp:
                    if resp.status_code != 200:
                        err_text = await resp.aread()
                        logger.error("Local Neural Lab provider HTTP %d: %s", resp.status_code, err_text)
                        yield {"type": "error", "message": f"Local model error HTTP {resp.status_code}"}
                        return

                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            raw_data = line[6:].strip()
                            if raw_data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(raw_data)
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {}).get("content", "")
                                    if delta:
                                        if first_token_time is None:
                                            first_token_time = time.perf_counter()
                                        total_chars += len(delta)
                                        yield {"type": "text.delta", "delta": delta}
                            except Exception:
                                pass
            success = True
        except Exception as exc:
            logger.error("Local model stream exception: %s", exc)
            yield {"type": "error", "message": str(exc)}
        finally:
            total_duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            ttft_ms = round((first_token_time - t0) * 1000, 2) if first_token_time else total_duration_ms
            if trace_id:
                record_turn_metrics(
                    trace_id=trace_id,
                    provider_id="local-neural-lab",
                    model=active_model,
                    ttft_ms=ttft_ms,
                    model_latency_ms=ttft_ms,
                    total_turn_ms=total_duration_ms,
                    chars_generated=total_chars,
                    success=success,
                )
