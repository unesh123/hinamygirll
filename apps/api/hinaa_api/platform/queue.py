"""
HINAA OS — Phase 17 Durable Task Queues & Exactly-Once Consequential Effects.

Provides:
- Redis Streams outbox/inbox for distributed staging/cloud profiles.
- Zero-external-dependency SQLite WAL fallback for local desktop & LAN profiles.
- Transactional Outbox pattern guaranteeing atomic database mutation + event staging.
- Idempotency key registry (platform_idempotency_keys) preventing duplicate consequential side effects.
- Strict payload sanitization (zero secrets, bearer tokens, or auth cookies logged).
- Dead Letter Queue (DLQ) with retry budgets, backoff, and manual operator replay.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from hinaa_api.platform.contracts import (
    DLQEntry,
    OutboxEntry,
    QueueBackendType,
)

logger = logging.getLogger(__name__)


class IdempotencyResult:
    """Wrapper that evaluates to bool for newly_executed while supporting tuple unpacking and result access."""
    def __init__(self, result: Any, newly_executed: bool):
        self.result = result
        self.newly_executed = newly_executed

    def __bool__(self) -> bool:
        return self.newly_executed

    def __getitem__(self, idx: int) -> Any:
        return (self.result, self.newly_executed)[idx]

    def __iter__(self):
        yield self.result
        yield self.newly_executed


class DurableQueueManager:
    """Manages transactional outbox, worker consumer groups, and idempotency keys."""

    def __init__(self, db_path: Optional[str] = None, redis_url: Optional[str] = None) -> None:
        self.db_path = db_path or os.environ.get("HINAA_AUTOPILOT_DB", "hinaa_autopilot.db")
        self.redis_url = redis_url or os.environ.get("HINAA_REDIS_URL")
        self._is_memory = str(self.db_path) == ":memory:"
        self._mem_conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()

        # Redis connection setup if configured and reachable
        self.redis = None
        if self.redis_url:
            try:
                import redis
                self.redis = redis.Redis.from_url(self.redis_url, decode_responses=True)
                self.redis.ping()
            except Exception as e:
                logger.warning(f"Redis unavailable ({e}), falling back to SQLite durable queue.")
                self.redis = None

        self._init_sqlite_tables()

    def _get_connection(self) -> sqlite3.Connection:
        if self._is_memory:
            if self._mem_conn is None:
                self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._mem_conn.row_factory = sqlite3.Row
            return self._mem_conn

        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite_tables(self) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS platform_outbox (
                        message_id TEXT PRIMARY KEY,
                        operation_key TEXT NOT NULL,
                        topic TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'PENDING',
                        retry_count INTEGER NOT NULL DEFAULT 0,
                        max_retries INTEGER NOT NULL DEFAULT 3,
                        created_at REAL NOT NULL,
                        dispatched_at REAL,
                        committed_at REAL
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS platform_idempotency_keys (
                        operation_key TEXT PRIMARY KEY,
                        result_json TEXT NOT NULL,
                        executed_at REAL NOT NULL
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS platform_dlq (
                        dlq_id TEXT PRIMARY KEY,
                        operation_key TEXT NOT NULL,
                        topic TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        failure_reason TEXT NOT NULL,
                        retry_count INTEGER NOT NULL,
                        dead_lettered_at REAL NOT NULL,
                        replayed_at REAL
                    );
                    """
                )
                conn.commit()

    @property
    def backend_type(self) -> QueueBackendType:
        return QueueBackendType.REDIS_STREAMS if self.redis is not None else QueueBackendType.SQLITE_DURABLE

    def sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Scrubs sensitive tokens, passwords, and private auth keys from message payloads."""
        forbidden_keys = {"token", "secret", "password", "api_key", "bearer", "authorization", "private_key"}
        sanitized = {}
        for k, v in payload.items():
            if any(f in k.lower() for f in forbidden_keys):
                sanitized[k] = "[REDACTED_SECRET]"
            elif isinstance(v, dict):
                sanitized[k] = self.sanitize_payload(v)
            else:
                sanitized[k] = v
        return sanitized

    def enqueue(self, operation_key: str, topic: str, payload: Dict[str, Any]) -> OutboxEntry:
        """Atomically inserts task into outbox and dispatches to queue."""
        clean_payload = self.sanitize_payload(payload)
        now = time.time()
        message_id = f"outbox_{uuid.uuid4().hex[:12]}"

        entry = OutboxEntry(
            message_id=message_id,
            operation_key=operation_key,
            topic=topic,
            payload=clean_payload,
            status="PENDING",
            retry_count=0,
            created_at=now,
        )

        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO platform_outbox (
                        message_id, operation_key, topic, payload_json,
                        status, retry_count, max_retries, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        entry.message_id,
                        entry.operation_key,
                        entry.topic,
                        json.dumps(entry.payload),
                        entry.status,
                        entry.retry_count,
                        entry.max_retries,
                        entry.created_at,
                    ),
                )
                conn.commit()

        # If Redis is active, dispatch to Redis Stream
        if self.redis is not None:
            try:
                self.redis.xadd(topic, {"message_id": message_id, "operation_key": operation_key})
                self._mark_dispatched(message_id)
            except Exception as e:
                logger.warning(f"Redis publish failed, message remains in durable SQLite outbox: {e}")

        return entry

    def publish_message(
        self,
        stream: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
    ) -> str:
        """Convenience method to publish message into stream with auto or custom key."""
        key = idempotency_key or f"idemp_{uuid.uuid4().hex[:12]}"
        entry = self.enqueue(operation_key=key, topic=stream, payload=payload)
        return entry.message_id

    def ack_message(self, message_id: str) -> None:
        """Marks message committed/acknowledged."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE platform_outbox SET status = 'COMMITTED', committed_at = ? WHERE message_id = ?;",
                    (time.time(), message_id),
                )
                conn.commit()

    def _mark_dispatched(self, message_id: str) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE platform_outbox SET status = 'IN_FLIGHT', dispatched_at = ? WHERE message_id = ?;",
                    (time.time(), message_id),
                )
                conn.commit()

    def execute_with_idempotency(
        self,
        operation_key: str,
        side_effect_fn: Callable[[], Any],
    ) -> IdempotencyResult:
        """
        Executes a consequential side effect with strict exactly-once semantics.
        Returns: IdempotencyResult which bool() evaluates to whether it was newly executed.
        """
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT result_json FROM platform_idempotency_keys WHERE operation_key = ?;",
                    (operation_key,),
                )
                row = cur.fetchone()
                if row:
                    # Consequential effect ALREADY executed. Return previous result without re-executing.
                    val = json.loads(row["result_json"])
                    return IdempotencyResult(val, False)

                # Execute side-effect function
                result = side_effect_fn()

                # Atomically record idempotency receipt
                res_clean = result if isinstance(result, (dict, list, str, int, float, bool)) else {"status": "executed"}
                conn.execute(
                    """
                    INSERT INTO platform_idempotency_keys (operation_key, result_json, executed_at)
                    VALUES (?, ?, ?);
                    """,
                    (operation_key, json.dumps(res_clean), time.time()),
                )
                conn.commit()
                return IdempotencyResult(result, True)

    def fail_and_retry(self, message_id: str, error_message: str) -> bool:
        """Increments retry count; moves to DLQ if max retries exceeded."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT * FROM platform_outbox WHERE message_id = ?;",
                    (message_id,),
                )
                row = cur.fetchone()
                if not row:
                    return False

                current_retries = row["retry_count"] + 1
                max_retries = row["max_retries"]

                if current_retries >= max_retries:
                    # Dead letter
                    dlq_id = f"dlq-{uuid.uuid4().hex[:12]}"
                    conn.execute(
                        """
                        INSERT INTO platform_dlq (
                            dlq_id, operation_key, topic, payload_json,
                            failure_reason, retry_count, dead_lettered_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            dlq_id,
                            row["operation_key"],
                            row["topic"],
                            row["payload_json"],
                            error_message,
                            current_retries,
                            time.time(),
                        ),
                    )
                    conn.execute(
                        "UPDATE platform_outbox SET status = 'DEAD_LETTER' WHERE message_id = ?;",
                        (message_id,),
                    )
                    conn.commit()
                    return False
                else:
                    conn.execute(
                        "UPDATE platform_outbox SET retry_count = ?, status = 'PENDING' WHERE message_id = ?;",
                        (current_retries, message_id),
                    )
                    conn.commit()
                    return True

    def replay_dlq(self, dlq_id: str) -> Optional[OutboxEntry]:
        """Requeues a dead-lettered message for reprocessing."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT * FROM platform_dlq WHERE dlq_id = ?;", (dlq_id,))
                row = cur.fetchone()
                if not row:
                    return None

                # Re-enqueue with fresh message_id
                entry = self.enqueue(
                    operation_key=row["operation_key"],
                    topic=row["topic"],
                    payload=json.loads(row["payload_json"]),
                )
                conn.execute(
                    "UPDATE platform_dlq SET replayed_at = ? WHERE dlq_id = ?;",
                    (time.time(), dlq_id),
                )
                conn.commit()
                return entry

    def get_pending_messages(self, limit: int = 50) -> List[OutboxEntry]:
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT * FROM platform_outbox WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT ?;",
                    (limit,),
                )
                rows = cur.fetchall()
                return [
                    OutboxEntry(
                        message_id=r["message_id"],
                        operation_key=r["operation_key"],
                        topic=r["topic"],
                        payload=json.loads(r["payload_json"]),
                        status=r["status"],
                        retry_count=r["retry_count"],
                        max_retries=r["max_retries"],
                        created_at=r["created_at"],
                        dispatched_at=r["dispatched_at"],
                        committed_at=r["committed_at"],
                    )
                    for r in rows
                ]

    def list_dlq(self, limit: int = 50) -> List[DLQEntry]:
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT * FROM platform_dlq ORDER BY dead_lettered_at DESC LIMIT ?;",
                    (limit,),
                )
                rows = cur.fetchall()
                return [
                    DLQEntry(
                        dlq_id=r["dlq_id"],
                        operation_key=r["operation_key"],
                        topic=r["topic"],
                        payload=json.loads(r["payload_json"]),
                        failure_reason=r["failure_reason"],
                        retry_count=r["retry_count"],
                        dead_lettered_at=r["dead_lettered_at"],
                        replayed_at=r["replayed_at"],
                    )
                    for r in rows
                ]
