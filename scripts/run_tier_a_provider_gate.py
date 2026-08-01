#!/usr/bin/env python3
"""Opt-in capped real-provider validation for Tier A conversation brain.

DISABLED BY DEFAULT. This script can incur Azure Speech and Gemini charges.

Required explicit confirmation:
  set HINAA_ALLOW_PAID_PROVIDER_TEST=1
  set HINAA_PAID_PROVIDER_TEST_CONFIRM=I_UNDERSTAND_THIS_MAY_COST_MONEY

Then run from repository root with apps/api/.env.local configured:
  apps\\api\\.venv\\Scripts\\python.exe scripts\\run_tier_a_provider_gate.py --max-turns 2

It never prints secret keys. It only reports observable timings and schema validity.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

CONFIRM = "I_UNDERSTAND_THIS_MAY_COST_MONEY"


def _gate_or_exit() -> None:
    if os.environ.get("HINAA_ALLOW_PAID_PROVIDER_TEST") != "1":
        print("Refusing to run: set HINAA_ALLOW_PAID_PROVIDER_TEST=1")
        raise SystemExit(2)
    if os.environ.get("HINAA_PAID_PROVIDER_TEST_CONFIRM") != CONFIRM:
        print(f"Refusing to run: set HINAA_PAID_PROVIDER_TEST_CONFIRM={CONFIRM}")
        raise SystemExit(2)


async def _run(max_turns: int) -> int:
    from hinaa_api.config import Settings
    from hinaa_api.models import TurnRequest
    from hinaa_api.services import ConversationService

    settings = Settings()  # type: ignore[call-arg]
    missing = settings.missing_real_configuration()
    if missing:
        print("Missing configuration:", ", ".join(missing))
        return 3

    service = ConversationService(settings)
    # Hard-capped owner evaluation utterances (max 2 successful turns).
    prompts = [
        (
            "Hi Hinaa, malai yo project ko current progress simple tarikale explain gara, "
            "ani next important step ke ho?"
        ),
        (
            "Actually mujhe short answer nahi chahiye. Please explain clearly how realtime "
            "interruption and memory consent work, but keep it natural for voice."
        ),
    ][: max(1, min(max_turns, 2))]

    print("Tier A paid provider gate starting (capped at 2 turns).")
    print(f"model={settings.gemini_model}")
    for index, text in enumerate(prompts, start=1):
        started = perf_counter()
        first_delta_ms: int | None = None

        async def emit(delta: str, _started=started) -> None:
            nonlocal first_delta_ms
            if first_delta_ms is None:
                first_delta_ms = int((perf_counter() - _started) * 1000)

        request = TurnRequest(
            sessionId="tier-a-paid-gate",
            text=text,
            companionId="hinaa",
            language="mixed",
            providerMode="real",
        )
        result = await service.create_live_plan(request, emit)
        total_ms = int((perf_counter() - started) * 1000)
        # Do not print full spoken content (may contain private phrasing).
        print(
            {
                "turn": index,
                "inputCategory": "romanized-ne-en" if index == 1 else "hi-en-technical",
                "provider": result.provider,
                "model": settings.gemini_model,
                "latencyMs": result.latency_ms,
                "firstDeltaMs": first_delta_ms,
                "totalMs": total_ms,
                "schemaValid": True,
                "spokenChars": len(result.value.spokenText),
                "emotion": result.value.emotion.primary,
                "gesture": result.value.performance.gesture,
                "toolRequests": result.value.toolRequests,
                "language": result.value.language,
            }
        )
    print("Done. Review timings and language quality manually. No commit performed.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Capped paid provider gate for Tier A")
    parser.add_argument("--max-turns", type=int, default=2)
    args = parser.parse_args()
    if args.max_turns > 2:
        print("Refusing: max-turns cannot exceed 2 for this gate.")
        raise SystemExit(2)
    _gate_or_exit()
    raise SystemExit(asyncio.run(_run(args.max_turns)))


if __name__ == "__main__":
    main()
