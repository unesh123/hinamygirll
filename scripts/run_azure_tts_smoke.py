#!/usr/bin/env python3
"""Opt-in single-phrase Azure TTS smoke test (Hemkala).

DISABLED BY DEFAULT. Can incur Azure Speech charges.

Does NOT:
  - call Gemini
  - call Azure STT
  - capture microphone audio
  - run from ordinary pytest
  - allow more than one synthesis without re-setting the gate

Required explicit confirmation in the SAME shell:
  set HINAA_ALLOW_PAID_VOICE_TEST=1
  set HINAA_PAID_VOICE_TEST_CONFIRM=I_UNDERSTAND_THIS_MAY_COST_MONEY

Then:
  apps\\api\\.venv\\Scripts\\python.exe scripts\\run_azure_tts_smoke.py

Writes WAV only under ignored .runtime/voice-smoke/ after successful nonzero audio.
Deletes it unless --keep-audio is passed. Never prints secret keys.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import wave
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

CONFIRM = "I_UNDERSTAND_THIS_MAY_COST_MONEY"
DEFAULT_PHRASE = "Namaste, ma Hinaa hus. Yo short voice smoke test ho."
OUT_DIR = ROOT / ".runtime" / "voice-smoke"
OUT_FILE = OUT_DIR / "hemkala-smoke.wav"


def _gate_or_exit() -> None:
    if os.environ.get("HINAA_ALLOW_PAID_VOICE_TEST") != "1":
        print("Refusing to run: set HINAA_ALLOW_PAID_VOICE_TEST=1")
        raise SystemExit(2)
    if os.environ.get("HINAA_PAID_VOICE_TEST_CONFIRM") != CONFIRM:
        print(f"Refusing to run: set HINAA_PAID_VOICE_TEST_CONFIRM={CONFIRM}")
        raise SystemExit(2)


def _wav_duration_seconds(data: bytes) -> float | None:
    try:
        with wave.open(__import__("io").BytesIO(data), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
            if rate <= 0:
                return None
            return round(frames / float(rate), 3)
    except Exception:
        return None


def _clear_temp_wav() -> None:
    OUT_FILE.unlink(missing_ok=True)


async def _run(*, keep_audio: bool) -> int:
    from hinaa_api.config import Settings
    from hinaa_api.errors import HinaaError
    from hinaa_api.providers.azure_errors import AZURE_ERROR_CODES
    from hinaa_api.services import ConversationService

    # Same Settings class / env_file path as API (`apps/api/.env.local`).
    settings = Settings()  # type: ignore[call-arg]
    if not settings.azure_speech_key or not settings.azure_speech_key.get_secret_value():
        print(
            {
                "azureAuthentication": "FAIL",
                "error": {"code": "AZURE_KEY_MISSING", "message": "Azure Speech key missing"},
            }
        )
        return 3
    if not settings.azure_speech_region:
        print(
            {
                "azureAuthentication": "FAIL",
                "error": {
                    "code": "AZURE_REGION_MISSING",
                    "message": "Azure Speech region missing",
                },
            }
        )
        return 3

    voice = settings.azure_speech_female_voice
    print("Azure TTS smoke (single phrase, no STT, no Gemini)")
    print(f"selectedVoice={voice}")
    print(f"configuredRegion={settings.azure_speech_region}")
    print(f"regionConfigured=yes")
    print(f"outputPath={OUT_FILE}")
    _clear_temp_wav()

    service = ConversationService(settings)
    request_started = perf_counter()
    tts_request_start_ms = 0
    first_audio_ms: int | None = None
    try:
        tts_request_start_ms = int((perf_counter() - request_started) * 1000)
        result = await service.synthesize_text(
            DEFAULT_PHRASE,
            "hinaa",
            "real",
            "natural",
        )
        first_audio_ms = int((perf_counter() - request_started) * 1000)
        total_ms = first_audio_ms
        audio = result.value
        if not audio:
            _clear_temp_wav()
            print(
                {
                    "azureAuthentication": "UNKNOWN",
                    "selectedVoice": voice,
                    "configuredRegion": settings.azure_speech_region,
                    "outputFormat": None,
                    "ttsExpected": False,
                    "error": {
                        "code": "AZURE_OUTPUT_WRITE_FAILED",
                        "message": "Empty audio returned; no WAV written",
                    },
                }
            )
            return 4
        duration = _wav_duration_seconds(audio)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        OUT_FILE.write_bytes(audio)
        print(
            {
                "azureAuthentication": "PASS",
                "selectedVoice": voice,
                "requestedVoice": voice,
                "configuredRegion": settings.azure_speech_region,
                "provider": result.provider,
                "ttsRequestStartMs": tts_request_start_ms,
                "firstAudioAvailabilityMs": first_audio_ms,
                "totalSynthesisMs": total_ms,
                "providerLatencyMs": result.latency_ms,
                "audioBytes": len(audio),
                "audioDurationSeconds": duration,
                "outputFormat": "audio/wav Riff16Khz16BitMonoPcm (configured)",
                "ttsExpected": True,
                "tempPath": str(OUT_FILE),
                "keptAudio": keep_audio,
                "sttExercised": False,
                "geminiExercised": False,
                "error": None,
            }
        )
        if not keep_audio:
            _clear_temp_wav()
            print("Temporary audio deleted after smoke measurement.")
        else:
            print("Temporary audio kept (gitignored via .runtime/ and *.wav). Do not commit.")
        return 0
    except HinaaError as error:
        _clear_temp_wav()
        authish = error.code in {
            "AZURE_AUTH_FAILED",
            "AZURE_KEY_REGION_MISMATCH",
            "AZURE_KEY_MISSING",
            "AZURE_REGION_MISSING",
            "PROVIDER_KEY_INVALID",
        }
        print(
            {
                "azureAuthentication": "FAIL" if authish else "UNKNOWN",
                "selectedVoice": voice,
                "configuredRegion": settings.azure_speech_region,
                "ttsRequestStartMs": tts_request_start_ms,
                "firstAudioAvailabilityMs": first_audio_ms,
                "totalSynthesisMs": int((perf_counter() - request_started) * 1000),
                "outputFormat": None,
                "ttsExpected": False,
                "sttExercised": False,
                "geminiExercised": False,
                "tempWavPresent": OUT_FILE.exists(),
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "azureCategoryKnown": error.code in AZURE_ERROR_CODES,
                },
            }
        )
        return 4
    except Exception:
        _clear_temp_wav()
        print(
            {
                "azureAuthentication": "UNKNOWN",
                "selectedVoice": voice,
                "configuredRegion": settings.azure_speech_region,
                "ttsExpected": False,
                "error": {"type": "Exception", "message": "sanitized failure"},
                "sttExercised": False,
                "geminiExercised": False,
            }
        )
        return 4


def main() -> None:
    parser = argparse.ArgumentParser(description="Capped Azure Hemkala TTS smoke test")
    parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="Keep ignored temporary WAV for manual listen; default deletes after report",
    )
    args = parser.parse_args()
    _gate_or_exit()
    os.environ.pop("HINAA_ALLOW_PAID_VOICE_TEST", None)
    os.environ.pop("HINAA_PAID_VOICE_TEST_CONFIRM", None)
    raise SystemExit(asyncio.run(_run(keep_audio=args.keep_audio)))


if __name__ == "__main__":
    main()
