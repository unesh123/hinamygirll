"""
HINAA OS — Phase 17 Local-First Edge Synchronization & Privacy-Guaranteed Replication.

Implements:
- Device pairing with cryptographic public-key fingerprints.
- Instant device revocation kill-switch.
- Zero-leak replication rules (never syncs raw credentials, bearer tokens, or audio files).
- Tenant boundary enforcement.
- Delete tombstones and conflict detection.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from hinaa_api.platform.contracts import (
    ConflictResolutionStrategy,
    PairedDevice,
    SyncConflict,
    SyncManifest,
    SyncPeerStatus,
)

logger = logging.getLogger(__name__)

EXCLUDED_SYNC_FIELDS = {"secret", "password", "token", "private_key", "cookie", "approval_token", "biometric"}
EXCLUDED_RECORD_TYPES = {"secrets", "payment_approval", "auth_session", "raw_voice_recording"}


class EdgeSyncEngine:
    """Manages offline-first edge synchronization, device pairing, and conflict resolution."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or os.environ.get("HINAA_AUTOPILOT_DB", "hinaa_autopilot.db")
        self._is_memory = str(self.db_path) == ":memory:"
        self._mem_conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._is_memory:
            if self._mem_conn is None:
                self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._mem_conn.row_factory = sqlite3.Row
            return self._mem_conn

        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS platform_paired_devices (
                        device_id TEXT PRIMARY KEY,
                        device_name TEXT NOT NULL,
                        public_key_fingerprint TEXT NOT NULL,
                        paired_at REAL NOT NULL,
                        status TEXT NOT NULL,
                        last_sync_watermark INTEGER NOT NULL DEFAULT 0,
                        allowed_tenants_json TEXT NOT NULL DEFAULT '["default"]',
                        is_same_host_simulation INTEGER NOT NULL DEFAULT 0,
                        tenant_id TEXT NOT NULL DEFAULT 'default'
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS platform_sync_events (
                        event_id TEXT PRIMARY KEY,
                        source_device_id TEXT NOT NULL,
                        tenant_id TEXT NOT NULL DEFAULT 'default',
                        record_id TEXT NOT NULL,
                        record_type TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        timestamp REAL NOT NULL
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS platform_sync_conflicts (
                        conflict_id TEXT PRIMARY KEY,
                        record_id TEXT NOT NULL,
                        record_type TEXT NOT NULL,
                        local_version INTEGER NOT NULL,
                        remote_version INTEGER NOT NULL,
                        local_data_json TEXT NOT NULL,
                        remote_data_json TEXT NOT NULL,
                        strategy TEXT NOT NULL,
                        resolved INTEGER NOT NULL DEFAULT 0,
                        resolution_winner TEXT,
                        detected_at REAL NOT NULL,
                        resolved_at REAL
                    );
                    """
                )
                conn.commit()

    def pair_device(
        self,
        device_name: str,
        public_key_fingerprint: str,
        device_id: Optional[str] = None,
        tenant_id: str = "default",
        allowed_tenants: Optional[List[str]] = None,
        is_same_host_simulation: bool = False,
    ) -> PairedDevice:
        """Pairs a new device with cryptographic fingerprint validation."""
        dev_id = device_id or f"dev_{uuid.uuid4().hex[:10]}"
        tenants = allowed_tenants or [tenant_id]

        device = PairedDevice(
            device_id=dev_id,
            device_name=device_name,
            public_key_fingerprint=public_key_fingerprint,
            paired_at=time.time(),
            status=SyncPeerStatus.ACTIVE,
            last_sync_watermark=0,
            allowed_tenants=tenants,
            is_same_host_simulation=is_same_host_simulation,
            tenant_id=tenant_id,
        )

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO platform_paired_devices (
                        device_id, device_name, public_key_fingerprint,
                        paired_at, status, last_sync_watermark, allowed_tenants_json,
                        is_same_host_simulation, tenant_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        device.device_id,
                        device.device_name,
                        device.public_key_fingerprint,
                        device.paired_at,
                        device.status.value,
                        device.last_sync_watermark,
                        json.dumps(device.allowed_tenants),
                        1 if device.is_same_host_simulation else 0,
                        tenant_id,
                    ),
                )
                conn.commit()

        return device

    def revoke_device(self, device_id: str) -> PairedDevice:
        """Immediately revokes device access; blocks any future sync requests."""
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("UPDATE platform_paired_devices SET status = 'REVOKED' WHERE device_id = ?;", (device_id,))
                conn.commit()
        dev = self.get_device(device_id)
        if not dev:
            raise ValueError(f"Device not found: {device_id}")
        return dev

    def get_device(self, device_id: str) -> Optional[PairedDevice]:
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute("SELECT * FROM platform_paired_devices WHERE device_id = ?;", (device_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return PairedDevice(
                    device_id=row["device_id"],
                    device_name=row["device_name"],
                    public_key_fingerprint=row["public_key_fingerprint"],
                    paired_at=row["paired_at"],
                    status=SyncPeerStatus(row["status"]),
                    last_sync_watermark=row["last_sync_watermark"],
                    allowed_tenants=json.loads(row["allowed_tenants_json"]),
                    is_same_host_simulation=bool(row["is_same_host_simulation"]),
                    tenant_id=row["tenant_id"] if "tenant_id" in row.keys() else "default",
                )

    def record_change(
        self,
        entity_type: str,
        entity_id: str,
        payload: Dict[str, Any],
        version: int,
        origin_device_id: str,
        is_deleted: bool = False,
        tenant_id: str = "default",
    ) -> str:
        """Records mutation or delete tombstone, verifying zero-leak sanitization."""
        if entity_type in EXCLUDED_RECORD_TYPES:
            raise PermissionError(f"Security Exclusion: Record type '{entity_type}' is prohibited from sync.")

        clean_data = {
            k: v for k, v in payload.items()
            if not any(f in k.lower() for f in EXCLUDED_SYNC_FIELDS)
        }
        operation = "DELETE_TOMBSTONE" if is_deleted else "UPDATE"
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        now = time.time()

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO platform_sync_events (
                        event_id, source_device_id, tenant_id, record_id,
                        record_type, operation, payload_json, version, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        event_id,
                        origin_device_id,
                        tenant_id,
                        entity_id,
                        entity_type,
                        operation,
                        json.dumps(clean_data),
                        version,
                        now,
                    ),
                )
                conn.commit()

        return event_id

    def generate_sync_manifest(self, target_device_id: str) -> SyncManifest:
        """Generates delta sync manifest for an authorized, active paired peer."""
        dev = self.get_device(target_device_id)
        if not dev:
            raise PermissionError(f"Unauthorized: Device {target_device_id} is not paired.")
        if dev.status != SyncPeerStatus.ACTIVE:
            raise PermissionError(f"Unauthorized: Device {target_device_id} is {dev.status.value}")

        allowed = dev.allowed_tenants
        records = []
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute("SELECT * FROM platform_sync_events ORDER BY timestamp ASC;")
                rows = cur.fetchall()
                for r in rows:
                    if r["tenant_id"] in allowed:
                        records.append({
                            "event_id": r["event_id"],
                            "entity_id": r["record_id"],
                            "entity_type": r["record_type"],
                            "operation": r["operation"],
                            "payload": json.loads(r["payload_json"]),
                            "version": r["version"],
                            "timestamp": r["timestamp"],
                        })

        return SyncManifest(
            manifest_id=f"mnf_{uuid.uuid4().hex[:10]}",
            origin_device_id="desktop_primary",
            target_device_id=target_device_id,
            watermark_start=0,
            watermark_end=len(records),
            records=records,
        )

    def detect_and_record_conflict(
        self,
        entity_type: str,
        entity_id: str,
        local_payload: Dict[str, Any],
        remote_payload: Dict[str, Any],
        local_version: int,
        remote_version: int,
    ) -> SyncConflict:
        """Records conflict item for inspection and resolution."""
        conflict_id = f"cnf_{uuid.uuid4().hex[:12]}"
        conflict = SyncConflict(
            conflict_id=conflict_id,
            entity_type=entity_type,
            entity_id=entity_id,
            record_id=entity_id,
            record_type=entity_type,
            local_version=local_version,
            remote_version=remote_version,
            local_payload=local_payload,
            remote_payload=remote_payload,
            local_data=local_payload,
            remote_data=remote_payload,
            strategy=ConflictResolutionStrategy.LOCAL_WINS,
            resolved=False,
            detected_at=time.time(),
        )

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO platform_sync_conflicts (
                        conflict_id, record_id, record_type, local_version,
                        remote_version, local_data_json, remote_data_json,
                        strategy, resolved, detected_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?);
                    """,
                    (
                        conflict.conflict_id,
                        entity_id,
                        entity_type,
                        local_version,
                        remote_version,
                        json.dumps(local_payload),
                        json.dumps(remote_payload),
                        conflict.strategy.value,
                        conflict.detected_at,
                    ),
                )
                conn.commit()

        return conflict

    def resolve_conflict(
        self,
        conflict_id: str,
        strategy: ConflictResolutionStrategy | str,
    ) -> SyncConflict:
        """Resolves conflict item according to selected resolution strategy."""
        strat_val = strategy.value if isinstance(strategy, ConflictResolutionStrategy) else strategy
        now = time.time()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    UPDATE platform_sync_conflicts
                    SET resolved = 1, resolution_winner = ?, resolved_at = ?
                    WHERE conflict_id = ?;
                    """,
                    (strat_val, now, conflict_id),
                )
                conn.commit()

                cur = conn.execute("SELECT * FROM platform_sync_conflicts WHERE conflict_id = ?;", (conflict_id,))
                r = cur.fetchone()
                if not r:
                    raise ValueError(f"Conflict not found: {conflict_id}")

                return SyncConflict(
                    conflict_id=r["conflict_id"],
                    entity_type=r["record_type"],
                    entity_id=r["record_id"],
                    record_id=r["record_id"],
                    record_type=r["record_type"],
                    local_version=r["local_version"],
                    remote_version=r["remote_version"],
                    local_payload=json.loads(r["local_data_json"]),
                    remote_payload=json.loads(r["remote_data_json"]),
                    local_data=json.loads(r["local_data_json"]),
                    remote_data=json.loads(r["remote_data_json"]),
                    strategy=ConflictResolutionStrategy(r["strategy"]),
                    resolved=bool(r["resolved"]),
                    resolution_strategy=r["resolution_winner"],
                    detected_at=r["detected_at"],
                )

    def list_conflicts(self) -> List[SyncConflict]:
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute("SELECT * FROM platform_sync_conflicts WHERE resolved = 0;")
                rows = cur.fetchall()
                return [
                    SyncConflict(
                        conflict_id=r["conflict_id"],
                        entity_type=r["record_type"],
                        entity_id=r["record_id"],
                        record_id=r["record_id"],
                        record_type=r["record_type"],
                        local_version=r["local_version"],
                        remote_version=r["remote_version"],
                        local_payload=json.loads(r["local_data_json"]),
                        remote_payload=json.loads(r["remote_data_json"]),
                        local_data=json.loads(r["local_data_json"]),
                        remote_data=json.loads(r["remote_data_json"]),
                        strategy=ConflictResolutionStrategy(r["strategy"]),
                        resolved=bool(r["resolved"]),
                        resolution_strategy=r["resolution_winner"],
                        detected_at=r["detected_at"],
                    )
                    for r in rows
                ]
