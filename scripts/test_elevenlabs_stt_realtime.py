"""
test_elevenlabs_stt_realtime.py

Owner-gated realtime STT smoke test script for ElevenLabs Scribe v2.
DO NOT RUN WITHOUT EXPLICIT OWNER GATES.

Required Environment Gates:
  HINAA_ALLOW_ELEVENLABS_STT_TEST="1"
  HINAA_ELEVENLABS_STT_TEST_CONFIRM="I_UNDERSTAND_THIS_MAY_COST_MONEY"

Usage:
  python scripts/test_elevenlabs_stt_realtime.py
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from hinaa_api.config import Settings
from hinaa_api.providers.elevenlabs import ElevenLabsConfig, ElevenLabsSTTProvider

def main():
    allow = os.environ.get("HINAA_ALLOW_ELEVENLABS_STT_TEST", "").strip()
    confirm = os.environ.get("HINAA_ELEVENLABS_STT_TEST_CONFIRM", "").strip()

    if allow != "1" or confirm != "I_UNDERSTAND_THIS_MAY_COST_MONEY":
        print("[GATE BLOCKED] STT Realtime test halted.")
        print("To run this owner-gated paid test, set in your environment:")
        print("  $env:HINAA_ALLOW_ELEVENLABS_STT_TEST=\"1\"")
        print("  $env:HINAA_ELEVENLABS_STT_TEST_CONFIRM=\"I_UNDERSTAND_THIS_MAY_COST_MONEY\"")
        sys.exit(1)

    print("[STAGE A] ElevenLabs STT Environment Gate Verified.")

    env_local = ROOT / "apps" / "api" / ".env.local"
    settings = Settings(_env_file=str(env_local) if env_local.exists() else None)

    api_key = (getattr(settings, "ELEVENLABS_API_KEY", "") or "").strip()
    if not api_key:
        print("[STAGE A ERROR] ELEVENLABS_API_KEY is missing in apps/api/.env.local")
        sys.exit(1)

    config = ElevenLabsConfig(api_key=api_key, model_id=settings.elevenlabs_stt_model_id)
    provider = ElevenLabsSTTProvider(config)

    print(f"[STAGE A] STT Model: {settings.elevenlabs_stt_model_id}")
    print("[STAGE B] Ready for single owner microphone test (STT only, no LLM, no TTS).")

    # Clear environment gate
    os.environ.pop("HINAA_ALLOW_ELEVENLABS_STT_TEST", None)
    os.environ.pop("HINAA_ELEVENLABS_STT_TEST_CONFIRM", None)

if __name__ == "__main__":
    main()
