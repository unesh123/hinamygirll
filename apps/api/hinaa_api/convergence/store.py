"""
HINAA OS — Phase 18 Convergence Persistence Store.

Provides thread-safe SQLite WAL storage for:
- UnifiedMission state records and execution histories.
- Typed output artifacts with SHA-256 content hashes.
- Scoped user autonomy contracts and spending limits.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from hinaa_api.convergence.contracts import (
    AutonomyContract,
    MissionStatus,
    TypedArtifact,
    UnifiedMission,
)

logger = logging.getLogger(__name__)


class MissionStore:
    """Manages SQLite WAL persistence for missions, artifacts, and autonomy policies."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or os.environ.get("HINAA_AUTOPILOT_DB", "hinaa_autopilot.db")
        self._is_memory = str(self.db_path) == ":memory:"
        self._mem_conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
        self._init_tables()

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

    def _init_tables(self) -> None:
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS platform_missions (
                        mission_id TEXT PRIMARY KEY,
                        tenant_id TEXT NOT NULL,
                        authenticated_actor TEXT NOT NULL,
                        objective TEXT NOT NULL,
                        run_state TEXT NOT NULL,
                        autonomous_mode TEXT NOT NULL,
                        audit_correlation_id TEXT NOT NULL,
                        mission_json TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS platform_mission_artifacts (
                        artifact_id TEXT PRIMARY KEY,
                        mission_id TEXT NOT NULL,
                        artifact_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        content_digest TEXT NOT NULL,
                        tenant_id TEXT NOT NULL,
                        file_path TEXT,
                        file_size_bytes INTEGER NOT NULL DEFAULT 0,
                        is_verified INTEGER NOT NULL DEFAULT 0,
                        artifact_json TEXT NOT NULL,
                        created_at REAL NOT NULL
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS platform_autonomy_contracts (
                        tenant_id TEXT PRIMARY KEY,
                        contract_json TEXT NOT NULL,
                        updated_at REAL NOT NULL
                    );
                    """
                )
                conn.commit()

    def save_mission(self, mission: UnifiedMission) -> None:
        mission.updated_at = time.time()
        data = mission.model_dump()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO platform_missions (
                        mission_id, tenant_id, authenticated_actor, objective,
                        run_state, autonomous_mode, audit_correlation_id,
                        mission_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        mission.mission_id,
                        mission.tenant_id,
                        mission.authenticated_actor,
                        mission.objective,
                        mission.run_state.value,
                        mission.autonomous_mode.value,
                        mission.audit_correlation_id,
                        json.dumps(data),
                        mission.created_at,
                        mission.updated_at,
                    ),
                )
                conn.commit()

    def get_mission(self, mission_id: str) -> Optional[UnifiedMission]:
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute("SELECT mission_json FROM platform_missions WHERE mission_id = ?;", (mission_id,))
                row = cur.fetchone()
                if not row:
                    return None
                data = json.loads(row["mission_json"])
                return UnifiedMission(**data)

    def list_missions(self, tenant_id: str = "default", limit: int = 50) -> List[UnifiedMission]:
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(
                    "SELECT mission_json FROM platform_missions WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?;",
                    (tenant_id, limit),
                )
                rows = cur.fetchall()
                return [UnifiedMission(**json.loads(r["mission_json"])) for r in rows]

    def save_artifact(self, mission_id: str, artifact: TypedArtifact) -> None:
        data = artifact.model_dump()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO platform_mission_artifacts (
                        artifact_id, mission_id, artifact_type, title,
                        content_digest, tenant_id, file_path, file_size_bytes,
                        is_verified, artifact_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        artifact.artifact_id,
                        mission_id,
                        artifact.artifact_type.value,
                        artifact.title,
                        artifact.content_digest,
                        artifact.tenant_id,
                        artifact.file_path,
                        artifact.file_size_bytes,
                        1 if artifact.is_verified else 0,
                        json.dumps(data),
                        artifact.created_at,
                    ),
                )
                conn.commit()

    def get_artifacts_for_mission(self, mission_id: str) -> List[TypedArtifact]:
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(
                    "SELECT artifact_json FROM platform_mission_artifacts WHERE mission_id = ? ORDER BY created_at ASC;",
                    (mission_id,),
                )
                rows = cur.fetchall()
                return [TypedArtifact(**json.loads(r["artifact_json"])) for r in rows]

    def get_autonomy_contract(self, tenant_id: str = "default") -> AutonomyContract:
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute("SELECT contract_json FROM platform_autonomy_contracts WHERE tenant_id = ?;", (tenant_id,))
                row = cur.fetchone()
                if row:
                    return AutonomyContract(**json.loads(row["contract_json"]))

                # Default safe contract
                contract = AutonomyContract(contract_id=f"autonomy_{tenant_id}", tenant_id=tenant_id)
                conn.execute(
                    "INSERT INTO platform_autonomy_contracts (tenant_id, contract_json, updated_at) VALUES (?, ?, ?);",
                    (tenant_id, json.dumps(contract.model_dump()), time.time()),
                )
                conn.commit()
                return contract

    def update_autonomy_contract(self, contract: AutonomyContract) -> None:
        contract.updated_at = time.time()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO platform_autonomy_contracts (tenant_id, contract_json, updated_at) VALUES (?, ?, ?);",
                    (contract.tenant_id, json.dumps(contract.model_dump()), contract.updated_at),
                )
                conn.commit()
