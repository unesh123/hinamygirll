"""
test_elevenlabs_tts.py

Strictly capped, owner-gated offline runtime smoke test script for ElevenLabs TTS.
DO NOT RUN THIS SCRIPT WITHOUT EXPLICIT OWNER INTENT AND MANDATORY GATES.

Required Environment Gates:
  HINAA_ALLOW_ELEVENLABS_TEST="1"
  HINAA_ELEVENLABS_TEST_CONFIRM="I_UNDERSTAND_THIS_MAY_COST_MONEY"

Usage:
  python scripts/test_elevenlabs_tts.py --voice-id <VOICE_ID> --model-id eleven_multilingual_v2 [--keep-audio]
"""
import argparse
import os
import sys
import time
from pathlib import Path

# Add apps/api to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from hinaa_api.config import Settings
from hinaa_api.providers.elevenlabs import (
    ElevenLabsConfig,
    ElevenLabsHTTPStreamingProvider,
    ElevenLabsError,
)

NON_PRIVATE_TEST_PHRASE = "Namaste. HINAA system check."

def main():
    parser = argparse.ArgumentParser(description="Owner-gated ElevenLabs TTS Runtime Test")
    parser.add_argument("--voice-id", required=True, help="ElevenLabs Voice ID to test")
    parser.add_argument("--model-id", default="eleven_multilingual_v2", help="ElevenLabs Model ID")
    parser.add_argument("--keep-audio", action="store_true", help="Keep temporary audio file in .runtime directory")
    args = parser.parse_args()

    # 1. Gate check
    allow = os.environ.get("HINAA_ALLOW_ELEVENLABS_TEST", "").strip()
    confirm = os.environ.get("HINAA_ELEVENLABS_TEST_CONFIRM", "").strip()

    if allow != "1" or confirm != "I_UNDERSTAND_THIS_MAY_COST_MONEY":
        print("[GATE BLOCKED] Test halted.")
        print("To run this owner-gated paid test, set in your environment:")
        print("  $env:HINAA_ALLOW_ELEVENLABS_TEST=\"1\"")
        print("  $env:HINAA_ELEVENLABS_TEST_CONFIRM=\"I_UNDERSTAND_THIS_MAY_COST_MONEY\"")
        sys.exit(1)

    print("[STAGE A] Environment Gate Verified.")

    # Load env from apps/api/.env.local
    env_local = ROOT / "apps" / "api" / ".env.local"
    settings = Settings(_env_file=str(env_local) if env_local.exists() else None)

    api_key = (getattr(settings, "ELEVENLABS_API_KEY", "") or "").strip()
    base_url = (getattr(settings, "ELEVENLABS_BASE_URL", "https://api.elevenlabs.io") or "https://api.elevenlabs.io").strip()
    output_format = (getattr(settings, "ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128") or "mp3_44100_128").strip()

    if not api_key:
        print("[STAGE A ERROR] ELEVENLABS_API_KEY is missing in apps/api/.env.local")
        sys.exit(1)

    # Mask key in output
    masked_key = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
    masked_voice = args.voice_id[:4] + "***" if len(args.voice_id) >= 4 else "***"

    print(f"[STAGE A] Configuration Validated:")
    print(f"  Base URL: {base_url}")
    print(f"  API Key:  PRESENT ({masked_key})")
    print(f"  Voice ID: {args.voice_id} (preview: {masked_voice})")
    print(f"  Model ID: {args.model_id}")
    print(f"  Format:   {output_format}")

    config = ElevenLabsConfig(
        api_key=api_key,
        base_url=base_url,
        voice_id=args.voice_id,
        model_id=args.model_id,
        output_format=output_format,
    )

    provider = ElevenLabsHTTPStreamingProvider(config)

    # 2. Capped Request Execution
    runtime_dir = ROOT / ".runtime"
    runtime_dir.mkdir(exist_ok=True)
    audio_path = runtime_dir / f"test_elevenlabs_{int(time.time())}.mp3"

    print(f"\n[STAGE B] Initiating 1 Capped Request (phrase: '{NON_PRIVATE_TEST_PHRASE}')...")
    start_time = time.time()
    first_byte_time = None
    total_bytes = 0

    try:
        import asyncio

        async def run_single_request():
            nonlocal first_byte_time, total_bytes
            with open(audio_path, "wb") as f:
                async for chunk in provider.synthesize(NON_PRIVATE_TEST_PHRASE):
                    if first_byte_time is None:
                        first_byte_time = time.time()
                    f.write(chunk)
                    total_bytes += len(chunk)

        asyncio.run(run_single_request())
        total_time = time.time() - start_time
        ttfb_ms = round((first_byte_time - start_time) * 1000) if first_byte_time else 0

        print(f"[STAGE B SUCCESS] Synthesis complete!")
        print(f"  Time to First Byte: {ttfb_ms} ms")
        print(f"  Total Duration:     {round(total_time * 1000)} ms")
        print(f"  Total Audio Bytes:  {total_bytes} bytes")
        print(f"  Audio Format:       {output_format}")

        if args.keep_audio:
            print(f"  Saved Audio Path:   {audio_path}")
        else:
            if audio_path.exists():
                audio_path.unlink()
            print("  Temporary audio file deleted (--keep-audio not specified).")

    except ElevenLabsError as err:
        print(f"[STAGE B ERROR] ElevenLabs provider returned error: {err}")
        if audio_path.exists():
            audio_path.unlink()
        sys.exit(1)
    except Exception as exc:
        print(f"[STAGE B ERROR] Unexpected failure: {type(exc).__name__} - {exc}")
        if audio_path.exists():
            audio_path.unlink()
        sys.exit(1)
    finally:
        # Clear environment gates
        os.environ.pop("HINAA_ALLOW_ELEVENLABS_TEST", None)
        os.environ.pop("HINAA_ELEVENLABS_TEST_CONFIRM", None)

if __name__ == "__main__":
    main()
