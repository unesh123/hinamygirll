"""Phase 19: Reliable Developer Event Contracts & Resumable Event Stream.

Implements the Feature B typed event contract with monotonic sequence ordering,
SQLite WAL persistence, Last-Event-ID resumption, and secure payload redaction.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, AsyncIterator, Dict, List, Optional, Set
from uuid import uuid4
from pydantic import BaseModel, Field

logger = logging.getLogger("hinaa.coding.events")

# Standard event kind constants per Phase 19 directive
EVENT_TASK_STARTED = "task.started"
EVENT_PLAN_UPDATED = "plan.updated"
EVENT_AGENT_ASSIGNED = "agent.assigned"
EVENT_FILE_OPENED = "file.opened"
EVENT_FILE_PATCH_PROPOSED = "file.patch.proposed"
EVENT_FILE_PATCH_APPLIED = "file.patch.applied"
EVENT_FILE_SAVED = "file.saved"
EVENT_COMMAND_STARTED = "command.started"
EVENT_COMMAND_STDOUT = "command.stdout"
EVENT_COMMAND_STDERR = "command.stderr"
EVENT_COMMAND_EXITED = "command.exited"
EVENT_TEST_STARTED = "test.started"
EVENT_TEST_PASSED = "test.passed"
EVENT_TEST_FAILED = "test.failed"
EVENT_PREVIEW_STARTING = "preview.starting"
EVENT_PREVIEW_READY = "preview.ready"
EVENT_PREVIEW_FAILED = "preview.failed"
EVENT_SCREENSHOT_CAPTURED = "screenshot.captured"
EVENT_REVIEW_FINDING = "review.finding"
EVENT_REPAIR_STARTED = "repair.started"
EVENT_ARTIFACT_VERIFIED = "artifact.verified"
EVENT_TASK_PARTIAL = "task.partial"
EVENT_TASK_COMPLETED = "task.completed"
EVENT_TASK_FAILED = "task.failed"


class DeveloperEvent(BaseModel):
    """Authoritative typed event contract for Phase 19 Live Developer Studio."""

    schema_version: int = 1
    event_id: str = Field(default_factory=lambda: f"dev-evt-{uuid4().hex[:12]}")
    task_id: str
    workspace_id: str
    seq: int = 0
    emitted_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: str
    actor_role: str = "engineer"  # architect | engineer | critic | reviewer | system
    file_path: Optional[str] = None
    old_sha256: Optional[str] = None
    new_sha256: Optional[str] = None
    patch_id: Optional[str] = None
    command_id: Optional[str] = None
    process_id: Optional[str] = None
    preview_id: Optional[str] = None
    artifact_id: Optional[str] = None
    redacted_payload: Dict[str, Any] = Field(default_factory=dict)

    @property
    def payload(self) -> Dict[str, Any]:
        return self.redacted_payload

    def to_sse_line(self) -> str:
        """Formats the event as a standard Server-Sent Event frame with cursor id."""
        data = self.model_dump_json()
        return f"id: {self.seq}\nevent: {self.kind}\ndata: {data}\n\n"


class DeveloperEventStore:
    """Thread-safe, SQLite WAL-backed event store with monotonic sequence & resumption."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            runtime_dir = Path(".runtime/coding").resolve()
            runtime_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = runtime_dir / "developer_events.db"
        else:
            self.db_path = db_path.resolve()
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._seq_counters: Dict[str, int] = {}
        self._subscribers: Dict[str, Set[asyncio.Queue[DeveloperEvent]]] = {}
        self._lock = asyncio.Lock()
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS developer_events (
                    event_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    emitted_at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    file_path TEXT,
                    old_sha256 TEXT,
                    new_sha256 TEXT,
                    patch_id TEXT,
                    command_id TEXT,
                    process_id TEXT,
                    preview_id TEXT,
                    artifact_id TEXT,
                    payload_json TEXT NOT NULL,
                    UNIQUE(task_id, seq)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_seq ON developer_events(task_id, seq);")
            conn.commit()
        finally:
            conn.close()

    async def emit_event(
        self,
        task_id: str,
        workspace_id: str,
        kind: str,
        actor_role: str = "engineer",
        file_path: Optional[str] = None,
        old_sha256: Optional[str] = None,
        new_sha256: Optional[str] = None,
        patch_id: Optional[str] = None,
        command_id: Optional[str] = None,
        process_id: Optional[str] = None,
        preview_id: Optional[str] = None,
        artifact_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> DeveloperEvent:
        """Atomically emits an event, stores it in SQLite, and pushes to active subscribers."""
        async with self._lock:
            # Monotonic sequence computation
            if task_id not in self._seq_counters:
                # Query max seq from database
                conn = sqlite3.connect(self.db_path)
                try:
                    cur = conn.execute("SELECT COALESCE(MAX(seq), 0) FROM developer_events WHERE task_id = ?", (task_id,))
                    row = cur.fetchone()
                    self._seq_counters[task_id] = row[0] if row else 0
                finally:
                    conn.close()

            self._seq_counters[task_id] += 1
            seq = self._seq_counters[task_id]

            # Redact sensitive parameters from payload
            clean_payload = self._redact_secrets(payload or {})

            event = DeveloperEvent(
                task_id=task_id,
                workspace_id=workspace_id,
                seq=seq,
                kind=kind,
                actor_role=actor_role,
                file_path=file_path,
                old_sha256=old_sha256,
                new_sha256=new_sha256,
                patch_id=patch_id,
                command_id=command_id,
                process_id=process_id,
                preview_id=preview_id,
                artifact_id=artifact_id,
                redacted_payload=clean_payload,
            )

            # Persist to database
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO developer_events (
                        event_id, task_id, workspace_id, seq, emitted_at, kind, actor_role,
                        file_path, old_sha256, new_sha256, patch_id, command_id, process_id,
                        preview_id, artifact_id, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    event.task_id,
                    event.workspace_id,
                    event.seq,
                    event.emitted_at,
                    event.kind,
                    event.actor_role,
                    event.file_path,
                    event.old_sha256,
                    event.new_sha256,
                    event.patch_id,
                    event.command_id,
                    event.process_id,
                    event.preview_id,
                    event.artifact_id,
                    json.dumps(event.redacted_payload),
                ))
                conn.commit()
            finally:
                conn.close()

            # Dispatch to subscribers
            subs = self._subscribers.get(task_id, set())
            for q in list(subs):
                try:
                    q.put_nowait(event)
                except Exception:
                    pass

            return event

    async def get_events(self, task_id: str, since_seq: int = 0) -> List[DeveloperEvent]:
        """Alias for get_events_after with async interface for callers."""
        return self.get_events_after(task_id, after_seq=since_seq)

    def get_events_after(self, task_id: str, after_seq: int = 0) -> List[DeveloperEvent]:
        """Fetches historical events from database starting strictly after after_seq."""
        events: List[DeveloperEvent] = []
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("""
                SELECT * FROM developer_events
                WHERE task_id = ? AND seq > ?
                ORDER BY seq ASC
            """, (task_id, after_seq))
            for row in cur.fetchall():
                try:
                    payload = json.loads(row["payload_json"])
                except Exception:
                    payload = {}
                events.append(DeveloperEvent(
                    schema_version=1,
                    event_id=row["event_id"],
                    task_id=row["task_id"],
                    workspace_id=row["workspace_id"],
                    seq=row["seq"],
                    emitted_at=row["emitted_at"],
                    kind=row["kind"],
                    actor_role=row["actor_role"],
                    file_path=row["file_path"],
                    old_sha256=row["old_sha256"],
                    new_sha256=row["new_sha256"],
                    patch_id=row["patch_id"],
                    command_id=row["command_id"],
                    process_id=row["process_id"],
                    preview_id=row["preview_id"],
                    artifact_id=row["artifact_id"],
                    redacted_payload=payload,
                ))
        finally:
            conn.close()
        return events

    def subscribe(self, task_id: str) -> asyncio.Queue[DeveloperEvent]:
        """Registers a real-time event subscriber queue."""
        if task_id not in self._subscribers:
            self._subscribers[task_id] = set()
        q: asyncio.Queue[DeveloperEvent] = asyncio.Queue()
        self._subscribers[task_id].add(q)
        return q

    def unsubscribe(self, task_id: str, q: asyncio.Queue[DeveloperEvent]) -> None:
        """Removes a subscriber queue."""
        subs = self._subscribers.get(task_id)
        if subs and q in subs:
            subs.remove(q)

    @staticmethod
    def _redact_secrets(data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redacts API keys, bearer tokens, and secrets."""
        redacted: Dict[str, Any] = {}
        sensitive_keys = {"token", "key", "secret", "password", "auth", "credential", "cookie", "xi-api-key"}
        for k, v in data.items():
            k_lower = k.lower()
            if any(s in k_lower for s in sensitive_keys) and isinstance(v, str):
                if len(v) > 8:
                    redacted[k] = f"{v[:4]}...[REDACTED]...{v[-4:]}"
                else:
                    redacted[k] = "[REDACTED]"
            elif isinstance(v, dict):
                redacted[k] = DeveloperEventStore._redact_secrets(v)
            elif isinstance(v, list):
                redacted[k] = [
                    DeveloperEventStore._redact_secrets(item) if isinstance(item, dict) else item
                    for item in v
                ]
            else:
                redacted[k] = v
        return redacted


_GLOBAL_EVENT_STORE: Optional[DeveloperEventStore] = None


def get_developer_event_store() -> DeveloperEventStore:
    global _GLOBAL_EVENT_STORE
    if _GLOBAL_EVENT_STORE is None:
        _GLOBAL_EVENT_STORE = DeveloperEventStore()
    return _GLOBAL_EVENT_STORE
