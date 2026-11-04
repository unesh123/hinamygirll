"""Explicit paid-provider smoke check with a supplied PCM16/16kHz mono WAV.

Does not read a microphone or trigger Hina actions. Prints only test transcript
and timing; API keys remain in backend settings. Run with --wav path/to/sample.wav.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from time import perf_counter
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
from hinaa_api.config import Settings
from hinaa_api.providers.streaming_stt import create_streaming_transcription


async def check(path, language, provider):
    with wave.open(str(path), "rb") as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):
            raise ValueError("Use a mono 16 kHz PCM16 WAV")
        audio = wav.readframes(wav.getnframes())
    started = perf_counter()
    first_partial = None
    statuses = []
    connected_ms = None

    async def partial(text):
        nonlocal first_partial
        if first_partial is None:
            first_partial = round((perf_counter() - started) * 1000)
            print(json.dumps({"firstPartialMs": first_partial, "text": text}), flush=True)

    async def status(mode):
        nonlocal connected_ms
        statuses.append(mode)
        if mode == "streaming":
            connected_ms = round((perf_counter() - started) * 1000)

    settings = Settings()
    if provider == "deepgram":
        settings = settings.model_copy(update={"elevenlabs_api_key": None})
    elif provider == "elevenlabs":
        settings = settings.model_copy(update={"deepgram_api_key": None})
    stream = create_streaming_transcription(settings, "real", language, partial, status)
    if stream is None:
        print(json.dumps({"success": False, "reason": "Streaming recognition is not configured for this language"}))
        return 1
    try:
        for offset in range(0, len(audio), 640):
            stream.offer(audio[offset:offset + 640])
            await asyncio.sleep(0.02)
        committed = perf_counter()
        final = await stream.finish()
        report = {"success": final is not None, "provider": stream.provider, "statuses": statuses,
                  "firstPartialMs": first_partial, "audioDurationMs": len(audio) // 32,
                  "connectedMs": connected_ms,
                  "finalAfterCommitMs": round((perf_counter() - committed) * 1000),
                  "finalText": final.value if final else "", "failureCode": stream.failure_code}
        target = ROOT / f".runtime/streaming-stt-probe-{stream.provider}.json"
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report), flush=True)
        return 0 if final else 1
    finally:
        await stream.abort()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--language", default="en-US")
    parser.add_argument("--provider", choices=["auto", "elevenlabs", "deepgram"], default="auto")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(check(args.wav, args.language, args.provider)))
