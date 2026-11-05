"""
HINAA OS — Phase 11 Durable Event Journal & SSE Streamer
Provides append-only persistence of task lifecycle events and tool receipts
with monotonic sequence numbering and cursor-based SSE reconnection.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import AsyncGenerator, List, Optional

from .contracts import TaskEvent, TaskStatus, _now_iso

logger = logging.getLogger("hinaa.agents.event_log")


class EventLogStore:
    """Thread-safe SQLite-backed append-only task event journal."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        if db_path is None:
            try:
                from ..config import DATA_DIR
                self.db_path = DATA_DIR / "hinaa_agent_events.db"
            except Exception:
                base = Path(__file__).resolve().parents[4]
                self.db_path = base / "apps" / "api" / "data" / "hinaa_agent_events.db"
        else:
            self.db_path = Path(db_path)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_events (
                    event_id TEXT PRIMARY KEY,
                    sequence INTEGER NOT NULL,
                    task_id TEXT NOT NULL,
                    node_id TEXT,
                    timestamp TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    state_before TEXT,
                    state_after TEXT,
                    trace_id TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_task_seq ON agent_events(task_id, sequence)")

    def append_event(self, event: TaskEvent) -> TaskEvent:
        """Atomically persist event with next monotonic sequence number for task."""
        with self._lock, self._get_connection() as conn:
            cur = conn.execute("SELECT COALESCE(MAX(sequence), 0) + 1 FROM agent_events WHERE task_id = ?", (event.task_id,))
            next_seq = cur.fetchone()[0]
            event.sequence = next_seq

            conn.execute(
                """
                INSERT INTO agent_events (
                    event_id, sequence, task_id, node_id, timestamp,
                    actor_role, event_type, payload, state_before, state_after, trace_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.sequence,
                    event.task_id,
                    event.node_id,
                    event.timestamp,
                    event.actor_role.value if hasattr(event.actor_role, "value") else str(event.actor_role),
                    event.event_type,
                    json.dumps(event.payload, ensure_ascii=False),
                    event.state_before.value if event.state_before else None,
                    event.state_after.value if event.state_after else None,
                    event.trace_id,
                ),
            )
        return event

    def get_events(self, task_id: str, since_sequence: int = 0, limit: int = 100) -> List[TaskEvent]:
        """Fetch ordered events since cursor sequence number."""
        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                """
                SELECT * FROM agent_events
                WHERE task_id = ? AND sequence > ?
                ORDER BY sequence ASC
                LIMIT ?
                """,
                (task_id, since_sequence, limit),
            )
            events: List[TaskEvent] = []
            for row in cur.fetchall():
                events.append(
                    TaskEvent(
                        event_id=row["event_id"],
                        sequence=row["sequence"],
                        task_id=row["task_id"],
                        node_id=row["node_id"],
                        timestamp=row["timestamp"],
                        actor_role=row["actor_role"],
                        event_type=row["event_type"],
                        payload=json.loads(row["payload"]),
                        state_before=TaskStatus(row["state_before"]) if row["state_before"] else None,
                        state_after=TaskStatus(row["state_after"]) if row["state_after"] else None,
                        trace_id=row["trace_id"],
                    )
                )
            return events


# Singleton event log store
event_log_store = EventLogStore()
