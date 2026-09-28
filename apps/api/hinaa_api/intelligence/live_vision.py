"""
Live Eyes: Real-Time Multimodal Vision Service for HINAA.

Allows Hina to continuously observe the user's screen or camera, providing
real-time commentary, debugging assistance, UI analysis, and visual context
for subsequent chat turns.
"""

from __future__ import annotations

import base64
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# In-memory cache of recent screen frames per conversation:
# conversation_id -> (bytes, mime_type, timestamp)
_FRAME_CACHE: Dict[str, Tuple[bytes, str, float]] = {}
_CACHE_TTL_SECONDS = 300.0  # 5 minutes


def _clean_base64(raw: str) -> Tuple[bytes, str]:
    """Extract raw image bytes and detected mime type from base64 string."""
    mime_type = "image/jpeg"
    clean_str = raw.strip()
    if clean_str.startswith("data:"):
        prefix, sep, payload = clean_str.partition(",")
        if ";" in prefix:
            mime_part = prefix.split(";")[0].replace("data:", "").strip()
            if mime_part:
                mime_type = mime_part
        clean_str = payload
    data = base64.b64decode(clean_str)
    return data, mime_type


class LiveVisionService:
    """Provides instant screen and camera vision intelligence."""

    def __init__(self) -> None:
        try:
            from ..config import get_settings
            settings = get_settings()
            self._gemini_key = (
                settings.gemini_api_key.get_secret_value()
                if settings.gemini_api_key
                else os.getenv("GEMINI_API_KEY", "")
            ).strip()
            self._codecraft_key = (
                settings.codecraft_api_key.get_secret_value()
                if settings.codecraft_api_key
                else (os.getenv("CODE_CRAFT_API_KEY") or os.getenv("CODE_CRAFT_API_KEY1") or "")
            ).strip()
        except Exception:
            self._gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
            self._codecraft_key = (
                os.getenv("CODE_CRAFT_API_KEY")
                or os.getenv("CODE_CRAFT_API_KEY1")
                or ""
            ).strip()

    def store_active_frame(
        self,
        conversation_id: str,
        frame_bytes: bytes,
        mime_type: str = "image/jpeg",
    ) -> None:
        """Store the latest visual frame for contextual turn-taking."""
        _FRAME_CACHE[conversation_id] = (frame_bytes, mime_type, time.time())

    def get_active_frame(
        self, conversation_id: str
    ) -> Optional[Tuple[bytes, str]]:
        """Retrieve recent active frame if still within TTL."""
        entry = _FRAME_CACHE.get(conversation_id)
        if not entry:
            return None
        data, mime, ts = entry
        if time.time() - ts > _CACHE_TTL_SECONDS:
            _FRAME_CACHE.pop(conversation_id, None)
            return None
        return data, mime

    async def observe_frame(
        self,
        frame_base64: str,
        query: Optional[str] = None,
        conversation_id: Optional[str] = None,
        companion_id: str = "hinaa",
    ) -> Dict[str, Any]:
        """Analyze a live screen or webcam frame with state-of-the-art vision."""
        try:
            image_bytes, mime_type = _clean_base64(frame_base64)
        except Exception as err:
            logger.warning("Failed to decode vision frame: %s", err)
            return {
                "ok": False,
                "error": "INVALID_IMAGE_DATA",
                "message": "Could not decode image frame.",
            }

        cid = conversation_id or "default"
        self.store_active_frame(cid, image_bytes, mime_type)

        user_query = query.strip() if query else "What am I looking at right now? Give me a concise, sharp, high-value breakdown."

        prompt_text = (
            f"You are Hinaa, Unesh's brilliant, loving, and ultra-sharp AI companion and coding co-pilot.\n"
            f"You are looking directly at Unesh's live screen or camera view right now.\n"
            f"Unesh asks: \"{user_query}\"\n\n"
            f"Instructions:\n"
            f"1. Directly address what is on screen with high precision and technical accuracy.\n"
            f"2. If code/terminal is visible: identify languages, pinpoint bugs or optimizations, reference exact lines.\n"
            f"3. If UI/design is visible: give crisp feedback on typography, alignment, UX flow, and colors.\n"
            f"4. If reading an article or document: summarize the key takeaways immediately.\n"
            f"5. Maintain Hina's warm, supportive, confident persona — speak naturally as if sitting right next to him.\n"
            f"Keep your response concise, structured, and immediately actionable."
        )

        # 1. Primary: Google Gemini 3.8 Flash (native multimodal vision, 1M+ tokens)
        if self._gemini_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self._gemini_key)
                part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

                # Use asyncio run in executor for synchronous client call
                import asyncio
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=[part, prompt_text],
                        config=types.GenerateContentConfig(
                            temperature=0.3,
                            max_output_tokens=1000,
                        ),
                    ),
                )
                text = response.text.strip() if response.text else "I see your screen clearly, Unesh! Everything looks ready."
                return {
                    "ok": True,
                    "provider": "gemini-3.8-flash",
                    "observation": text,
                    "query": user_query,
                    "timestamp": time.time(),
                }
            except Exception as err:
                logger.warning("Gemini live vision observation failed, falling back: %s", err)

        # 2. Fallback: CodeCraft Claude / GPT Multimodal endpoint
        if self._codecraft_key:
            try:
                import httpx
                base_b64 = base64.b64encode(image_bytes).decode("ascii")
                data_uri = f"data:{mime_type};base64,{base_b64}"
                payload = {
                    "model": "claude-fable-5",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt_text},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": data_uri},
                                },
                            ],
                        }
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.3,
                }
                base_url = os.getenv("CODE_CRAFT_BASE_URL", "https://codecraftapi.com/v1").rstrip("/")
                endpoint = f"{base_url}/chat/completions"
                async with httpx.AsyncClient(timeout=15.0) as http_client:
                    resp = await http_client.post(
                        endpoint,
                        headers={
                            "Authorization": f"Bearer {self._codecraft_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        text = data["choices"][0]["message"]["content"].strip()
                        return {
                            "ok": True,
                            "provider": "codecraft/claude-fable-5",
                            "observation": text,
                            "query": user_query,
                            "timestamp": time.time(),
                        }
            except Exception as err:
                logger.warning("Codecraft vision fallback failed: %s", err)

        return {
            "ok": False,
            "error": "VISION_TEMPORARILY_UNAVAILABLE",
            "message": "Both primary and fallback vision models are momentarily unavailable. Please retry in a few seconds.",
        }


live_vision_service = LiveVisionService()
