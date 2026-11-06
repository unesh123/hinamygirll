"""
HINAA OS — Phase 16 Evaluation & Self-Improvement Persistence Store
SQLite WAL-backed persistent storage for dataset manifests, eval cases, run manifests,
per-case score results, candidate changes, canary states, and CAS worker leases.
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

from hinaa_api.evals.contracts import (
    CandidateChange,
    CandidateStatus,
    DatasetManifest,
    DatasetPartition,
    EvalCase,
    EvalRunManifest,
    EvalRunStatus,
    ImprovementProposal,
    PromotionDecision,
    RollbackReceipt,
    ScoreResult,
    TraceReceipt,
)

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(os.environ.get("HINAA_AUTOPILOT_DB", "hinaa_autopilot.db"))


class EvalStore:
    """Thread-safe SQLite store for evaluation manifests, cases, candidates, and runs."""

    def __init__(self, db_path: Optional[Union[Path, str]] = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._is_memory = str(self.db_path) == ":memory:" or "mode=memory" in str(self.db_path)
        self._mem_conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._is_memory:
            if self._mem_conn is None:
                self._mem_conn = sqlite3.connect(
                    ":memory:",
                    timeout=30.0,
                    check_same_thread=False,
                    isolation_level="DEFERRED",
                )
                self._mem_conn.row_factory = sqlite3.Row
            return self._mem_conn

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
                # 1. Datasets table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS eval_datasets (
                        dataset_id TEXT PRIMARY KEY,
                        version TEXT NOT NULL,
                        dataset_hash TEXT NOT NULL,
                        total_cases INTEGER NOT NULL,
                        dev_count INTEGER NOT NULL,
                        val_count INTEGER NOT NULL,
                        holdout_count INTEGER NOT NULL,
                        manifest_json TEXT NOT NULL,
                        frozen_at REAL NOT NULL
                    );
                    """
                )

                # 2. Evaluation Cases table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS eval_cases (
                        case_id TEXT PRIMARY KEY,
                        dataset_id TEXT NOT NULL,
                        domain TEXT NOT NULL,
                        partition TEXT NOT NULL,
                        case_hash TEXT NOT NULL,
                        content_json TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        FOREIGN KEY(dataset_id) REFERENCES eval_datasets(dataset_id)
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_eval_cases_dataset ON eval_cases(dataset_id, partition);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_eval_cases_domain ON eval_cases(domain);")

                # 3. Candidates table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS eval_candidates (
                        candidate_id TEXT PRIMARY KEY,
                        proposal_id TEXT NOT NULL,
                        target_layer TEXT NOT NULL,
                        description TEXT NOT NULL,
                        patch_diff TEXT NOT NULL,
                        config_hash_before TEXT NOT NULL,
                        config_hash_after TEXT NOT NULL,
                        weights_updated INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL,
                        created_at REAL NOT NULL
                    );
                    """
                )

                # 4. Evaluation Runs table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS eval_runs (
                        run_id TEXT PRIMARY KEY,
                        eval_suite_id TEXT NOT NULL,
                        dataset_id TEXT NOT NULL,
                        dataset_hash TEXT NOT NULL,
                        baseline_snapshot_id TEXT NOT NULL,
                        candidate_id TEXT,
                        status TEXT NOT NULL,
                        cases_total INTEGER NOT NULL,
                        cases_completed INTEGER NOT NULL,
                        cases_passed INTEGER NOT NULL,
                        cases_failed INTEGER NOT NULL,
                        cases_blocked INTEGER NOT NULL,
                        total_tokens INTEGER NOT NULL,
                        total_cost_paisa INTEGER NOT NULL,
                        p50_latency_ms REAL NOT NULL,
                        p95_latency_ms REAL NOT NULL,
                        p99_latency_ms REAL NOT NULL,
                        git_commit TEXT NOT NULL,
                        hardware_fingerprint TEXT NOT NULL,
                        manifest_json TEXT NOT NULL,
                        started_at REAL NOT NULL,
                        completed_at REAL
                    );
                    """
                )

                # 5. Scores table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS eval_scores (
                        score_id TEXT PRIMARY KEY,
                        case_id TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        candidate_id TEXT,
                        evaluator_name TEXT NOT NULL,
                        score REAL NOT NULL,
                        passed INTEGER NOT NULL,
                        metrics_json TEXT NOT NULL,
                        details_json TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        FOREIGN KEY(run_id) REFERENCES eval_runs(run_id)
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_eval_scores_run ON eval_scores(run_id);")

                # 6. Trace Receipts table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS eval_traces (
                        trace_id TEXT PRIMARY KEY,
                        case_id TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        candidate_id TEXT,
                        input_tokens INTEGER NOT NULL,
                        output_tokens INTEGER NOT NULL,
                        cost_paisa INTEGER NOT NULL,
                        latency_ms REAL NOT NULL,
                        redacted_trace_json TEXT NOT NULL,
                        created_at REAL NOT NULL
                    );
                    """
                )

                # 7. Proposals table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS eval_proposals (
                        proposal_id TEXT PRIMARY KEY,
                        symptom TEXT NOT NULL,
                        failure_cluster TEXT NOT NULL,
                        proposal_json TEXT NOT NULL,
                        created_at REAL NOT NULL
                    );
                    """
                )

                # 8. Promotions and Rollbacks table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS eval_promotions (
                        decision_id TEXT PRIMARY KEY,
                        candidate_id TEXT NOT NULL,
                        primary_metric_gain REAL NOT NULL,
                        is_statistically_significant INTEGER NOT NULL,
                        holdout_hash TEXT NOT NULL,
                        security_gate_passed INTEGER NOT NULL,
                        human_approver_id TEXT NOT NULL,
                        approval_token_id TEXT NOT NULL,
                        outcome TEXT NOT NULL,
                        details_json TEXT NOT NULL,
                        decided_at REAL NOT NULL
                    );
                    """
                )

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS eval_rollbacks (
                        rollback_id TEXT PRIMARY KEY,
                        candidate_id TEXT NOT NULL,
                        trigger_reason TEXT NOT NULL,
                        restored_config_hash TEXT NOT NULL,
                        restored_at REAL NOT NULL,
                        restored_by TEXT NOT NULL
                    );
                    """
                )

                # 9. Worker CAS Leases with Fencing Tokens
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS eval_worker_leases (
                        run_id TEXT PRIMARY KEY,
                        worker_id TEXT NOT NULL,
                        fence_token INTEGER NOT NULL,
                        lease_expires_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    );
                    """
                )
                conn.commit()

    # --- Dataset Operations ---

    def save_dataset(self, manifest: DatasetManifest, cases: List[EvalCase]) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO eval_datasets (
                        dataset_id, version, dataset_hash, total_cases,
                        dev_count, val_count, holdout_count, manifest_json, frozen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(dataset_id) DO UPDATE SET
                        dataset_hash = excluded.dataset_hash,
                        total_cases = excluded.total_cases,
                        dev_count = excluded.dev_count,
                        val_count = excluded.val_count,
                        holdout_count = excluded.holdout_count,
                        manifest_json = excluded.manifest_json;
                    """,
                    (
                        manifest.dataset_id,
                        manifest.version,
                        manifest.dataset_hash,
                        manifest.total_cases,
                        manifest.dev_count,
                        manifest.val_count,
                        manifest.holdout_count,
                        manifest.model_dump_json(),
                        manifest.frozen_at,
                    ),
                )

                for c in cases:
                    conn.execute(
                        """
                        INSERT INTO eval_cases (
                            case_id, dataset_id, domain, partition,
                            case_hash, content_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(case_id) DO UPDATE SET
                            domain = excluded.domain,
                            partition = excluded.partition,
                            case_hash = excluded.case_hash,
                            content_json = excluded.content_json;
                        """,
                        (
                            c.case_id,
                            manifest.dataset_id,
                            c.domain.value,
                            c.partition.value,
                            c.case_id,
                            c.model_dump_json(),
                            c.created_at,
                        ),
                    )
                conn.commit()

    def get_dataset(self, dataset_id: str) -> Optional[DatasetManifest]:
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT manifest_json FROM eval_datasets WHERE dataset_id = ?;", (dataset_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return DatasetManifest(**json.loads(row["manifest_json"]))

    def get_cases(
        self,
        dataset_id: str,
        partition: Optional[DatasetPartition] = None,
        limit: int = 500,
    ) -> List[EvalCase]:
        with self._lock:
            with self._get_connection() as conn:
                if partition:
                    cur = conn.execute(
                        "SELECT content_json FROM eval_cases WHERE dataset_id = ? AND partition = ? LIMIT ?;",
                        (dataset_id, partition.value, limit),
                    )
                else:
                    cur = conn.execute(
                        "SELECT content_json FROM eval_cases WHERE dataset_id = ? LIMIT ?;",
                        (dataset_id, limit),
                    )
                return [EvalCase(**json.loads(r["content_json"])) for r in cur.fetchall()]

    # --- Runs & Scores Operations ---

    def save_run(self, manifest: EvalRunManifest) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO eval_runs (
                        run_id, eval_suite_id, dataset_id, dataset_hash,
                        baseline_snapshot_id, candidate_id, status,
                        cases_total, cases_completed, cases_passed, cases_failed, cases_blocked,
                        total_tokens, total_cost_paisa, p50_latency_ms, p95_latency_ms, p99_latency_ms,
                        git_commit, hardware_fingerprint, manifest_json, started_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id) DO UPDATE SET
                        status = excluded.status,
                        cases_completed = excluded.cases_completed,
                        cases_passed = excluded.cases_passed,
                        cases_failed = excluded.cases_failed,
                        cases_blocked = excluded.cases_blocked,
                        total_tokens = excluded.total_tokens,
                        total_cost_paisa = excluded.total_cost_paisa,
                        p50_latency_ms = excluded.p50_latency_ms,
                        p95_latency_ms = excluded.p95_latency_ms,
                        p99_latency_ms = excluded.p99_latency_ms,
                        manifest_json = excluded.manifest_json,
                        completed_at = excluded.completed_at;
                    """,
                    (
                        manifest.run_id,
                        manifest.eval_suite_id,
                        manifest.dataset_id,
                        manifest.dataset_hash,
                        manifest.baseline_snapshot_id,
                        manifest.candidate_id,
                        manifest.status.value,
                        manifest.cases_total,
                        manifest.cases_completed,
                        manifest.cases_passed,
                        manifest.cases_failed,
                        manifest.cases_blocked,
                        manifest.total_tokens,
                        manifest.total_cost_paisa,
                        manifest.p50_latency_ms,
                        manifest.p95_latency_ms,
                        manifest.p99_latency_ms,
                        manifest.git_commit,
                        manifest.hardware_fingerprint,
                        manifest.model_dump_json(),
                        manifest.started_at,
                        manifest.completed_at,
                    ),
                )
                conn.commit()

    def get_run(self, run_id: str) -> Optional[EvalRunManifest]:
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT manifest_json FROM eval_runs WHERE run_id = ?;", (run_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return EvalRunManifest(**json.loads(row["manifest_json"]))

    def save_score(self, score: ScoreResult) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO eval_scores (
                        score_id, case_id, run_id, candidate_id,
                        evaluator_name, score, passed, metrics_json, details_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(score_id) DO UPDATE SET
                        score = excluded.score,
                        passed = excluded.passed,
                        metrics_json = excluded.metrics_json;
                    """,
                    (
                        score.score_id,
                        score.case_id,
                        score.run_id,
                        score.candidate_id,
                        score.evaluator_name,
                        score.score,
                        1 if score.passed else 0,
                        score.metrics.model_dump_json(),
                        json.dumps(score.details),
                        score.created_at,
                    ),
                )
                conn.commit()

    def get_scores_for_run(self, run_id: str) -> List[ScoreResult]:
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT * FROM eval_scores WHERE run_id = ?;", (run_id,))
                results = []
                for r in cur.fetchall():
                    results.append(
                        ScoreResult(
                            score_id=r["score_id"],
                            case_id=r["case_id"],
                            run_id=r["run_id"],
                            candidate_id=r["candidate_id"],
                            evaluator_name=r["evaluator_name"],
                            score=r["score"],
                            passed=bool(r["passed"]),
                            metrics=json.loads(r["metrics_json"]),
                            details=json.loads(r["details_json"]),
                            created_at=r["created_at"],
                        )
                    )
                return results

    # --- Candidate & Promotion Operations ---

    def save_candidate(self, candidate: CandidateChange) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO eval_candidates (
                        candidate_id, proposal_id, target_layer, description,
                        patch_diff, config_hash_before, config_hash_after,
                        weights_updated, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(candidate_id) DO UPDATE SET
                        status = excluded.status;
                    """,
                    (
                        candidate.candidate_id,
                        candidate.proposal_id,
                        candidate.target_layer,
                        candidate.description,
                        candidate.patch_diff,
                        candidate.config_hash_before,
                        candidate.config_hash_after,
                        1 if candidate.weights_updated else 0,
                        candidate.status.value,
                        candidate.created_at,
                    ),
                )
                conn.commit()

    def get_candidate(self, candidate_id: str) -> Optional[CandidateChange]:
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT * FROM eval_candidates WHERE candidate_id = ?;", (candidate_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return CandidateChange(
                    candidate_id=row["candidate_id"],
                    proposal_id=row["proposal_id"],
                    target_layer=row["target_layer"],
                    description=row["description"],
                    patch_diff=row["patch_diff"],
                    config_hash_before=row["config_hash_before"],
                    config_hash_after=row["config_hash_after"],
                    weights_updated=bool(row["weights_updated"]),
                    status=CandidateStatus(row["status"]),
                    created_at=row["created_at"],
                )

    def save_promotion(self, promo: PromotionDecision) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO eval_promotions (
                        decision_id, candidate_id, primary_metric_gain,
                        is_statistically_significant, holdout_hash, security_gate_passed,
                        human_approver_id, approval_token_id, outcome, details_json, decided_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        promo.decision_id,
                        promo.candidate_id,
                        promo.primary_metric_gain,
                        1 if promo.is_statistically_significant else 0,
                        promo.holdout_hash,
                        1 if promo.security_gate_passed else 0,
                        promo.human_approver_id,
                        promo.approval_token_id,
                        promo.outcome.value,
                        promo.model_dump_json(),
                        promo.decided_at,
                    ),
                )
                conn.commit()

    def save_rollback(self, rollback: RollbackReceipt) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO eval_rollbacks (
                        rollback_id, candidate_id, trigger_reason,
                        restored_config_hash, restored_at, restored_by
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rollback.rollback_id,
                        rollback.candidate_id,
                        rollback.trigger_reason,
                        rollback.restored_config_hash,
                        rollback.restored_at,
                        rollback.restored_by,
                    ),
                )
                conn.commit()

    # --- Worker CAS Lease & Fencing Tokens ---

    def acquire_eval_lease(self, run_id: str, worker_id: str, ttl_seconds: float = 60.0) -> Tuple[bool, int]:
        """Atomically acquires lease with an incremented fencing token."""
        with self._lock:
            with self._get_connection() as conn:
                now = time.time()
                cur = conn.execute("SELECT worker_id, fence_token, lease_expires_at FROM eval_worker_leases WHERE run_id = ?;", (run_id,))
                row = cur.fetchone()
                if not row:
                    # Initial acquisition
                    fence = 1
                    conn.execute(
                        """
                        INSERT INTO eval_worker_leases (run_id, worker_id, fence_token, lease_expires_at, updated_at)
                        VALUES (?, ?, ?, ?, ?);
                        """,
                        (run_id, worker_id, fence, now + ttl_seconds, now),
                    )
                    conn.commit()
                    return True, fence

                # Check if expired or owned by same worker
                if row["lease_expires_at"] < now or row["worker_id"] == worker_id:
                    fence = row["fence_token"] + 1
                    conn.execute(
                        """
                        UPDATE eval_worker_leases
                        SET worker_id = ?, fence_token = ?, lease_expires_at = ?, updated_at = ?
                        WHERE run_id = ? AND fence_token = ?;
                        """,
                        (worker_id, fence, now + ttl_seconds, now, run_id, row["fence_token"]),
                    )
                    conn.commit()
                    return True, fence

                return False, row["fence_token"]


_default_eval_store: Optional[EvalStore] = None


def get_eval_store(db_path: Optional[Path] = None) -> EvalStore:
    global _default_eval_store
    if db_path is not None:
        return EvalStore(db_path)
    if _default_eval_store is None:
        _default_eval_store = EvalStore()
    return _default_eval_store
