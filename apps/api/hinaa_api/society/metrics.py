"""Honest telemetry metrics & REST router for Agent Society health."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from ..runtime_paths import project_root


def _default_metrics_path() -> Path:
    override = os.environ.get("HINAA_SOCIETY_METRICS_PATH")
    if override:
        return Path(override)
    return project_root() / ".hina" / "society_metrics.json"


class SocietyMetricsStore:
    """Persistent counters and recent run outcomes (zero fabricated defaults)."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path else _default_metrics_path()
        self._lock = threading.Lock()
        self._data: dict[str, Any] = self._load()

    def _empty(self) -> dict[str, Any]:
        return {
            "total_circles": 0,
            "first_pass_verified": 0,
            "reviewer_catches": 0,
            "verifier_failures": 0,
            "lessons_stored": 0,
            "lessons_applied": 0,
            "skills_synthesized": 0,
            "marathons_completed": 0,
            "marathons_paused": 0,
            "recent_events": [],
            "updated_at": None,
        }

    def _load(self) -> dict[str, Any]:
        if not self._path.is_file():
            return self._empty()
        try:
            loaded = json.loads(self._path.read_text(encoding="utf-8"))
            base = self._empty()
            base.update(loaded)
            return base
        except Exception:
            return self._empty()

    def _save_locked(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data["updated_at"] = time.time()
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)

    def record_circle(
        self,
        *,
        goal: str,
        verified: bool,
        rounds: int,
        reviewer_caught: int,
        failures: list[str] | None = None,
    ) -> None:
        with self._lock:
            self._data["total_circles"] += 1
            if verified and rounds == 1:
                self._data["first_pass_verified"] += 1
            self._data["reviewer_catches"] += max(0, reviewer_caught)
            if not verified:
                self._data["verifier_failures"] += 1
            self._append_event_locked(
                {
                    "kind": "society.circle",
                    "goal": goal[:160],
                    "verified": verified,
                    "rounds": rounds,
                    "reviewer_caught": reviewer_caught,
                    "failures": (failures or [])[:5],
                    "ts": time.time(),
                }
            )
            self._save_locked()

    def record_counter(self, key: str, delta: int = 1, *, event: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._data[key] = int(self._data.get(key, 0)) + delta
            if event:
                self._append_event_locked({"ts": time.time(), **event})
            self._save_locked()

    def _append_event_locked(self, evt: dict[str, Any]) -> None:
        events = list(self._data.get("recent_events") or [])
        events.append(evt)
        self._data["recent_events"] = events[-25:]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            total = int(self._data.get("total_circles", 0))
            first = int(self._data.get("first_pass_verified", 0))
            rate = round((first / total) * 100.0, 1) if total > 0 else None
            return {
                **self._data,
                "first_pass_rate_pct": rate,
            }


_METRICS_SINGLETON: SocietyMetricsStore | None = None


def get_society_metrics() -> SocietyMetricsStore:
    global _METRICS_SINGLETON
    if _METRICS_SINGLETON is None:
        _METRICS_SINGLETON = SocietyMetricsStore()
    return _METRICS_SINGLETON


def create_society_router(store: SocietyMetricsStore | None = None) -> APIRouter:
    router = APIRouter()

    @router.get("/v1/society/metrics")
    @router.get("/api/v1/society/metrics")
    async def get_metrics() -> dict[str, Any]:
        st = store or get_society_metrics()
        return {"status": "ok", **st.snapshot()}

    return router
