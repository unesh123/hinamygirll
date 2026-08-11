import httpx
import logging
from typing import Any

from .base import TTSProvider, STTProvider, ProviderResult

logger = logging.getLogger("hinaa.deepgram")

class DeepgramTTSProvider(TTSProvider):
    id: str = "deepgram"

    def __init__(self, api_key: str, base_url: str):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def synthesize(self, text: str, voice: str) -> ProviderResult[bytes]:
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
                    latency_ms=int((time.time() - start) * 1000)
                )
        except Exception as e:
            logger.error(f"Deepgram TTS exception: {e}")
            raise e


class DeepgramSTTProvider(STTProvider):
    id: str = "deepgram"

    def __init__(self, api_key: str, base_url: str):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def transcribe(self, audio: bytes, language: str = "en") -> ProviderResult[str]:
        # Simple REST STT endpoint for one-shot transcription
        url = f"{self._base_url}/v1/listen?model=flux-general-en&smart_format=true"
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "audio/webm" # We'll assume webm or standard format from browser
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, content=audio, timeout=20.0)
                if response.status_code != 200:
                    logger.error(f"Deepgram STT failed: {response.status_code} {response.text}")
                    raise Exception(f"Deepgram STT failed: {response.status_code}")
                
                data = response.json()
                transcript = data.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "")
                
                # Assume start time was not recorded, or we could add it
                # For now, just return ProviderResult with value
                return ProviderResult(
                    value=transcript,
                    provider=self.id,
                    latency_ms=0 # Ideally we'd time it, but 0 is okay for fallback fix
                )
        except Exception as e:
            logger.error(f"Deepgram STT exception: {e}")
            raise e
