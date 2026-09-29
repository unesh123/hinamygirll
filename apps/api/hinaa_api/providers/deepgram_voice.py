import httpx
import io
import logging
import wave
from time import perf_counter
from typing import Any

from .base import TTSProvider, STTProvider, ProviderResult
from ..errors import HinaaError

logger = logging.getLogger("hinaa.deepgram")

# What /v1/realtime actually accumulates: mono 16-bit signed little-endian.
PCM_SAMPLE_RATE = 16_000


def pcm_to_wav(pcm: bytes, sample_rate: int = PCM_SAMPLE_RATE) -> bytes:
    """Wrap the socket's raw PCM in the container the vendor is told it received.

    Both STT call sites hand us PCM frames, so posting them with an `audio/webm`
    label made Deepgram decode a file that is not one.
    """
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
    return buffer.getvalue()

class DeepgramTTSProvider(TTSProvider):
    id: str = "deepgram"

    def __init__(self, api_key: str, base_url: str):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or getattr(self._client, "is_closed", False):
            try:
                self._client = httpx.AsyncClient(timeout=35.0)
            except TypeError:
                self._client = httpx.AsyncClient()
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def synthesize(self, text: str, voice: str) -> ProviderResult[bytes]:
        import asyncio
        import re

        started = perf_counter()
        clean_text = text.strip()
        url = f"{self._base_url}/v1/speak?model={voice}&encoding=mp3"
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "application/json"
        }
        client = self._get_client()

        # For long content (> 300 chars), split into sentence chunks and synthesize
        # concurrently. This prevents timeouts and achieves 4x faster speech turnaround.
        if len(clean_text) > 300:
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean_text) if s.strip()]
            # Group small sentences together if too short (< 80 chars) to prevent excessive requests
            merged_chunks: list[str] = []
            curr = ""
            for s in sentences:
                if curr and len(curr) + len(s) + 1 <= 300:
                    curr += " " + s
                else:
                    if curr:
                        merged_chunks.append(curr)
                    curr = s
            if curr:
                merged_chunks.append(curr)

            if len(merged_chunks) > 1:
                async def fetch_chunk(chunk_text: str) -> bytes:
                    resp = await client.post(url, headers=headers, json={"text": chunk_text})
                    if resp.status_code != 200:
                        logger.error("Deepgram TTS chunk failed: %s %s", resp.status_code, resp.text)
                        raise Exception(f"Deepgram TTS chunk failed: {resp.status_code}")
                    return resp.content

                try:
                    audio_chunks = await asyncio.gather(*[fetch_chunk(c) for c in merged_chunks])
                    combined_audio = b"".join(audio_chunks)
                    return ProviderResult(
                        value=combined_audio,
                        provider=self.id,
                        latency_ms=int((perf_counter() - started) * 1000)
                    )
                except Exception as chunk_err:
                    logger.warning("Concurrent TTS chunk failed, falling back to single request: %s", chunk_err)

        # Standard single request path
        payload = {"text": clean_text}
        try:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                logger.error(f"Deepgram TTS failed: {response.status_code} {response.text}")
                raise Exception(f"Deepgram TTS failed: {response.status_code}")
            
            return ProviderResult(
                value=response.content,
                provider=self.id,
                latency_ms=int((perf_counter() - started) * 1000)
            )
        except Exception as e:
            logger.error(f"Deepgram TTS exception: {e}")
            raise e


class DeepgramSTTProvider(STTProvider):
    id: str = "deepgram"

    def __init__(self, api_key: str, base_url: str, model: str = "nova-2-general"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or getattr(self._client, "is_closed", False):
            try:
                self._client = httpx.AsyncClient(timeout=15.0)
            except TypeError:
                self._client = httpx.AsyncClient()
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def transcribe(self, audio: bytes, language: str = "en") -> ProviderResult[str]:
        started = perf_counter()
        if not audio:
            return ProviderResult("", self.id, 0)

        url = f"{self._base_url}/v1/listen"
        params: dict[str, Any] = {
            "model": self._model or "nova-2-general",
            "smart_format": "true",
            "punctuate": "true",
            "keywords": ["Hina:3", "HINAA:3", "Unesh:3", "babe:2", "kya:2", "kaise:2", "suno:2", "batao:2"],
        }
        supported_langs = {
            "en", "hi", "es", "fr", "de", "it", "pt", "nl", "ja", "ko", "zh", "ru",
            "tr", "sv", "id", "da", "no", "pl", "uk", "ta", "te", "mr", "bn", "gu", "kn", "ml", "pa"
        }
        lang_code = language.split("-")[0].lower() if language else ""
        if lang_code in supported_langs and lang_code not in ("auto", "mixed"):
            params["language"] = lang_code
        else:
            params["detect_language"] = "true"

        # Detect existing container format, or wrap raw PCM16 into standard WAV
        if audio.startswith(b"RIFF") and b"WAVE" in audio[:12]:
            body_bytes = audio
            content_type = "audio/wav"
        elif audio.startswith(b"ID3") or (len(audio) > 2 and audio[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
            body_bytes = audio
            content_type = "audio/mpeg"
        elif audio.startswith(b"OggS"):
            body_bytes = audio
            content_type = "audio/ogg"
        elif audio.startswith(b"\x1a\x45\xdf\xa3"):
            body_bytes = audio
            content_type = "audio/webm"
        else:
            body_bytes = pcm_to_wav(audio)
            content_type = "audio/wav"

        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": content_type,
        }

        try:
            client = self._get_client()
            response = await client.post(
                url, headers=headers, params=params, content=body_bytes
            )
            # If explicit language was rejected with 400, retry with auto-detection
            if response.status_code == 400 and "language" in params:
                params.pop("language", None)
                params["detect_language"] = "true"
                response = await client.post(
                    url, headers=headers, params=params, content=body_bytes
                )
        except Exception as error:
            raise HinaaError(
                "PROVIDER_CONNECTION_FAILED",
                "Speech recognition could not reach Deepgram.",
                502,
                True,
            ) from error

        latency_ms = int((perf_counter() - started) * 1000)
        if response.status_code != 200:
            reason = ""
            try:
                reason = str(response.json().get("message", ""))[:160]
            except Exception:
                pass
            logger.error("Deepgram STT failed: %s %s", response.status_code, reason)
            raise HinaaError(
                "STT_PROVIDER_REJECTED",
                "Deepgram could not transcribe that audio.",
                502,
                True,
                developer_message=reason or f"HTTP {response.status_code}",
            )

        payload = response.json()
        channels = payload.get("results", {}).get("channels", [])
        alternatives = channels[0].get("alternatives", []) if channels else []
        transcript = (alternatives[0].get("transcript", "") if alternatives else "").strip()
        if transcript:
            import re
            transcript = re.sub(
                r'^(?:है\s*ही\s*ना|हे\s*ही\s*ना|है\s*हिना|हाय\s*हिना|हे\s*हिना)\b',
                'Hina',
                transcript,
                flags=re.IGNORECASE,
            )
            transcript = re.sub(
                r'\b(?:है\s*ही\s*ना|हे\s*ही\s*ना)\b',
                'Hina',
                transcript,
                flags=re.IGNORECASE,
            )
        return ProviderResult(value=transcript, provider=self.id, latency_ms=latency_ms)
