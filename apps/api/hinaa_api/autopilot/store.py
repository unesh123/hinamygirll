"""
HINAA OS — Phase 13: Durable SQLite WAL Autopilot Storage Engine
Provides transactional persistence for schedules, jobs, attempts, leases, permissions, notifications, and events.
Features atomic Compare-and-Swap (CAS) claiming, fencing tokens, stale worker rejection, and crash recovery.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3

from ..persistence import sqlcompat
import time
from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    AutopilotEvent,
    Job,
    JobAttempt,
    JobStatus,
    Lease,
    MisfirePolicy,
    Notification,
    PermissionGrant,
    PermissionTier,
    Schedule,
    ScheduleType,
    SeverityLevel,
    TaskTemplate,
)

logger = logging.getLogger(__name__)


class StaleFencingTokenError(Exception):
    """Raised when an attempt is made to commit work with an expired or superseded fencing token."""
    pass


class AutopilotStore:
    def __init__(self, db_path: str = "hinaa_autopilot.db"):
        self.db_path = db_path
        self._pg = sqlcompat.pg_target(db_path, is_default=db_path == "hinaa_autopilot.db")
        self._mem_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        if self._pg:
            return sqlcompat.connect_pg(self._pg)
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            with conn:
                # 1. Schedules Table
                conn.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    schedule_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    schedule_type TEXT NOT NULL,
                    task_template_json TEXT NOT NULL,
                    cron_expr TEXT,
                    interval_seconds INTEGER,
                    timezone TEXT NOT NULL DEFAULT 'Asia/Kathmandu',
                    start_time_utc REAL NOT NULL,
                    end_time_utc REAL,
                    is_paused INTEGER NOT NULL DEFAULT 0,
                    max_runs INTEGER,
                    run_count INTEGER NOT NULL DEFAULT 0,
                    misfire_policy TEXT NOT NULL DEFAULT 'COALESCE',
                    idempotency_key TEXT,
                    created_at_utc REAL NOT NULL,
                    updated_at_utc REAL NOT NULL,
                    next_fire_time_utc REAL,
                    metadata_json TEXT
                )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sched_tenant ON schedules(tenant_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sched_next_fire ON schedules(next_fire_time_utc, is_paused)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sched_idempotency ON schedules(tenant_id, idempotency_key)")

                # 2. Jobs Table
                conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    schedule_id TEXT,
                    tenant_id TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    current_lease_owner TEXT,
                    lease_expires_at_utc REAL,
                    fencing_token INTEGER NOT NULL DEFAULT 0,
                    last_heartbeat_at_utc REAL,
                    scheduled_for_utc REAL NOT NULL,
                    started_at_utc REAL,
                    completed_at_utc REAL,
                    error_message TEXT,
                    idempotency_key TEXT,
                    ancestry TEXT NOT NULL,
                    budget_tokens INTEGER NOT NULL,
                    consumed_tokens INTEGER NOT NULL DEFAULT 0,
                    budget_paisa INTEGER NOT NULL,
                    consumed_paisa INTEGER NOT NULL DEFAULT 0,
                    artifacts_json TEXT,
                    trace_id TEXT NOT NULL,
                    metadata_json TEXT
                )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, scheduled_for_utc)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_schedule ON jobs(schedule_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_idempotency ON jobs(tenant_id, idempotency_key)")

                # 3. Job Attempts Table
                conn.execute("""
                CREATE TABLE IF NOT EXISTS job_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    worker_id TEXT NOT NULL,
                    started_at_utc REAL NOT NULL,
                    ended_at_utc REAL,
                    status TEXT NOT NULL,
                    error_details TEXT,
                    exit_code INTEGER,
                    diagnostics_json TEXT,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
                )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_attempts_job ON job_attempts(job_id)")

                # 4. Leases Table
                conn.execute("""
                CREATE TABLE IF NOT EXISTS leases (
                    lease_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL UNIQUE,
                    worker_id TEXT NOT NULL,
                    fencing_token INTEGER NOT NULL,
                    acquired_at_utc REAL NOT NULL,
                    expires_at_utc REAL NOT NULL,
                    renewed_at_utc REAL NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
                )
                """)

                # 5. Permission Grants Table
                conn.execute("""
                CREATE TABLE IF NOT EXISTS permission_grants (
                    grant_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    tier TEXT NOT NULL,
                    allowed_tools_json TEXT NOT NULL,
                    allowed_domains_json TEXT,
                    repo_whitelist_json TEXT,
                    max_budget_paisa INTEGER NOT NULL DEFAULT 50000,
                    expires_at_utc REAL,
                    is_revoked INTEGER NOT NULL DEFAULT 0,
                    created_at_utc REAL NOT NULL
                )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_grants_tenant ON permission_grants(tenant_id, owner_user_id)")

                # 6. Notifications Table
                conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    job_id TEXT,
                    schedule_id TEXT,
                    severity TEXT NOT NULL DEFAULT 'INFO',
                    is_read INTEGER NOT NULL DEFAULT 0,
                    created_at_utc REAL NOT NULL,
                    idempotency_key TEXT,
                    metadata_json TEXT
                )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_notifs_user ON notifications(tenant_id, user_id, is_read)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_notifs_idemp ON notifications(tenant_id, idempotency_key)")

                # 7. Autopilot Events Table (Append-only Monotonic Log)
                conn.execute("""
                CREATE TABLE IF NOT EXISTS autopilot_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    tenant_id TEXT NOT NULL,
                    job_id TEXT,
                    schedule_id TEXT,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    timestamp_utc REAL NOT NULL
                )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant_seq ON autopilot_events(tenant_id, sequence)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_events_job ON autopilot_events(job_id)")
        finally:
            if self._mem_conn is None:
                conn.close()

    # -------------------------------------------------------------------------
    # SCHEDULES
    # -------------------------------------------------------------------------
    def save_schedule(self, schedule: Schedule) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                INSERT INTO schedules (
                    schedule_id, tenant_id, owner_user_id, name, description,
                    schedule_type, task_template_json, cron_expr, interval_seconds,
                    timezone, start_time_utc, end_time_utc, is_paused, max_runs,
                    run_count, misfire_policy, idempotency_key, created_at_utc,
                    updated_at_utc, next_fire_time_utc, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(schedule_id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    task_template_json = excluded.task_template_json,
                    cron_expr = excluded.cron_expr,
                    interval_seconds = excluded.interval_seconds,
                    timezone = excluded.timezone,
                    end_time_utc = excluded.end_time_utc,
                    is_paused = excluded.is_paused,
                    max_runs = excluded.max_runs,
                    run_count = excluded.run_count,
                    misfire_policy = excluded.misfire_policy,
                    updated_at_utc = excluded.updated_at_utc,
                    next_fire_time_utc = excluded.next_fire_time_utc,
                    metadata_json = excluded.metadata_json
                """, (
                    schedule.schedule_id,
                    schedule.tenant_id,
                    schedule.owner_user_id,
                    schedule.name,
                    schedule.description,
                    schedule.schedule_type.value,
                    json.dumps(schedule.task_template.to_dict()),
                    schedule.cron_expr,
                    schedule.interval_seconds,
                    schedule.timezone,
                    schedule.start_time_utc,
                    schedule.end_time_utc,
                    1 if schedule.is_paused else 0,
                    schedule.max_runs,
                    schedule.run_count,
                    schedule.misfire_policy.value,
                    schedule.idempotency_key,
                    schedule.created_at_utc,
                    schedule.updated_at_utc,
                    schedule.next_fire_time_utc,
                    json.dumps(schedule.metadata),
                ))
        finally:
            if self._mem_conn is None:
                conn.close()

    def get_schedule(self, schedule_id: str) -> Optional[Schedule]:
        conn = self._get_connection()
        try:
            cur = conn.execute("SELECT * FROM schedules WHERE schedule_id = ?", (schedule_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_schedule(row)
        finally:
            if self._mem_conn is None:
                conn.close()

    def get_schedule_by_idempotency_key(self, tenant_id: str, idempotency_key: str) -> Optional[Schedule]:
        if not idempotency_key:
            return None
        conn = self._get_connection()
        try:
            cur = conn.execute(
                "SELECT * FROM schedules WHERE tenant_id = ? AND idempotency_key = ?",
                (tenant_id, idempotency_key),
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_schedule(row)
        finally:
            if self._mem_conn is None:
                conn.close()

    def list_schedules(self, tenant_id: str, include_paused: bool = True) -> List[Schedule]:
        conn = self._get_connection()
        try:
            if include_paused:
                cur = conn.execute("SELECT * FROM schedules WHERE tenant_id = ? ORDER BY created_at_utc DESC", (tenant_id,))
            else:
                cur = conn.execute("SELECT * FROM schedules WHERE tenant_id = ? AND is_paused = 0 ORDER BY created_at_utc DESC", (tenant_id,))
            return [self._row_to_schedule(r) for r in cur.fetchall()]
        finally:
            if self._mem_conn is None:
                conn.close()

    def list_due_schedules(self, now_utc: float) -> List[Schedule]:
        conn = self._get_connection()
        try:
            cur = conn.execute(
                "SELECT * FROM schedules WHERE is_paused = 0 AND next_fire_time_utc IS NOT NULL AND next_fire_time_utc <= ? ORDER BY next_fire_time_utc ASC",
                (now_utc,),
            )
            return [self._row_to_schedule(r) for r in cur.fetchall()]
        finally:
            if self._mem_conn is None:
                conn.close()

    def delete_schedule(self, schedule_id: str) -> bool:
        conn = self._get_connection()
        try:
            with conn:
                cur = conn.execute("DELETE FROM schedules WHERE schedule_id = ?", (schedule_id,))
                return cur.rowcount > 0
        finally:
            if self._mem_conn is None:
                conn.close()

    def _row_to_schedule(self, row: sqlite3.Row) -> Schedule:
        template_dict = json.loads(row["task_template_json"])
        template = TaskTemplate.from_dict(template_dict)
        meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
        return Schedule(
            schedule_id=row["schedule_id"],
            tenant_id=row["tenant_id"],
            owner_user_id=row["owner_user_id"],
            name=row["name"],
            description=row["description"] or "",
            schedule_type=ScheduleType(row["schedule_type"]),
            task_template=template,
            cron_expr=row["cron_expr"],
            interval_seconds=row["interval_seconds"],
            timezone=row["timezone"],
            start_time_utc=row["start_time_utc"],
            end_time_utc=row["end_time_utc"],
            is_paused=bool(row["is_paused"]),
            max_runs=row["max_runs"],
            run_count=row["run_count"],
            misfire_policy=MisfirePolicy(row["misfire_policy"]),
            idempotency_key=row["idempotency_key"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
            next_fire_time_utc=row["next_fire_time_utc"],
            metadata=meta,
        )

    # -------------------------------------------------------------------------
    # JOBS & CAS LEASING
    # -------------------------------------------------------------------------
    def save_job(self, job: Job) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                INSERT INTO jobs (
                    job_id, schedule_id, tenant_id, owner_user_id, task_id,
                    status, attempt_count, max_attempts, current_lease_owner,
                    lease_expires_at_utc, fencing_token, last_heartbeat_at_utc,
                    scheduled_for_utc, started_at_utc, completed_at_utc,
                    error_message, idempotency_key, ancestry, budget_tokens,
                    consumed_tokens, budget_paisa, consumed_paisa, artifacts_json,
                    trace_id, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status = excluded.status,
                    attempt_count = excluded.attempt_count,
                    max_attempts = excluded.max_attempts,
                    current_lease_owner = excluded.current_lease_owner,
                    lease_expires_at_utc = excluded.lease_expires_at_utc,
                    fencing_token = excluded.fencing_token,
                    last_heartbeat_at_utc = excluded.last_heartbeat_at_utc,
                    scheduled_for_utc = excluded.scheduled_for_utc,
                    started_at_utc = excluded.started_at_utc,
                    completed_at_utc = excluded.completed_at_utc,
                    error_message = excluded.error_message,
                    consumed_tokens = excluded.consumed_tokens,
                    consumed_paisa = excluded.consumed_paisa,
                    artifacts_json = excluded.artifacts_json,
                    metadata_json = excluded.metadata_json
                """, (
                    job.job_id,
                    job.schedule_id,
                    job.tenant_id,
                    job.owner_user_id,
                    job.task_id,
                    job.status.value,
                    job.attempt_count,
                    job.max_attempts,
                    job.current_lease_owner,
                    job.lease_expires_at_utc,
                    job.fencing_token,
                    job.last_heartbeat_at_utc,
                    job.scheduled_for_utc,
                    job.started_at_utc,
                    job.completed_at_utc,
                    job.error_message,
                    job.idempotency_key,
                    job.ancestry,
                    job.budget_tokens,
                    job.consumed_tokens,
                    job.budget_paisa,
                    job.consumed_paisa,
                    json.dumps(job.artifacts),
                    job.trace_id,
                    json.dumps(job.metadata),
                ))
        finally:
            if self._mem_conn is None:
                conn.close()

    def get_job(self, job_id: str) -> Optional[Job]:
        conn = self._get_connection()
        try:
            cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_job(row)
        finally:
            if self._mem_conn is None:
                conn.close()

    def get_job_by_idempotency_key(self, tenant_id: str, idempotency_key: str) -> Optional[Job]:
        if not idempotency_key:
            return None
        conn = self._get_connection()
        try:
            cur = conn.execute(
                "SELECT * FROM jobs WHERE tenant_id = ? AND idempotency_key = ?",
                (tenant_id, idempotency_key),
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_job(row)
        finally:
            if self._mem_conn is None:
                conn.close()

    def list_jobs(self, tenant_id: str, limit: int = 100, status: Optional[JobStatus] = None) -> List[Job]:
        conn = self._get_connection()
        try:
            if status:
                cur = conn.execute(
                    "SELECT * FROM jobs WHERE tenant_id = ? AND status = ? ORDER BY scheduled_for_utc DESC LIMIT ?",
                    (tenant_id, status.value, limit),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM jobs WHERE tenant_id = ? ORDER BY scheduled_for_utc DESC LIMIT ?",
                    (tenant_id, limit),
                )
            return [self._row_to_job(r) for r in cur.fetchall()]
        finally:
            if self._mem_conn is None:
                conn.close()

    def claim_job_atomic(
        self,
        job_id: str,
        worker_id: str,
        lease_duration_seconds: float = 30.0,
    ) -> Optional[Job]:
        """
        Atomic Compare-and-Swap claim with fencing token increment.
        Ensures concurrent workers cannot claim the same job.
        """
        now = time.time()
        expires = now + lease_duration_seconds
        conn = self._get_connection()
        try:
            with conn:
                # 1. Atomic update of jobs table
                cur = conn.execute("""
                UPDATE jobs
                SET status = ?,
                    current_lease_owner = ?,
                    lease_expires_at_utc = ?,
                    fencing_token = fencing_token + 1,
                    last_heartbeat_at_utc = ?,
                    started_at_utc = COALESCE(started_at_utc, ?)
                WHERE job_id = ? AND status IN (?, ?, ?)
                """, (
                    JobStatus.CLAIMED.value,
                    worker_id,
                    expires,
                    now,
                    now,
                    job_id,
                    JobStatus.READY.value,
                    JobStatus.SCHEDULED.value,
                    JobStatus.RETRY_PENDING.value,
                ))

                if cur.rowcount == 0:
                    return None

                # 2. Retrieve updated job
                cur_job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
                row = cur_job.fetchone()
                job = self._row_to_job(row)

                # 3. Insert or replace into leases table
                conn.execute("""
                INSERT INTO leases (lease_id, job_id, worker_id, fencing_token, acquired_at_utc, expires_at_utc, renewed_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    worker_id = excluded.worker_id,
                    fencing_token = excluded.fencing_token,
                    acquired_at_utc = excluded.acquired_at_utc,
                    expires_at_utc = excluded.expires_at_utc,
                    renewed_at_utc = excluded.renewed_at_utc
                """, (
                    f"lease-{job_id}",
                    job_id,
                    worker_id,
                    job.fencing_token,
                    now,
                    expires,
                    now,
                ))

                return job
        finally:
            if self._mem_conn is None:
                conn.close()

    def renew_lease(self, job_id: str, worker_id: str, fencing_token: int, extend_seconds: float = 30.0) -> bool:
        now = time.time()
        expires = now + extend_seconds
        conn = self._get_connection()
        try:
            with conn:
                cur = conn.execute("""
                UPDATE jobs
                SET lease_expires_at_utc = ?, last_heartbeat_at_utc = ?
                WHERE job_id = ? AND current_lease_owner = ? AND fencing_token = ? AND status IN (?, ?)
                """, (
                    expires,
                    now,
                    job_id,
                    worker_id,
                    fencing_token,
                    JobStatus.CLAIMED.value,
                    JobStatus.RUNNING.value,
                ))
                if cur.rowcount == 0:
                    return False
                conn.execute("""
                UPDATE leases
                SET expires_at_utc = ?, renewed_at_utc = ?
                WHERE job_id = ? AND worker_id = ? AND fencing_token = ?
                """, (expires, now, job_id, worker_id, fencing_token))
                return True
        finally:
            if self._mem_conn is None:
                conn.close()

    def commit_job_terminal_status(
        self,
        job_id: str,
        fencing_token: int,
        status: JobStatus,
        error_message: Optional[str] = None,
        artifacts: Optional[List[Dict[str, Any]]] = None,
        consumed_tokens: int = 0,
        consumed_paisa: int = 0,
    ) -> None:
        """
        Commits final job outcome verified against the active fencing token.
        Raises StaleFencingTokenError if a newer worker has taken over.
        """
        now = time.time()
        conn = self._get_connection()
        try:
            with conn:
                cur = conn.execute("""
                UPDATE jobs
                SET status = ?,
                    completed_at_utc = ?,
                    error_message = ?,
                    artifacts_json = COALESCE(?, artifacts_json),
                    consumed_tokens = consumed_tokens + ?,
                    consumed_paisa = consumed_paisa + ?,
                    current_lease_owner = NULL,
                    lease_expires_at_utc = NULL
                WHERE job_id = ? AND fencing_token = ?
                """, (
                    status.value,
                    now,
                    error_message,
                    json.dumps(artifacts) if artifacts is not None else None,
                    consumed_tokens,
                    consumed_paisa,
                    job_id,
                    fencing_token,
                ))

                if cur.rowcount == 0:
                    raise StaleFencingTokenError(
                        f"Commit rejected: worker held stale fencing token {fencing_token} for job {job_id}"
                    )

                # Clean up lease
                conn.execute("DELETE FROM leases WHERE job_id = ?", (job_id,))
        finally:
            if self._mem_conn is None:
                conn.close()

    def record_job_attempt(self, attempt: JobAttempt) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                INSERT INTO job_attempts (
                    attempt_id, job_id, attempt_number, worker_id, started_at_utc,
                    ended_at_utc, status, error_details, exit_code, diagnostics_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(attempt_id) DO UPDATE SET
                    ended_at_utc = excluded.ended_at_utc,
                    status = excluded.status,
                    error_details = excluded.error_details,
                    exit_code = excluded.exit_code,
                    diagnostics_json = excluded.diagnostics_json
                """, (
                    attempt.attempt_id,
                    attempt.job_id,
                    attempt.attempt_number,
                    attempt.worker_id,
                    attempt.started_at_utc,
                    attempt.ended_at_utc,
                    attempt.status.value,
                    attempt.error_details,
                    attempt.exit_code,
                    json.dumps(attempt.diagnostics),
                ))
        finally:
            if self._mem_conn is None:
                conn.close()

    def list_job_attempts(self, job_id: str) -> List[JobAttempt]:
        conn = self._get_connection()
        try:
            cur = conn.execute("SELECT * FROM job_attempts WHERE job_id = ? ORDER BY attempt_number ASC", (job_id,))
            attempts = []
            for r in cur.fetchall():
                diag = json.loads(r["diagnostics_json"]) if r["diagnostics_json"] else {}
                attempts.append(JobAttempt(
                    attempt_id=r["attempt_id"],
                    job_id=r["job_id"],
                    attempt_number=r["attempt_number"],
                    worker_id=r["worker_id"],
                    started_at_utc=r["started_at_utc"],
                    ended_at_utc=r["ended_at_utc"],
                    status=JobStatus(r["status"]),
                    error_details=r["error_details"],
                    exit_code=r["exit_code"],
                    diagnostics=diag,
                ))
            return attempts
        finally:
            if self._mem_conn is None:
                conn.close()

    def recover_orphaned_jobs(self, now_utc: float) -> List[Job]:
        """
        Finds jobs in CLAIMED or RUNNING status whose lease has expired.
        Resets them to READY or RETRY_PENDING so healthy workers can claim them.
        """
        conn = self._get_connection()
        try:
            with conn:
                cur = conn.execute("""
                SELECT * FROM jobs
                WHERE status IN (?, ?) AND lease_expires_at_utc IS NOT NULL AND lease_expires_at_utc <= ?
                """, (JobStatus.CLAIMED.value, JobStatus.RUNNING.value, now_utc))
                rows = cur.fetchall()
                recovered: List[Job] = []

                for r in rows:
                    job = self._row_to_job(r)
                    new_status = JobStatus.READY if job.attempt_count < job.max_attempts else JobStatus.FAILED
                    conn.execute("""
                    UPDATE jobs
                    SET status = ?,
                        current_lease_owner = NULL,
                        lease_expires_at_utc = NULL,
                        error_message = COALESCE(error_message, 'Worker crashed or lease expired; recovered for retry')
                    WHERE job_id = ?
                    """, (new_status.value, job.job_id))
                    conn.execute("DELETE FROM leases WHERE job_id = ?", (job.job_id,))
                    job.status = new_status
                    recovered.append(job)

                return recovered
        finally:
            if self._mem_conn is None:
                conn.close()

    def prune_completed_jobs(self, older_than_seconds: float) -> int:
        cutoff = time.time() - older_than_seconds
        conn = self._get_connection()
        try:
            with conn:
                cur = conn.execute("""
                DELETE FROM jobs
                WHERE status IN (?, ?, ?) AND completed_at_utc IS NOT NULL AND completed_at_utc <= ?
                """, (JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value, cutoff))
                return cur.rowcount
        finally:
            if self._mem_conn is None:
                conn.close()

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        artifacts = json.loads(row["artifacts_json"]) if row["artifacts_json"] else []
        meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
        return Job(
            job_id=row["job_id"],
            schedule_id=row["schedule_id"],
            tenant_id=row["tenant_id"],
            owner_user_id=row["owner_user_id"],
            task_id=row["task_id"],
            status=JobStatus(row["status"]),
            attempt_count=row["attempt_count"],
            max_attempts=row["max_attempts"],
            current_lease_owner=row["current_lease_owner"],
            lease_expires_at_utc=row["lease_expires_at_utc"],
            fencing_token=row["fencing_token"],
            last_heartbeat_at_utc=row["last_heartbeat_at_utc"],
            scheduled_for_utc=row["scheduled_for_utc"],
            started_at_utc=row["started_at_utc"],
            completed_at_utc=row["completed_at_utc"],
            error_message=row["error_message"],
            idempotency_key=row["idempotency_key"],
            ancestry=row["ancestry"],
            budget_tokens=row["budget_tokens"],
            consumed_tokens=row["consumed_tokens"],
            budget_paisa=row["budget_paisa"],
            consumed_paisa=row["consumed_paisa"],
            artifacts=artifacts,
            trace_id=row["trace_id"],
            metadata=meta,
        )

    # -------------------------------------------------------------------------
    # PERMISSION GRANTS
    # -------------------------------------------------------------------------
    def save_permission_grant(self, grant: PermissionGrant) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                INSERT INTO permission_grants (
                    grant_id, tenant_id, owner_user_id, tier, allowed_tools_json,
                    allowed_domains_json, repo_whitelist_json, max_budget_paisa,
                    expires_at_utc, is_revoked, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(grant_id) DO UPDATE SET
                    tier = excluded.tier,
                    allowed_tools_json = excluded.allowed_tools_json,
                    allowed_domains_json = excluded.allowed_domains_json,
                    repo_whitelist_json = excluded.repo_whitelist_json,
                    max_budget_paisa = excluded.max_budget_paisa,
                    expires_at_utc = excluded.expires_at_utc,
                    is_revoked = excluded.is_revoked
                """, (
                    grant.grant_id,
                    grant.tenant_id,
                    grant.owner_user_id,
                    grant.tier.value,
                    json.dumps(grant.allowed_tools),
                    json.dumps(grant.allowed_domains),
                    json.dumps(grant.repo_whitelist),
                    grant.max_budget_paisa,
                    grant.expires_at_utc,
                    1 if grant.is_revoked else 0,
                    grant.created_at_utc,
                ))
        finally:
            if self._mem_conn is None:
                conn.close()

    def get_permission_grant(self, grant_id: str) -> Optional[PermissionGrant]:
        conn = self._get_connection()
        try:
            cur = conn.execute("SELECT * FROM permission_grants WHERE grant_id = ?", (grant_id,))
            row = cur.fetchone()
            if not row:
                return None
            return PermissionGrant(
                grant_id=row["grant_id"],
                tenant_id=row["tenant_id"],
                owner_user_id=row["owner_user_id"],
                tier=PermissionTier(row["tier"]),
                allowed_tools=json.loads(row["allowed_tools_json"]),
                allowed_domains=json.loads(row["allowed_domains_json"]) if row["allowed_domains_json"] else [],
                repo_whitelist=json.loads(row["repo_whitelist_json"]) if row["repo_whitelist_json"] else [],
                max_budget_paisa=row["max_budget_paisa"],
                expires_at_utc=row["expires_at_utc"],
                is_revoked=bool(row["is_revoked"]),
                created_at_utc=row["created_at_utc"],
            )
        finally:
            if self._mem_conn is None:
                conn.close()

    def revoke_permission_grant(self, grant_id: str) -> bool:
        conn = self._get_connection()
        try:
            with conn:
                cur = conn.execute("UPDATE permission_grants SET is_revoked = 1 WHERE grant_id = ?", (grant_id,))
                return cur.rowcount > 0
        finally:
            if self._mem_conn is None:
                conn.close()

    # -------------------------------------------------------------------------
    # NOTIFICATIONS
    # -------------------------------------------------------------------------
    def save_notification(self, notif: Notification) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                INSERT INTO notifications (
                    notification_id, tenant_id, user_id, event_type, title,
                    message, job_id, schedule_id, severity, is_read,
                    created_at_utc, idempotency_key, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(notification_id) DO UPDATE SET
                    is_read = excluded.is_read
                """, (
                    notif.notification_id,
                    notif.tenant_id,
                    notif.user_id,
                    notif.event_type,
                    notif.title,
                    notif.message,
                    notif.job_id,
                    notif.schedule_id,
                    notif.severity.value if isinstance(notif.severity, SeverityLevel) else notif.severity,
                    1 if notif.is_read else 0,
                    notif.created_at_utc,
                    notif.idempotency_key,
                    json.dumps(notif.metadata),
                ))
        finally:
            if self._mem_conn is None:
                conn.close()

    def get_notification_by_idempotency_key(self, tenant_id: str, idempotency_key: str) -> Optional[Notification]:
        if not idempotency_key:
            return None
        conn = self._get_connection()
        try:
            cur = conn.execute(
                "SELECT * FROM notifications WHERE tenant_id = ? AND idempotency_key = ?",
                (tenant_id, idempotency_key),
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_notification(row)
        finally:
            if self._mem_conn is None:
                conn.close()

    def list_notifications(self, tenant_id: str, user_id: str, limit: int = 50, unread_only: bool = False) -> List[Notification]:
        conn = self._get_connection()
        try:
            if unread_only:
                cur = conn.execute(
                    "SELECT * FROM notifications WHERE tenant_id = ? AND user_id = ? AND is_read = 0 ORDER BY created_at_utc DESC LIMIT ?",
                    (tenant_id, user_id, limit),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM notifications WHERE tenant_id = ? AND user_id = ? ORDER BY created_at_utc DESC LIMIT ?",
                    (tenant_id, user_id, limit),
                )
            return [self._row_to_notification(r) for r in cur.fetchall()]
        finally:
            if self._mem_conn is None:
                conn.close()

    def mark_notifications_read(self, tenant_id: str, user_id: str, notification_ids: Optional[List[str]] = None) -> int:
        conn = self._get_connection()
        try:
            with conn:
                if notification_ids:
                    placeholders = ",".join("?" for _ in notification_ids)
                    cur = conn.execute(
                        f"UPDATE notifications SET is_read = 1 WHERE tenant_id = ? AND user_id = ? AND notification_id IN ({placeholders})",
                        [tenant_id, user_id, *notification_ids],
                    )
                else:
                    cur = conn.execute(
                        "UPDATE notifications SET is_read = 1 WHERE tenant_id = ? AND user_id = ?",
                        (tenant_id, user_id),
                    )
                return cur.rowcount
        finally:
            if self._mem_conn is None:
                conn.close()

    def _row_to_notification(self, row: sqlite3.Row) -> Notification:
        meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
        return Notification(
            notification_id=row["notification_id"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            event_type=row["event_type"],
            title=row["title"],
            message=row["message"],
            job_id=row["job_id"],
            schedule_id=row["schedule_id"],
            severity=SeverityLevel(row["severity"]),
            is_read=bool(row["is_read"]),
            created_at_utc=row["created_at_utc"],
            idempotency_key=row["idempotency_key"],
            metadata=meta,
        )

    # -------------------------------------------------------------------------
    # APPEND-ONLY MONOTONIC EVENT JOURNAL
    # -------------------------------------------------------------------------
    def append_event(
        self,
        event_id: str,
        tenant_id: str,
        event_type: str,
        payload: Dict[str, Any],
        trace_id: str,
        job_id: Optional[str] = None,
        schedule_id: Optional[str] = None,
    ) -> AutopilotEvent:
        conn = self._get_connection()
        now = time.time()
        try:
            with conn:
                cur = conn.execute("""
                INSERT INTO autopilot_events (
                    event_id, tenant_id, job_id, schedule_id, event_type,
                    payload_json, trace_id, timestamp_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id,
                    tenant_id,
                    job_id,
                    schedule_id,
                    event_type,
                    json.dumps(payload),
                    trace_id,
                    now,
                ))
                seq = cur.lastrowid
                return AutopilotEvent(
                    event_id=event_id,
                    sequence=seq,
                    tenant_id=tenant_id,
                    job_id=job_id,
                    schedule_id=schedule_id,
                    event_type=event_type,
                    payload=payload,
                    trace_id=trace_id,
                    timestamp_utc=now,
                )
        finally:
            if self._mem_conn is None:
                conn.close()

    def get_events(self, tenant_id: str, since_sequence: int = 0, limit: int = 100) -> List[AutopilotEvent]:
        conn = self._get_connection()
        try:
            cur = conn.execute(
                "SELECT * FROM autopilot_events WHERE tenant_id = ? AND sequence > ? ORDER BY sequence ASC LIMIT ?",
                (tenant_id, since_sequence, limit),
            )
            events = []
            for r in cur.fetchall():
                payload = json.loads(r["payload_json"]) if r["payload_json"] else {}
                events.append(AutopilotEvent(
                    event_id=r["event_id"],
                    sequence=r["sequence"],
                    tenant_id=r["tenant_id"],
                    job_id=r["job_id"],
                    schedule_id=r["schedule_id"],
                    event_type=r["event_type"],
                    payload=payload,
                    trace_id=r["trace_id"],
                    timestamp_utc=r["timestamp_utc"],
                ))
            return events
        finally:
            if self._mem_conn is None:
                conn.close()
