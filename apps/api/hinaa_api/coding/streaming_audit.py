"""Phase 20: Streaming and Latency Truth Audit Engine.

Rigorously measures:
- Time-to-First-Byte (TTFB)
- Time-to-First-Token (TTFT)
- Chunk distribution and intervals
- Multi-chunk streaming verification (assert chunk_count > 1)
- Tokens per second throughput
- Cost computation in Nepali Rupees (NPR)
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel, Field


class StreamingChunkMetric(BaseModel):
    chunk_index: int
    arrival_offset_ms: float
    token_count: int
    content_snippet: str


class StreamingAuditReport(BaseModel):
    model_name: str
    provider: str
    prompt: str
    ttfb_ms: float
    ttft_ms: float
    total_duration_ms: float
    total_tokens: int
    tokens_per_second: float
    chunk_count: int
    chunks: List[StreamingChunkMetric] = Field(default_factory=list)
    is_multi_chunk_stream: bool = True
    estimated_cost_usd: float
    estimated_cost_npr: float  # Exchange rate e.g. 1 USD = 135.50 NPR
    status: str = "VERIFIED_STREAMING"


class StreamingAuditEngine:
    """Audits LLM streaming responses for genuine incremental token generation."""

    USD_TO_NPR_RATE: float = 135.50

    async def audit_stream(
        self,
        stream_generator: AsyncGenerator[str, None],
        model_name: str = "xkiro/qwen-2.5-coder-32b",
        provider: str = "xKiro Gateway",
        prompt: str = "Synthesize an authenticated REST API for doctor appointment bookings",
        cost_per_million_tokens_usd: float = 0.80,
    ) -> StreamingAuditReport:
        start_time = time.perf_counter()
        first_byte_time: Optional[float] = None
        first_token_time: Optional[float] = None

        chunks: List[StreamingChunkMetric] = []
        total_tokens = 0
        chunk_idx = 0

        async for chunk_text in stream_generator:
            now = time.perf_counter()
            offset_ms = (now - start_time) * 1000.0

            if first_byte_time is None:
                first_byte_time = now

            tokens = max(1, len(chunk_text.split()))
            total_tokens += tokens

            if first_token_time is None and chunk_text.strip():
                first_token_time = now

            chunks.append(
                StreamingChunkMetric(
                    chunk_index=chunk_idx,
                    arrival_offset_ms=round(offset_ms, 2),
                    token_count=tokens,
                    content_snippet=chunk_text[:30].replace("\n", " "),
                )
            )
            chunk_idx += 1

        total_end = time.perf_counter()
        total_duration_ms = (total_end - start_time) * 1000.0

        ttfb_ms = round(((first_byte_time or total_end) - start_time) * 1000.0, 2)
        ttft_ms = round(((first_token_time or total_end) - start_time) * 1000.0, 2)

        duration_sec = max(0.001, (total_end - (first_token_time or start_time)))
        tokens_per_sec = round(total_tokens / duration_sec, 2)

        cost_usd = (total_tokens / 1_000_000.0) * cost_per_million_tokens_usd
        cost_npr = round(cost_usd * self.USD_TO_NPR_RATE, 4)

        is_multi = len(chunks) > 1

        return StreamingAuditReport(
            model_name=model_name,
            provider=provider,
            prompt=prompt,
            ttfb_ms=ttfb_ms,
            ttft_ms=ttft_ms,
            total_duration_ms=round(total_duration_ms, 2),
            total_tokens=total_tokens,
            tokens_per_second=tokens_per_sec,
            chunk_count=len(chunks),
            chunks=chunks,
            is_multi_chunk_stream=is_multi,
            estimated_cost_usd=round(cost_usd, 6),
            estimated_cost_npr=cost_npr,
            status="VERIFIED_STREAMING" if is_multi else "BUFFERED_SINGLE_CHUNK_WARNING",
        )

    async def run_simulated_audit(
        self,
        model_name: str = "xkiro/qwen-2.5-coder-32b",
        simulated_tokens: int = 120,
        chunk_delay_ms: float = 18.0,
    ) -> StreamingAuditReport:
        """Runs a synthetic streaming cycle with realistic inter-token latency for CI/testing."""

        async def _generator():
            words = (
                "SELECT id, doctor_name, slot_time, patient_id FROM appointments "
                "WHERE slot_time = :target_slot AND status = 'CONFIRMED' FOR UPDATE; "
                "-- Atomic collision check completed. No double-booking permitted.\n"
            ).split()
            for word in words:
                await asyncio.sleep(chunk_delay_ms / 1000.0)
                yield word + " "

        return await self.audit_stream(
            stream_generator=_generator(),
            model_name=model_name,
            provider="xKiro Multi-Model Gateway",
            prompt="Write SQL query to prevent doctor slot collision in SQLite",
        )


_STREAMING_AUDIT_ENGINE: Optional[StreamingAuditEngine] = None


def get_streaming_audit_engine() -> StreamingAuditEngine:
    global _STREAMING_AUDIT_ENGINE
    if _STREAMING_AUDIT_ENGINE is None:
        _STREAMING_AUDIT_ENGINE = StreamingAuditEngine()
    return _STREAMING_AUDIT_ENGINE
