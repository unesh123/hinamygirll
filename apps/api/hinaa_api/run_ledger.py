"""Persistent run ledger for Hina.

Every conversation turn, every TTS request, and every animation state change is
recorded here so the owner can audit *after the fact* that she really did stop:
a turn row carries a start timestamp, the delivered response, and a stop/idle
timestamp, and a TTS row carries provider, voice, model, latency and outcome.

Design rules
------------
* **Non-fatal.** A ledger failure must never break a turn or a synthesis call.
  Every public method swallows its own errors and logs one warning line.
* **Single file, WAL, stdlib only.** ``sqlite3`` lives beside the app's existing
  runtime DB so it moves with the app and needs no migration tooling.
* **Bounded reads.** ``recent_*`` return at most ``limit`` rows, newest first.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("hinaa.run_ledger")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS turns (
    turn_id       TEXT PRIMARY KEY,
    session_id    TEXT,
    started_at    REAL NOT NULL,
    stopped_at    REAL,
    status        TEXT,
    provider      TEXT,
    response_text TEXT,
    duration_ms   INTEGER
);
CREATE TABLE IF NOT EXISTS tts_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id       TEXT,
    created_at    REAL NOT NULL,
    provider      TEXT,
    voice_id      TEXT,
    model_id      TEXT,
    output_format TEXT,
    latency_ms    INTEGER,
    ok            INTEGER NOT NULL,
    audio_bytes   INTEGER,
    error         TEXT
);
CREATE TABLE IF NOT EXISTS motion_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at REAL NOT NULL,
    session_id TEXT,
    state      TEXT,
    detail     TEXT
);
CREATE TABLE IF NOT EXISTS execution_receipts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id         TEXT NOT NULL,
    session_id      TEXT,
    created_at      REAL NOT NULL,
    step_type       TEXT NOT NULL,
    step_name       TEXT,
    status          TEXT NOT NULL DEFAULT 'started',
    duration_ms     INTEGER,
    input_summary   TEXT,
    output_summary  TEXT,
    token_input     INTEGER,
    token_output    INTEGER,
    source_count    INTEGER,
    error           TEXT,
    metadata_json   TEXT
);
CREATE INDEX IF NOT EXISTS idx_turns_started ON turns(started_at);
CREATE INDEX IF NOT EXISTS idx_tts_created ON tts_events(created_at);
CREATE INDEX IF NOT EXISTS idx_motion_created ON motion_events(created_at);
CREATE INDEX IF NOT EXISTS idx_receipts_turn ON execution_receipts(turn_id);
CREATE INDEX IF NOT EXISTS idx_receipts_created ON execution_receipts(created_at);
"""


@dataclass(frozen=True, slots=True)
class TurnRow:
    turn_id: str
    session_id: str | None
    started_at: float
    stopped_at: float | None
    status: str | None
    provider: str | None
    response_preview: str | None
    duration_ms: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "turnId": self.turn_id,
            "sessionId": self.session_id,
            "startedAt": self.started_at,
            "stoppedAt": self.stopped_at,
            "status": self.status,
            "provider": self.provider,
            "responsePreview": self.response_preview,
            "durationMs": self.duration_ms,
        }


def _now() -> float:
    return time.time()


def _preview(text: str | None, limit: int = 240) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    return text[:limit]


class RunLedger:
    """SQLite-backed audit trail. Thread-safe; every write is best-effort."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._ready = False
        self._connect()

    # -- lifecycle ---------------------------------------------------------
    def _connect(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._path), check_same_thread=False, timeout=5.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.executescript(_SCHEMA)
            conn.commit()
            self._conn = conn
            self._ready = True
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Run ledger unavailable at %s: %s", self._path, exc)
            self._conn = None
            self._ready = False

    @property
    def available(self) -> bool:
        return self._ready and self._conn is not None

    def _execute(self, sql: str, params: tuple[Any, ...]) -> None:
        if not self.available:
            return
        try:
            with self._lock:
                self._conn.execute(sql, params)  # type: ignore[union-attr]
                self._conn.commit()  # type: ignore[union-attr]
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Run ledger write failed: %s", exc)

    # -- turns -------------------------------------------------------------
    def record_turn_start(
        self,
        turn_id: str,
        *,
        session_id: str | None = None,
        provider: str | None = None,
    ) -> None:
        self._execute(
            "INSERT OR REPLACE INTO turns "
            "(turn_id, session_id, started_at, stopped_at, status, provider) "
            "VALUES (?, ?, ?, NULL, 'running', ?)",
            (turn_id, session_id, _now(), provider),
        )

    def record_turn_stop(
        self,
        turn_id: str,
        *,
        response_text: str | None = None,
        status: str = "completed",
        provider: str | None = None,
    ) -> None:
        stopped_at = _now()
        if not self.available:
            return
        try:
            with self._lock:
                row = self._conn.execute(  # type: ignore[union-attr]
                    "SELECT started_at FROM turns WHERE turn_id = ?", (turn_id,)
                ).fetchone()
                started = float(row[0]) if row else stopped_at
                self._conn.execute(  # type: ignore[union-attr]
                    "UPDATE turns SET stopped_at = ?, status = ?, "
                    "response_text = COALESCE(?, response_text), "
                    "provider = COALESCE(?, provider), duration_ms = ? "
                    "WHERE turn_id = ?",
                    (
                        stopped_at,
                        status,
                        _preview(response_text),
                        provider,
                        int((stopped_at - started) * 1000),
                        turn_id,
                    ),
                )
                self._conn.commit()  # type: ignore[union-attr]
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Run ledger stop write failed: %s", exc)

    # -- tts ---------------------------------------------------------------
    def record_tts(
        self,
        *,
        provider: str,
        voice_id: str | None,
        model_id: str | None,
        output_format: str | None,
        latency_ms: int | None,
        ok: bool,
        audio_bytes: int | None = None,
        error: str | None = None,
        turn_id: str | None = None,
    ) -> None:
        self._execute(
            "INSERT INTO tts_events "
            "(turn_id, created_at, provider, voice_id, model_id, output_format, "
            " latency_ms, ok, audio_bytes, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                turn_id,
                _now(),
                provider,
                voice_id,
                model_id,
                output_format,
                latency_ms,
                1 if ok else 0,
                audio_bytes,
                _preview(error),
            ),
        )

    # -- motion ------------------------------------------------------------
    def record_motion(
        self, *, state: str, session_id: str | None = None, detail: str | None = None
    ) -> None:
        self._execute(
            "INSERT INTO motion_events (created_at, session_id, state, detail) "
            "VALUES (?, ?, ?, ?)",
            (_now(), session_id, state, _preview(detail)),
        )

    # -- execution receipts ------------------------------------------------
    def record_receipt(
        self,
        *,
        turn_id: str,
        step_type: str,
        step_name: str | None = None,
        status: str = "started",
        duration_ms: int | None = None,
        input_summary: str | None = None,
        output_summary: str | None = None,
        token_input: int | None = None,
        token_output: int | None = None,
        source_count: int | None = None,
        error: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record one step of an execution workflow for audit inspection."""
        import json as _json
        meta_str = _json.dumps(metadata) if metadata else None
        self._execute(
            "INSERT INTO execution_receipts "
            "(turn_id, session_id, created_at, step_type, step_name, status, "
            " duration_ms, input_summary, output_summary, token_input, "
            " token_output, source_count, error, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                turn_id,
                session_id,
                _now(),
                step_type,
                step_name,
                status,
                duration_ms,
                _preview(input_summary, 500),
                _preview(output_summary, 500),
                token_input,
                token_output,
                source_count,
                _preview(error),
                meta_str,
            ),
        )

    def recent_receipts(
        self, *, turn_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Retrieve recent execution receipts, optionally filtered by turn."""
        if not self.available:
            return []
        limit = max(1, min(limit, 500))
        try:
            with self._lock:
                if turn_id:
                    rows = self._conn.execute(  # type: ignore[union-attr]
                        "SELECT id, turn_id, session_id, created_at, step_type, "
                        "step_name, status, duration_ms, input_summary, "
                        "output_summary, token_input, token_output, source_count, "
                        "error, metadata_json "
                        "FROM execution_receipts WHERE turn_id = ? "
                        "ORDER BY created_at ASC LIMIT ?",
                        (turn_id, limit),
                    ).fetchall()
                else:
                    rows = self._conn.execute(  # type: ignore[union-attr]
                        "SELECT id, turn_id, session_id, created_at, step_type, "
                        "step_name, status, duration_ms, input_summary, "
                        "output_summary, token_input, token_output, source_count, "
                        "error, metadata_json "
                        "FROM execution_receipts "
                        "ORDER BY created_at DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
        except Exception as exc:
            logger.warning("Run ledger receipt read failed: %s", exc)
            return []
        import json as _json
        keys = (
            "id", "turnId", "sessionId", "createdAt", "stepType",
            "stepName", "status", "durationMs", "inputSummary",
            "outputSummary", "tokenInput", "tokenOutput", "sourceCount",
            "error", "metadata",
        )
        results = []
        for r in rows:
            d = dict(zip(keys, r))
            if d.get("metadata") and isinstance(d["metadata"], str):
                try:
                    d["metadata"] = _json.loads(d["metadata"])
                except Exception:
                    pass
            results.append(d)
        return results

    # -- reads -------------------------------------------------------------
    def recent_turns(self, limit: int = 20) -> list[TurnRow]:
        if not self.available:
            return []
        limit = max(1, min(limit, 200))
        try:
            with self._lock:
                rows = self._conn.execute(  # type: ignore[union-attr]
                    "SELECT turn_id, session_id, started_at, stopped_at, status, "
                    "provider, response_text, duration_ms FROM turns "
                    "ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Run ledger read failed: %s", exc)
            return []
        return [
            TurnRow(
                turn_id=r[0],
                session_id=r[1],
                started_at=r[2],
                stopped_at=r[3],
                status=r[4],
                provider=r[5],
                response_preview=r[6],
                duration_ms=r[7],
            )
            for r in rows
        ]

    def recent_tts(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.available:
            return []
        limit = max(1, min(limit, 200))
        try:
            with self._lock:
                rows = self._conn.execute(  # type: ignore[union-attr]
                    "SELECT created_at, provider, voice_id, model_id, output_format, "
                    "latency_ms, ok, audio_bytes, error, turn_id FROM tts_events "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Run ledger tts read failed: %s", exc)
            return []
        keys = (
            "createdAt",
            "provider",
            "voiceId",
            "modelId",
            "outputFormat",
            "latencyMs",
            "ok",
            "audioBytes",
            "error",
            "turnId",
        )
        return [dict(zip(keys, r)) for r in rows]

    def recent_motion(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.available:
            return []
        limit = max(1, min(limit, 500))
        try:
            with self._lock:
                rows = self._conn.execute(  # type: ignore[union-attr]
                    "SELECT created_at, session_id, state, detail FROM motion_events "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Run ledger motion read failed: %s", exc)
            return []
        return [
            {"createdAt": r[0], "sessionId": r[1], "state": r[2], "detail": r[3]}
            for r in rows
        ]

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # pragma: no cover - defensive
                pass


def default_ledger_path() -> Path:
    """``apps/api/.runtime/run_ledger.db`` — beside the app's existing runtime DB."""
    return Path(__file__).resolve().parents[1] / ".runtime" / "run_ledger.db"


_LEDGER: RunLedger | None = None
_LEDGER_LOCK = threading.Lock()


def get_run_ledger() -> RunLedger:
    """Process-wide ledger. A single connection is reused so repeated turns do
    not churn file handles, and a failure to open leaves an inert ledger that
    still accepts (and drops) writes."""
    global _LEDGER
    if _LEDGER is None:
        with _LEDGER_LOCK:
            if _LEDGER is None:
                _LEDGER = RunLedger(default_ledger_path())
    return _LEDGER
