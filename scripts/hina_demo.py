"""End-to-end demo: a scripted multi-turn conversation, audited after the fact.

Runs THREE real turns through the live HTTP endpoint (mock brain, no paid calls),
then speaks the final reply through the voice pipeline. Everything it asserts is
read back from the persistent run ledger, so the demo proves the stop behaviour
instead of describing it.

Writes:
  <delivery>/hina-demo-evidence.json   machine-readable evidence
  <delivery>/hina-demo-reply.mp3       her spoken demo line
Exit code is non-zero if any assertion fails.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

API = r"C:\Users\unesh\OneDrive\all my cloud stroge\Desktop\APPS\HINAMYGIRL\apps\api"
DELIVERY = Path(r"C:\Users\unesh\.openclaw-autoclaw\agents\auto-coder\workspace\DELIVERY")
sys.path.insert(0, API)

from fastapi.testclient import TestClient  # noqa: E402

from hinaa_api.config import Settings  # noqa: E402
from hinaa_api.main import app  # noqa: E402
from hinaa_api.run_ledger import get_run_ledger  # noqa: E402
from hinaa_api.services import ConversationService  # noqa: E402
from hinaa_api.voice_fallback import clear_voice_cooldown  # noqa: E402

SESSION = "hina-demo-01"
TURNS = [
    "Hi Hina, are you there?",
    "What can you help me with today?",
    "Thanks. Give me one short tip to focus.",
]

client = TestClient(app)
turn_evidence = []

for index, prompt in enumerate(TURNS, 1):
    started = time.time()
    event_count = 0
    plan_seen = False
    with client.stream(
        "POST",
        "/v1/conversations/turns:stream",
        json={"sessionId": SESSION, "text": prompt, "providerMode": "mock"},
    ) as response:
        status = response.status_code
        for line in response.iter_lines():
            if not line.strip():
                continue
            event_count += 1
            if '"type": "plan"' in line:
                plan_seen = True
    turn_evidence.append(
        {
            "turn": index,
            "prompt": prompt,
            "httpStatus": status,
            "eventCount": event_count,
            "planReceived": plan_seen,
            "wallMs": int((time.time() - started) * 1000),
        }
    )
    print(f"turn {index}: HTTP {status}, {event_count} events, plan={plan_seen}")

# --- read the ledger back: every demo turn must have a stop/idle timestamp ---
ledger = get_run_ledger()
rows = [t for t in ledger.recent_turns(20) if t.session_id == SESSION]
rows_sorted = sorted(rows, key=lambda t: t.started_at)

stop_report = [
    {
        "turnId": t.turn_id,
        "status": t.status,
        "startedAt": t.started_at,
        "stoppedAt": t.stopped_at,
        "durationMs": t.duration_ms,
        "reply": t.response_preview,
        "stopped": t.stopped_at is not None,
    }
    for t in rows_sorted
]

all_stopped = bool(rows_sorted) and all(r["stopped"] for r in stop_report)
terminal = all(r["status"] in {"completed", "aborted"} for r in stop_report)

# --- she speaks: the voice pipeline must return real audio ---
clear_voice_cooldown()
settings = Settings()
service = ConversationService(settings)
spoken_line = rows_sorted[-1].response_preview or "Hello Unesh, I am Hina."
voice_started = time.perf_counter()
voice_result = None
voice_error = None
try:
    import asyncio

    voice_result = asyncio.run(
        service.synthesize_text(spoken_line, "hinaa", "auto", live=False)
    )
except Exception as exc:  # noqa: BLE001
    voice_error = f"{type(exc).__name__}: {exc}"
voice_wall_ms = int((time.perf_counter() - voice_started) * 1000)

audio_path = None
audio_bytes = 0
if voice_result is not None:
    audio_bytes = len(voice_result.value)
    audio_path = DELIVERY / "hina-demo-reply.mp3"
    audio_path.write_bytes(voice_result.value)

voice_events = [e for e in ledger.recent_tts(6) if e.get("bytes") is not None or True][:4]

evidence = {
    "session": SESSION,
    "generatedAt": time.time(),
    "turns": turn_evidence,
    "ledgerTurns": stop_report,
    "allTurnsStopped": all_stopped,
    "allTurnsTerminal": terminal,
    "voice": {
        "line": spoken_line,
        "provider": getattr(voice_result, "provider", None),
        "audioBytes": audio_bytes,
        "wallMs": voice_wall_ms,
        "audioFile": str(audio_path) if audio_path else None,
        "error": voice_error,
    },
    "ledgerTtsTail": ledger.recent_tts(4),
}

DELIVERY.mkdir(parents=True, exist_ok=True)
(DELIVERY / "hina-demo-evidence.json").write_text(
    json.dumps(evidence, indent=2), encoding="utf-8"
)

print("\n=== ledger turns for this demo ===")
for row in stop_report:
    print(
        f"  {row['turnId'][:8]}… status={row['status']} stopped={row['stopped']}"
        f" dur={row['durationMs']}ms reply={row['reply']!r}"
    )
print(
    f"\nallTurnsStopped={all_stopped}  allTurnsTerminal={terminal}"
    f"  voice={getattr(voice_result, 'provider', None)} bytes={audio_bytes} wall={voice_wall_ms}ms"
)
print(f"evidence -> {DELIVERY / 'hina-demo-evidence.json'}")

ok = all_stopped and terminal and audio_bytes > 0
print("\nDEMO RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
