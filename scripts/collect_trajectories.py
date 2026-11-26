"""Collect verified & failed agentic runs from .hina/agentic_runs into DPO pairs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from hinaa_api.training.grade import export_dpo_pairs  # noqa: E402


def main() -> int:
    runs_dir = ROOT / ".hina" / "agentic_runs"
    out_file = ROOT / ".hina" / "dpo_pairs.jsonl"
    traces = []
    if runs_dir.is_dir():
        for fp in sorted(runs_dir.glob("*.json")):
            try:
                raw = json.loads(fp.read_text(encoding="utf-8"))
                result = raw.get("result") or {}
                traces.append(
                    {
                        "goal": raw.get("goal") or "",
                        "status": result.get("status") or "unknown",
                        "verified": result.get("status") == "completed",
                        "summary": result.get("summary") or "",
                        "steps": result.get("steps") or [],
                    }
                )
            except Exception:
                continue
    pairs = export_dpo_pairs(traces, out_file)
    print(f"Scanned {len(traces)} runs -> wrote {len(pairs)} DPO pairs to {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
