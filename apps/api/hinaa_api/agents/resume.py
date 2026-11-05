"""
HINAA OS — Phase 11 Durable State Store, Leases & Restart Recovery
Manages task checkpoints in SQLite, optimistic Compare-And-Swap (CAS) worker leases,
and idempotent crash recovery.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    BudgetLedger,
    TaskNode,
    TaskSpec,
    TaskStatus,
    ToolReceipt,
    _now_iso,
)

logger = logging.getLogger("hinaa.agents.resume")


class TaskStore:
    """Thread-safe SQLite store for TaskSpec, TaskNode, and worker leases."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        if db_path is None:
            try:
                from ..config import DATA_DIR
                self.db_path = DATA_DIR / "hinaa_agent_tasks.db"
            except Exception:
                base = Path(__file__).resolve().parents[4]
                self.db_path = base / "apps" / "api" / "data" / "hinaa_agent_tasks.db"
        else:
            self.db_path = Path(db_path)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if str(self.db_path) == ":memory:":
            if not hasattr(self, "_mem_conn") or self._mem_conn is None:
                self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False, isolation_level=None)
                self._mem_conn.row_factory = sqlite3.Row
            return self._mem_conn
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    instruction_hash TEXT,
                    language TEXT NOT NULL,
                    status TEXT NOT NULL,
                    budget_json TEXT NOT NULL,
                    active_node_id TEXT,
                    artifacts_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    version INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_nodes (
                    node_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    specialist_role TEXT NOT NULL,
                    dependencies_json TEXT NOT NULL,
                    allowed_tools_json TEXT NOT NULL,
                    permission_tier TEXT NOT NULL,
                    input_data_json TEXT NOT NULL,
                    output_schema_json TEXT,
                    expected_postcondition TEXT,
                    status TEXT NOT NULL,
                    result_data_json TEXT,
                    error TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    lease_owner TEXT,
                    lease_expires_at REAL,
                    start_time REAL,
                    end_time REAL,
                    receipts_json TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_task ON task_nodes(task_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")

    def save_task(self, task: TaskSpec) -> None:
        """Atomically persist or update a complete TaskSpec and its nodes."""
        with self._lock, self._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """
                    INSERT INTO tasks (
                        task_id, tenant_id, user_id, goal, instruction_hash,
                        language, status, budget_json, active_node_id,
                        artifacts_json, created_at, updated_at, completed_at, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(task_id) DO UPDATE SET
                        status = excluded.status,
                        budget_json = excluded.budget_json,
                        active_node_id = excluded.active_node_id,
                        artifacts_json = excluded.artifacts_json,
                        updated_at = excluded.updated_at,
                        completed_at = excluded.completed_at,
                        version = version + 1
                    """,
                    (
                        task.task_id,
                        task.tenant_id,
                        task.user_id,
                        task.goal,
                        task.instruction_hash,
                        task.language,
                        task.status.value if hasattr(task.status, "value") else str(task.status),
                        task.budget.model_dump_json(),
                        task.active_node_id,
                        json.dumps(task.artifacts, ensure_ascii=False),
                        task.created_at,
                        _now_iso(),
                        task.completed_at,
                        task.version,
                    ),
                )

                for node in task.nodes:
                    self._upsert_node(conn, node)

                conn.execute("COMMIT")
            except Exception as e:
                conn.execute("ROLLBACK")
                raise e

    def _upsert_node(self, conn: sqlite3.Connection, node: TaskNode) -> None:
        receipts_data = [r.model_dump() for r in node.receipts]
        conn.execute(
            """
            INSERT INTO task_nodes (
                node_id, task_id, title, specialist_role, dependencies_json,
                allowed_tools_json, permission_tier, input_data_json,
                output_schema_json, expected_postcondition, status,
                result_data_json, error, attempts, max_attempts,
                lease_owner, lease_expires_at, start_time, end_time, receipts_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(node_id) DO UPDATE SET
                status = excluded.status,
                result_data_json = excluded.result_data_json,
                error = excluded.error,
                attempts = excluded.attempts,
                lease_owner = excluded.lease_owner,
                lease_expires_at = excluded.lease_expires_at,
                start_time = excluded.start_time,
                end_time = excluded.end_time,
                receipts_json = excluded.receipts_json
            """,
            (
                node.node_id,
                node.task_id,
                node.title,
                node.specialist_role.value if hasattr(node.specialist_role, "value") else str(node.specialist_role),
                json.dumps(node.dependencies),
                json.dumps(node.allowed_tools),
                node.permission_tier.value if hasattr(node.permission_tier, "value") else str(node.permission_tier),
                json.dumps(node.input_data, ensure_ascii=False),
                json.dumps(node.output_schema) if node.output_schema else None,
                node.expected_postcondition,
                node.status.value if hasattr(node.status, "value") else str(node.status),
                json.dumps(node.result_data, ensure_ascii=False) if node.result_data else None,
                node.error,
                node.attempts,
                node.max_attempts,
                node.lease_owner,
                node.lease_expires_at,
                node.start_time,
                node.end_time,
                json.dumps(receipts_data, ensure_ascii=False),
            ),
        )

    def get_task(self, task_id: str) -> Optional[TaskSpec]:
        """Fetch task and all associated nodes."""
        with self._lock, self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = cur.fetchone()
            if not row:
                return None

            node_cur = conn.execute("SELECT * FROM task_nodes WHERE task_id = ?", (task_id,))
            nodes: List[TaskNode] = []
            for n_row in node_cur.fetchall():
                receipts_raw = json.loads(n_row["receipts_json"])
                receipts = [ToolReceipt(**r) for r in receipts_raw]
                node = TaskNode(
                    node_id=n_row["node_id"],
                    task_id=n_row["task_id"],
                    title=n_row["title"],
                    specialist_role=n_row["specialist_role"],
                    dependencies=json.loads(n_row["dependencies_json"]),
                    allowed_tools=json.loads(n_row["allowed_tools_json"]),
                    permission_tier=n_row["permission_tier"],
                    input_data=json.loads(n_row["input_data_json"]),
                    output_schema=json.loads(n_row["output_schema_json"]) if n_row["output_schema_json"] else None,
                    expected_postcondition=n_row["expected_postcondition"],
                    status=n_row["status"],
                    result_data=json.loads(n_row["result_data_json"]) if n_row["result_data_json"] else None,
                    error=n_row["error"],
                    attempts=n_row["attempts"],
                    max_attempts=n_row["max_attempts"],
                    lease_owner=n_row["lease_owner"],
                    lease_expires_at=n_row["lease_expires_at"],
                    start_time=n_row["start_time"],
                    end_time=n_row["end_time"],
                    receipts=receipts,
                )
                nodes.append(node)

            budget_data = json.loads(row["budget_json"])
            return TaskSpec(
                task_id=row["task_id"],
                tenant_id=row["tenant_id"],
                user_id=row["user_id"],
                goal=row["goal"],
                instruction_hash=row["instruction_hash"] or "",
                language=row["language"],
                status=row["status"],
                budget=BudgetLedger(**budget_data),
                nodes=nodes,
                active_node_id=row["active_node_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                completed_at=row["completed_at"],
                version=row["version"],
                artifacts=json.loads(row["artifacts_json"]),
            )

    def claim_node_lease(
        self,
        node_id: str,
        worker_id: str,
        lease_duration_sec: float = 60.0,
    ) -> bool:
        """
        Optimistic CAS (Compare-and-Swap) worker lease acquisition.
        Succeeds only if unleased or lease has expired.
        """
        now = time.time()
        new_expires = now + lease_duration_sec
        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE task_nodes
                SET lease_owner = ?, lease_expires_at = ?, status = 'RUNNING'
                WHERE node_id = ?
                  AND (lease_owner IS NULL OR lease_expires_at < ? OR lease_owner = ?)
                  AND status IN ('READY', 'RETRYING', 'RECOVERING')
                """,
                (worker_id, new_expires, node_id, now, worker_id),
            )
            return cur.rowcount > 0

    def release_node_lease(self, node_id: str, worker_id: str, new_status: TaskStatus) -> bool:
        """Release lease upon completion or failure."""
        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE task_nodes
                SET lease_owner = NULL, lease_expires_at = NULL, status = ?
                WHERE node_id = ? AND lease_owner = ?
                """,
                (new_status.value if hasattr(new_status, "value") else str(new_status), node_id, worker_id),
            )
            return cur.rowcount > 0

    def find_recoverable_tasks(self) -> List[str]:
        """Find task_ids that were interrupted by crash or restart."""
        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                """
                SELECT DISTINCT task_id FROM tasks
                WHERE status IN ('RUNNING', 'PLANNING', 'WAITING_APPROVAL', 'RETRYING', 'RECOVERING')
                """
            )
            return [r[0] for r in cur.fetchall()]

    def reset_expired_leases(self) -> int:
        """Reset nodes whose worker lease has expired back to READY / RECOVERING."""
        now = time.time()
        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE task_nodes
                SET lease_owner = NULL, lease_expires_at = NULL, status = 'RECOVERING'
                WHERE status = 'RUNNING' AND lease_expires_at < ?
                """,
                (now,),
            )
            return cur.rowcount
