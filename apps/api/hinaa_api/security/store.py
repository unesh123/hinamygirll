"""
HINAA OS — Phase 15 Security Persistence Store
SQLite WAL-backed persistent storage for tamper-evident audit trails,
cryptographic approval ceremony tokens, revocation ledgers, and secret metadata.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from hinaa_api.security.contracts import (
    ApprovalCeremonyToken,
    AuditEvent,
    KeystoreType,
)

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(os.environ.get("HINAA_AUTOPILOT_DB", "hinaa_autopilot.db"))


class SecurityStore:
    """Thread-safe SQLite store for security audit logs, approval tokens, and revocations."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            check_same_thread=False,
            isolation_level="DEFERRED",
        )
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            with self._get_connection() as conn:
                # 1. Audit events table with hash-chaining support
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_events (
                        sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT UNIQUE NOT NULL,
                        timestamp REAL NOT NULL,
                        tenant_id TEXT NOT NULL,
                        subject_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        resource TEXT NOT NULL,
                        decision TEXT NOT NULL,
                        reason_code TEXT NOT NULL,
                        prev_hash TEXT NOT NULL,
                        event_hash TEXT NOT NULL,
                        signature TEXT NOT NULL
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_events(tenant_id, timestamp);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_event_id ON audit_events(event_id);")

                # 2. Cryptographic approval ceremonies table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS approval_tokens (
                        token_id TEXT PRIMARY KEY,
                        tenant_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        parameters_digest TEXT NOT NULL,
                        nonce TEXT UNIQUE NOT NULL,
                        issued_at REAL NOT NULL,
                        expires_at REAL NOT NULL,
                        consumed_at REAL,
                        amount_paisa INTEGER,
                        currency TEXT DEFAULT 'NPR',
                        approved_by TEXT,
                        signature TEXT NOT NULL,
                        status TEXT NOT NULL
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_approval_nonce ON approval_tokens(nonce);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_approval_tenant ON approval_tokens(tenant_id);")

                # 3. Dynamic revocation ledger
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS revocation_ledger (
                        revocation_id TEXT PRIMARY KEY,
                        target_type TEXT NOT NULL, -- 'user', 'role', 'agent', 'token', 'session'
                        target_id TEXT NOT NULL,
                        tenant_id TEXT NOT NULL,
                        revoked_at REAL NOT NULL,
                        reason TEXT NOT NULL,
                        revoked_by TEXT NOT NULL
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_revocation_target ON revocation_ledger(target_type, target_id);")

                # 4. Secret metadata table (zero raw secret values stored here)
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS secret_metadata (
                        secret_name TEXT PRIMARY KEY,
                        keystore_type TEXT NOT NULL,
                        is_hardware_backed INTEGER NOT NULL,
                        last_rotated_at REAL NOT NULL,
                        expires_at REAL
                    );
                    """
                )
                conn.commit()

    # --- Audit Trail Methods ---

    def get_latest_audit_event(self) -> Optional[AuditEvent]:
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT * FROM audit_events ORDER BY sequence_id DESC LIMIT 1;")
                row = cur.fetchone()
                if not row:
                    return None
                return AuditEvent(**dict(row))

    def append_audit_event(
        self,
        event_id: str,
        timestamp: float,
        tenant_id: str,
        subject_id: str,
        action: str,
        resource: str,
        decision: str,
        reason_code: str,
        prev_hash: str,
        event_hash: str,
        signature: str,
    ) -> AuditEvent:
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO audit_events (
                        event_id, timestamp, tenant_id, subject_id,
                        action, resource, decision, reason_code,
                        prev_hash, event_hash, signature
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id, timestamp, tenant_id, subject_id,
                        action, resource, decision, reason_code,
                        prev_hash, event_hash, signature,
                    ),
                )
                seq_id = cur.lastrowid
                conn.commit()
                return AuditEvent(
                    sequence_id=seq_id,
                    event_id=event_id,
                    timestamp=timestamp,
                    tenant_id=tenant_id,
                    subject_id=subject_id,
                    action=action,
                    resource=resource,
                    decision=decision,
                    reason_code=reason_code,
                    prev_hash=prev_hash,
                    event_hash=event_hash,
                    signature=signature,
                )

    def list_audit_events(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEvent]:
        with self._lock:
            with self._get_connection() as conn:
                if tenant_id:
                    cur = conn.execute(
                        "SELECT * FROM audit_events WHERE tenant_id = ? ORDER BY sequence_id ASC LIMIT ? OFFSET ?;",
                        (tenant_id, limit, offset),
                    )
                else:
                    cur = conn.execute(
                        "SELECT * FROM audit_events ORDER BY sequence_id ASC LIMIT ? OFFSET ?;",
                        (limit, offset),
                    )
                return [AuditEvent(**dict(r)) for r in cur.fetchall()]

    def get_all_audit_events_ordered(self) -> List[AuditEvent]:
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT * FROM audit_events ORDER BY sequence_id ASC;")
                return [AuditEvent(**dict(r)) for r in cur.fetchall()]

    # --- Approval Ceremony Methods ---

    def save_approval_token(self, token: ApprovalCeremonyToken) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO approval_tokens (
                        token_id, tenant_id, action, parameters_digest, nonce,
                        issued_at, expires_at, consumed_at, amount_paisa, currency,
                        approved_by, signature, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(token_id) DO UPDATE SET
                        consumed_at = excluded.consumed_at,
                        approved_by = excluded.approved_by,
                        status = excluded.status;
                    """,
                    (
                        token.token_id,
                        token.tenant_id,
                        token.action,
                        token.parameters_digest,
                        token.nonce,
                        token.issued_at,
                        token.expires_at,
                        token.consumed_at,
                        token.amount_paisa,
                        token.currency,
                        token.approved_by,
                        token.signature,
                        token.status,
                    ),
                )
                conn.commit()

    def get_approval_token(self, token_id: str) -> Optional[ApprovalCeremonyToken]:
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT * FROM approval_tokens WHERE token_id = ?;", (token_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return ApprovalCeremonyToken(**dict(row))

    def consume_approval_token(self, token_id: str, nonce: str) -> bool:
        """Atomically marks a token as consumed; fails if already consumed or expired."""
        with self._lock:
            with self._get_connection() as conn:
                now = time.time()
                cur = conn.execute(
                    """
                    UPDATE approval_tokens
                    SET status = 'CONSUMED', consumed_at = ?
                    WHERE token_id = ? AND nonce = ? AND status = 'APPROVED' AND consumed_at IS NULL AND expires_at > ?;
                    """,
                    (now, token_id, nonce, now),
                )
                conn.commit()
                return cur.rowcount > 0

    # --- Revocation Methods ---

    def add_revocation(
        self,
        revocation_id: str,
        target_type: str,
        target_id: str,
        tenant_id: str,
        reason: str,
        revoked_by: str,
    ) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO revocation_ledger (
                        revocation_id, target_type, target_id, tenant_id,
                        revoked_at, reason, revoked_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        revocation_id,
                        target_type,
                        target_id,
                        tenant_id,
                        time.time(),
                        reason,
                        revoked_by,
                    ),
                )
                conn.commit()

    def is_revoked(self, target_type: str, target_id: str) -> bool:
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT 1 FROM revocation_ledger WHERE target_type = ? AND target_id = ? LIMIT 1;",
                    (target_type, target_id),
                )
                return cur.fetchone() is not None

    def list_revocations(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            with self._get_connection() as conn:
                if tenant_id:
                    cur = conn.execute("SELECT * FROM revocation_ledger WHERE tenant_id = ? ORDER BY revoked_at DESC;", (tenant_id,))
                else:
                    cur = conn.execute("SELECT * FROM revocation_ledger ORDER BY revoked_at DESC;")
                return [dict(r) for r in cur.fetchall()]


_default_security_store: Optional[SecurityStore] = None


def get_security_store(db_path: Optional[Path] = None) -> SecurityStore:
    global _default_security_store
    if db_path is not None:
        return SecurityStore(db_path)
    if _default_security_store is None:
        _default_security_store = SecurityStore()
    return _default_security_store
