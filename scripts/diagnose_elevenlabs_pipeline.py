"""Diagnose the ElevenLabs voice pipeline with the real configured credentials.

Makes three minimal calls (negligible/no cost):
  1. GET /v1/user            -> is the API key valid?
  2. GET /v1/voices/{id}     -> does the configured Hinaa voice exist?
  3. POST /v1/speech-to-text -> does the configured STT model id work? (1s silence)

Never prints the API key. Prints status codes and short sanitized bodies.
"""
from __future__ import annotations

import io
import sys
import wave
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from hinaa_api.config import Settings  # noqa: E402


def main() -> int:
    env_local = ROOT / "apps" / "api" / ".env.local"
    settings = Settings(_env_file=str(env_local) if env_local.exists() else None)
    if not settings.elevenlabs_configured:
        print("[FAIL] ElevenLabs is not configured (missing key or voice id).")
        return 1
    key = settings.elevenlabs_api_key.get_secret_value()  # type: ignore[union-attr]
    base = settings.elevenlabs_base_url.rstrip("/")
    headers = {"xi-api-key": key}
    print(f"[INFO] base_url={base}")
    print(f"[INFO] hinaa_voice_id={settings.elevenlabs_hinaa_voice_id}")
    print(f"[INFO] tts_model_id={settings.elevenlabs_model_id}")
    print(f"[INFO] stt_model_id={settings.elevenlabs_stt_model_id}")
    print(f"[INFO] output_format={settings.elevenlabs_output_format}")

    with httpx.Client(timeout=20.0) as client:
        # 1. Key check
        r = client.get(f"{base}/v1/user", headers=headers)
        print(f"[1] key check GET /v1/user -> {r.status_code}")
        if r.status_code != 200:
            print(f"    body: {r.text[:300]}")
            print("[FAIL] API key is not accepted. Fix ELEVENLABS_API_KEY first.")
            return 1

        # 2. Voice check
        vid = settings.elevenlabs_hinaa_voice_id
        r = client.get(f"{base}/v1/voices/{vid}", headers=headers)
        print(f"[2] voice check GET /v1/voices/{vid} -> {r.status_code}")
        if r.status_code == 200:
            print(f"    voice name: {r.json().get('name')}")
        else:
            print(f"    body: {r.text[:300]}")
            print("[FAIL] Configured Hinaa voice id does not exist on this account.")

        # 3. STT check with 1 second of silence
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(16000)
            f.writeframes(b"\x00\x00" * 16000)
        r = client.post(
            f"{base}/v1/speech-to-text",
            headers=headers,
            files={"file": ("audio.wav", wav_io.getvalue(), "audio/wav")},
            data={"model_id": settings.elevenlabs_stt_model_id or "scribe_v2"},
        )
        print(f"[3] stt check POST /v1/speech-to-text -> {r.status_code}")
        if r.status_code == 200:
            print(f"    transcript for silence: {r.json().get('text')!r}")
            print("[OK] STT endpoint + model id accepted.")
        else:
            print(f"    body: {r.text[:400]}")
            print("[FAIL] STT call rejected — this is why Hinaa cannot hear you.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
