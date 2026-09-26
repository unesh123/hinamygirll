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

    async def synthesize(self, text: str, voice: str) -> ProviderResult[bytes]:
        started = perf_counter()
        url = f"{self._base_url}/v1/speak?model={voice}&encoding=mp3"
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "application/json"
        }
        payload = {"text": text}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=20.0)
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

    async def transcribe(self, audio: bytes, language: str = "en") -> ProviderResult[str]:
        started = perf_counter()
        if not audio:
            return ProviderResult("", self.id, 0)

        url = f"{self._base_url}/v1/listen"
        params = {"model": self._model, "smart_format": "true", "punctuate": "true"}
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "audio/wav",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, headers=headers, params=params, content=pcm_to_wav(audio), timeout=20.0
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
        return ProviderResult(value=transcript, provider=self.id, latency_ms=latency_ms)
