"""
scripts/test_elevenlabs_stt_batch.py

Owner-gated script to test ElevenLabs Scribe v2 Batch STT API directly using Python.

REQUIRED ENVIRONMENT GATES:
  HINAA_ALLOW_ELEVENLABS_BATCH_STT_TEST=1
  HINAA_ELEVENLABS_BATCH_STT_TEST_CONFIRM=I_UNDERSTAND_THIS_MAY_COST_MONEY

USAGE:
  python scripts/test_elevenlabs_stt_batch.py [--duration SECONDS] [--keep-audio]
"""
import argparse
import asyncio
import io
import os
import sys
import time
import wave
from pathlib import Path

# Add apps/api to path so we can import hinaa_api
ROOT_DIR = Path(__file__).resolve().parents[1]
API_DIR = ROOT_DIR / "apps" / "api"
sys.path.insert(0, str(API_DIR))

from hinaa_api.config import Settings
from hinaa_api.providers.elevenlabs import ElevenLabsConfig, ElevenLabsSTTProvider


def check_owner_gates() -> None:
    allow = os.environ.get("HINAA_ALLOW_ELEVENLABS_BATCH_STT_TEST", "")
    confirm = os.environ.get("HINAA_ELEVENLABS_BATCH_STT_TEST_CONFIRM", "")

    if allow != "1" or confirm != "I_UNDERSTAND_THIS_MAY_COST_MONEY":
        print("❌ OWNER SAFETY GATES NOT SET.")
        print("To run real ElevenLabs batch STT test, you must set environment variables:")
        print("  export HINAA_ALLOW_ELEVENLABS_BATCH_STT_TEST=1")
        print("  export HINAA_ELEVENLABS_BATCH_STT_TEST_CONFIRM=I_UNDERSTAND_THIS_MAY_COST_MONEY")
        print("\nSkipping live API call.")
        sys.exit(1)


def generate_synthetic_pcm(duration_sec: float = 2.0, sample_rate: int = 16000) -> bytes:
    """Generate a 16kHz 16-bit mono sine wave PCM buffer for offline verification."""
    import math
    import struct

    total_samples = int(duration_sec * sample_rate)
    pcm = bytearray()
    frequency = 440.0  # 440 Hz tone
    for i in range(total_samples):
        sample = int(16000 * math.sin(2 * math.pi * frequency * i / sample_rate))
        pcm.extend(struct.pack("<h", sample))
    return bytes(pcm)


def record_microphone(duration_sec: float = 3.0, sample_rate: int = 16000) -> bytes:
    """Attempt sounddevice audio capture if installed, else fallback to synthetic tone."""
    try:
        import sounddevice as sd
        print(f"🎙️ Recording microphone for {duration_sec} seconds at {sample_rate} Hz (mono PCM16)...")
        audio = sd.rec(int(duration_sec * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")
        sd.wait()
        print("✅ Recording complete.")
        return audio.tobytes()
    except Exception as e:
        print(f"⚠️ Microphone capture unavailable ({e}). Using synthetic test audio.")
        return generate_synthetic_pcm(duration_sec, sample_rate)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Owner-gated ElevenLabs Scribe v2 Batch STT test")
    parser.add_argument("--duration", type=float, default=3.0, help="Utterance duration in seconds")
    parser.add_argument("--keep-audio", action="store_true", help="Save diagnostic WAV to disk")
    args = parser.parse_args()

    check_owner_gates()

    settings = Settings()
    if not settings.elevenlabs_configured:
        print("❌ ElevenLabs is not configured in .env.local (ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID missing).")
        sys.exit(1)

    api_key = settings.elevenlabs_api_key.get_secret_value() if settings.elevenlabs_api_key else ""
    config = ElevenLabsConfig(
        api_key=api_key,
        base_url=settings.elevenlabs_base_url,
        voice_id=settings.elevenlabs_voice_id,
        model_id=settings.elevenlabs_stt_model_id,  # scribe_v2
    )

    print("═════════════════════════════════════════════════════════════════")
    print(" HINAA Owner-Gated ElevenLabs Scribe v2 Batch STT Test")
    print("═════════════════════════════════════════════════════════════════")
    print(f"Provider model ID: {config.model_id}")
    print(f"API Base URL:      {config.base_url}")
    print(f"Key preview:       {api_key[:4]}***")

    # Record or synthesize audio
    pcm = record_microphone(duration_sec=args.duration)
    sample_rate = 16000
    sample_count = len(pcm) // 2
    actual_duration = sample_count / sample_rate

    print(f" Utterance sample count: {sample_count}")
    print(f" Utterance duration:     {actual_duration:.2f}s")
    print(f" PCM byte length:        {len(pcm)} bytes")

    if args.keep-audio if hasattr(args, "keep_audio") else False:
        out_wav = ROOT_DIR / "scratch" / "test_utterance_diagnostic.wav"
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm)
        print(f"💾 Saved diagnostic WAV to: {out_wav}")

    stt_provider = ElevenLabsSTTProvider(config)
    print("🚀 Sending batch STT request to ElevenLabs Scribe v2...")

    start_time = time.time()
    try:
        result = await stt_provider.transcribe(pcm, language="auto")
        elapsed_ms = int((time.time() - start_time) * 1000)

        print("\n✅ TRANSCRIPTION SUCCESSFUL")
        print(f"   Provider:   {result.provider}")
        print(f"   Latency:    {elapsed_ms} ms")
        print(f"   Transcript: \"{result.value}\"")

    except Exception as exc:
        print(f"\n❌ STT REQUEST FAILED: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
