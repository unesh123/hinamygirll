"""
test_hinaa_elevenlabs_live_turn.py

Owner-gated full integrated live turn test script (STT -> LLM -> ElevenLabs TTS).
DO NOT RUN WITHOUT EXPLICIT OWNER GATES.

Required Environment Gates:
  HINAA_ALLOW_ELEVENLABS_LIVE_TURN_TEST="1"
  HINAA_ELEVENLABS_LIVE_TURN_TEST_CONFIRM="I_UNDERSTAND_THIS_MAY_COST_MONEY"

Usage:
  python scripts/test_hinaa_elevenlabs_live_turn.py
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from hinaa_api.config import Settings

def main():
    allow = os.environ.get("HINAA_ALLOW_ELEVENLABS_LIVE_TURN_TEST", "").strip()
    confirm = os.environ.get("HINAA_ELEVENLABS_LIVE_TURN_TEST_CONFIRM", "").strip()

    if allow != "1" or confirm != "I_UNDERSTAND_THIS_MAY_COST_MONEY":
        print("[GATE BLOCKED] Live Turn test halted.")
        print("To run this owner-gated paid test, set in your environment:")
        print("  $env:HINAA_ALLOW_ELEVENLABS_LIVE_TURN_TEST=\"1\"")
        print("  $env:HINAA_ELEVENLABS_LIVE_TURN_TEST_CONFIRM=\"I_UNDERSTAND_THIS_MAY_COST_MONEY\"")
        sys.exit(1)

    print("[STAGE A] ElevenLabs Live Turn Environment Gate Verified.")

    env_local = ROOT / "apps" / "api" / ".env.local"
    settings = Settings(_env_file=str(env_local) if env_local.exists() else None)

    print(f"[STAGE A] Voice ID: {settings.elevenlabs_voice_id}")
    print(f"[STAGE A] Model ID: {settings.elevenlabs_model_id}")
    print("[STAGE B] Ready for single integrated turn (microphone -> brain -> ElevenLabs TTS).")

    # Clear environment gate
    os.environ.pop("HINAA_ALLOW_ELEVENLABS_LIVE_TURN_TEST", None)
    os.environ.pop("HINAA_ELEVENLABS_LIVE_TURN_TEST_CONFIRM", None)

if __name__ == "__main__":
    main()
