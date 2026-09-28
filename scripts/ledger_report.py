"""Inspect Hina's run ledger from the command line.

    python scripts/ledger_report.py
    python scripts/ledger_report.py --turns 50 --tts 50 --motion 30 --json

Prints each conversation turn with its start time, delivered reply and stop/idle
timestamp, then each TTS request with provider, voice, model, latency, outcome
and byte count. This is the human-readable half of the "did she actually stop?"
audit; the JSON output is the machine-readable half.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from hinaa_api.run_ledger import RunLedger, default_ledger_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect Hina's run ledger.")
    parser.add_argument("--db", default=str(default_ledger_path()))
    parser.add_argument("--turns", type=int, default=20)
    parser.add_argument("--tts", type=int, default=20)
    parser.add_argument("--motion", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    ledger = RunLedger(args.db)
    if not ledger.available:
        print(f"ledger unavailable at {args.db}", file=sys.stderr)
        return 2

    payload: dict[str, object] = {
        "turns": [t.as_dict() for t in ledger.recent_turns(args.turns)],
        "tts": ledger.recent_tts(args.tts),
    }
    if args.motion:
        payload["motion"] = ledger.recent_motion(args.motion)

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    turns = payload["turns"]
    tts = payload["tts"]
    print(f"=== turns ({len(turns)}) ===")
    for turn in turns:  # type: ignore[union-attr]
        stopped = "yes" if turn["stoppedAt"] else "NO"
        print(
            f"  {turn['turnId']}  status={turn['status']}  stopped={stopped}"
            f"  dur={turn['durationMs']}ms  {turn['responsePreview']!r}"
        )
    print(f"=== tts ({len(tts)}) ===")
    for event in tts:  # type: ignore[union-attr]
        print(
            f"  ok={event['ok']} provider={event['provider']} voice={event['voiceId']}"
            f" model={event['modelId']} latency={event['latencyMs']}ms"
            f" bytes={event['audioBytes']} err={event['error']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
