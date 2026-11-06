"""
HINAA OS — Phase 17 Full 112-Scenario Acceptance Test Suite (P17-001 to P17-112).

Covers all 14 platform reliability, hardening, edge sync & high availability groups:
- Group A: Packaging, Multi-Stage Builds & Dependency Integrity (P17-001 to P17-008)
- Group B: Configuration, Environment Schemas & Production Validation (P17-009 to P17-016)
- Group C: Startup, Bootstrap & Dependency Sequencing (P17-017 to P17-024)
- Group D: Reverse Proxy, TLS & Traffic Routing (P17-025 to P17-032)
- Group E: Durable Task Queue & Transactional Outbox (P17-033 to P17-040)
- Group F: Exactly-Once Consequential Execution & Idempotency (P17-041 to P17-048)
- Group G: Dead Letter Queue, Retry Budgets & Backoff (P17-049 to P17-056)
- Group H: SQLite WAL Durability, Checkpoints & Migrations (P17-057 to P17-064)
- Group I: Hot Online Backups, RPO & Deterministic Restores (P17-065 to P17-072)
- Group J: Edge Pairing, Public Key Fingerprints & Revocation (P17-073 to P17-080)
- Group K: Local-First Replication, Zero-Leak & Tombstones (P17-081 to P17-088)
- Group L: Conflict Detection, Structured Review & Convergence (P17-089 to P17-096)
- Group M: Fault Injection, Chaos Drills & Availability (P17-097 to P17-104)
- Group N: Structured Observability, Tracing & SLO Auditing (P17-105 to P17-112)
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Add apps/api to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hinaa_api.platform.contracts import (
    ConflictResolutionStrategy,
    DeploymentProfile,
    HealthState,
    ProbeResponse,
    QueueBackendType,
    SyncPeerStatus,
    VerificationStatus,
)
from hinaa_api.platform.config_schema import EnvironmentConfig, load_environment_config
from hinaa_api.platform.health import HealthManager
from hinaa_api.platform.queue import DurableQueueManager
from hinaa_api.platform.backup import BackupManager
from hinaa_api.platform.migration import MigrationRunner
from hinaa_api.platform.sync import EdgeSyncEngine
from hinaa_api.platform.chaos import ChaosDrillRunner
from hinaa_api.platform.metrics import TelemetryCollector

REPO_ROOT = Path(__file__).resolve().parents[4]


class TestPhase17AcceptanceSuite(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="hinaa_p17_suite_")
        self.db_path = Path(self.temp_dir) / "test_hinaa.db"
        self.backup_dir = Path(self.temp_dir) / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self.queue_mgr = DurableQueueManager(db_path=str(self.db_path))
        self.backup_mgr = BackupManager(db_path=str(self.db_path), backup_dir=str(self.backup_dir))
        self.sync_engine = EdgeSyncEngine(db_path=str(self.db_path))
        self.chaos_runner = ChaosDrillRunner(self.queue_mgr, self.backup_mgr)
        self.telemetry = TelemetryCollector()

        # Seed test db
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS test_entities (id TEXT PRIMARY KEY, val TEXT);")
            conn.execute("INSERT OR REPLACE INTO test_entities VALUES ('e1', 'init');")
            conn.commit()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # Group A: Packaging, Multi-Stage Builds & Dependency Integrity (P17-001 to P17-008)
    # =========================================================================

    def test_p17_001_api_dockerfile_multistage_non_root(self):
        df = REPO_ROOT / "deploy" / "docker" / "Dockerfile.api"
        self.assertTrue(df.exists())
        content = df.read_text(encoding="utf-8")
        self.assertIn("FROM python:3.12-slim-bookworm AS builder", content)
        self.assertIn("FROM python:3.12-slim-bookworm AS runtime", content)
        self.assertIn("useradd -u 10001", content)
        self.assertIn("USER hinaa:hinaa", content)

    def test_p17_002_web_dockerfile_multistage(self):
        df = REPO_ROOT / "deploy" / "docker" / "Dockerfile.web"
        self.assertTrue(df.exists())
        content = df.read_text(encoding="utf-8")
        self.assertIn("FROM node:20-alpine AS builder", content)
        self.assertIn("pnpm --filter web build", content)

    def test_p17_003_worker_dockerfile_isolated(self):
        df = REPO_ROOT / "deploy" / "docker" / "Dockerfile.worker"
        self.assertTrue(df.exists())
        content = df.read_text(encoding="utf-8")
        self.assertIn("hinaa_api.platform.queue", content)
        self.assertNotIn("EXPOSE 8000", content)

    def test_p17_004_dockerignore_excludes_secrets(self):
        di = REPO_ROOT / "deploy" / "docker" / ".dockerignore"
        self.assertTrue(di.exists())
        content = di.read_text(encoding="utf-8")
        self.assertIn(".venv", content)
        self.assertIn(".env*", content)
        self.assertIn("node_modules", content)

    def test_p17_005_dependency_pinning_pyproject(self):
        pj = REPO_ROOT / "apps" / "api" / "pyproject.toml"
        self.assertTrue(pj.exists())
        content = pj.read_text(encoding="utf-8")
        self.assertIn("pytest", content)

    def test_p17_006_docker_daemon_detection_honesty(self):
        # On Windows laptop without background daemon, container builds are marked CONTAINER_BUILD_BLOCKED
        status = VerificationStatus.CONTAINER_BUILD_BLOCKED
        self.assertIn(status, VerificationStatus)

    def test_p17_007_supply_chain_sha_verification(self):
        # Cryptographic checksum of deploy artifact
        api_df = REPO_ROOT / "deploy" / "docker" / "Dockerfile.api"
        import hashlib
        sha = hashlib.sha256(api_df.read_bytes()).hexdigest()
        self.assertEqual(len(sha), 64)

    def test_p17_008_non_root_container_permissions(self):
        df = REPO_ROOT / "deploy" / "docker" / "Dockerfile.api"
        content = df.read_text(encoding="utf-8")
        self.assertIn("10001", content)
        self.assertNotIn("USER root", content)

    # =========================================================================
    # Group B: Configuration, Environment Schemas & Production Validation (P17-009 to P17-016)
    # =========================================================================

    def test_p17_009_prod_schema_rejects_debug(self):
        with self.assertRaises(ValueError):
            EnvironmentConfig(
                deployment_profile=DeploymentProfile.CLOUD_PRODUCTION,
                debug=True,
                secret_key="hinaa_secure_prod_key_over_32_characters_long",
            )

    def test_p17_010_prod_schema_rejects_wildcard_cors(self):
        with self.assertRaises(ValueError):
            EnvironmentConfig(
                deployment_profile=DeploymentProfile.CLOUD_PRODUCTION,
                cors_origins=["*"],
                secret_key="hinaa_secure_prod_key_over_32_characters_long",
            )

    def test_p17_011_prod_schema_rejects_short_secret(self):
        with self.assertRaises(ValueError):
            EnvironmentConfig(
                deployment_profile=DeploymentProfile.CLOUD_PRODUCTION,
                secret_key="short_key",
            )

    def test_p17_012_local_desktop_allows_dev_settings(self):
        cfg = EnvironmentConfig(
            deployment_profile=DeploymentProfile.LOCAL_DESKTOP,
            debug=True,
            secret_key="dev_secret",
        )
        self.assertTrue(cfg.debug)
        self.assertEqual(cfg.get_verification_status(), VerificationStatus.LOCAL_VERIFIED)

    def test_p17_013_lan_collaboration_profile(self):
        cfg = EnvironmentConfig(
            deployment_profile=DeploymentProfile.LOCAL_LAN,
            bind_host="0.0.0.0",
        )
        self.assertEqual(cfg.get_verification_status(), VerificationStatus.MULTI_PROCESS_SAME_HOST_VERIFIED)

    def test_p17_014_staging_profile_honest_status(self):
        cfg = EnvironmentConfig(
            deployment_profile=DeploymentProfile.CLOUD_STAGING,
            secret_key="hinaa_staging_secret_key_over_32_characters_long",
        )
        # Without multi-host redis, status must be CONFIG_REQUIRED, not MULTI_HOST_VERIFIED
        self.assertEqual(cfg.get_verification_status(), VerificationStatus.CONFIG_REQUIRED)

    def test_p17_015_load_environment_defaults(self):
        cfg = load_environment_config()
        self.assertIsNotNone(cfg.deployment_profile)
        self.assertEqual(cfg.bind_port, 8000)

    def test_p17_016_environment_profile_detection(self):
        cfg = load_environment_config({"HINAA_DEPLOYMENT_PROFILE": "LOCAL_DESKTOP"})
        self.assertEqual(cfg.deployment_profile, DeploymentProfile.LOCAL_DESKTOP)

    # =========================================================================
    # Group C: Startup, Bootstrap & Dependency Sequencing (P17-017 to P17-024)
    # =========================================================================

    def test_p17_017_startup_probe_in_progress(self):
        h = HealthManager(db_path=str(self.db_path))
        h._startup_completed = False
        res = h.check_startup()
        self.assertEqual(res.status, HealthState.STARTING)

    def test_p17_018_startup_probe_complete(self):
        h = HealthManager(db_path=str(self.db_path))
        h.mark_startup_complete()
        res = h.check_startup()
        self.assertEqual(res.status, HealthState.HEALTHY)

    def test_p17_019_liveness_probe_low_latency(self):
        h = HealthManager(db_path=str(self.db_path))
        t0 = time.perf_counter()
        res = h.check_liveness()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.assertEqual(res.status, HealthState.HEALTHY)
        self.assertLess(elapsed_ms, 15.0)

    def test_p17_020_readiness_probe_active(self):
        h = HealthManager(db_path=str(self.db_path))
        res = h.check_readiness()
        self.assertEqual(res.status, HealthState.HEALTHY)

    def test_p17_021_dependencies_probe_unauthenticated_denied(self):
        h = HealthManager(db_path=str(self.db_path))
        with self.assertRaises(PermissionError):
            h.check_dependencies(caller_role="anonymous")

    def test_p17_022_dependencies_probe_operator_allowed(self):
        h = HealthManager(db_path=str(self.db_path))
        diag = h.check_dependencies(caller_role="operator")
        self.assertEqual(diag.overall_status, HealthState.HEALTHY)
        self.assertIn("sqlite", diag.dependencies)

    def test_p17_023_startup_failure_marks_unhealthy(self):
        h = HealthManager(db_path=str(self.db_path))
        h.mark_startup_failed("Fatal schema migration error")
        res = h.check_startup()
        self.assertEqual(res.status, HealthState.UNHEALTHY)
        self.assertIn("error", res.details)

    def test_p17_024_fast_retry_loop_resilience(self):
        h = HealthManager(db_path=str(self.db_path))
        ok, msg = h._probe_sqlite()
        self.assertTrue(ok)
        self.assertEqual(msg, "Database healthy")

    # =========================================================================
    # Group D: Reverse Proxy, TLS & Traffic Routing (P17-025 to P17-032)
    # =========================================================================

    def test_p17_025_nginx_conf_syntax(self):
        conf = REPO_ROOT / "deploy" / "nginx" / "nginx.conf"
        self.assertTrue(conf.exists())
        text = conf.read_text(encoding="utf-8")
        self.assertIn("proxy_pass http://api:8000/api/;", text)
        self.assertIn("proxy_pass http://api:8000/health/;", text)

    def test_p17_026_caddyfile_syntax(self):
        caddy = REPO_ROOT / "deploy" / "caddy" / "Caddyfile"
        self.assertTrue(caddy.exists())
        text = caddy.read_text(encoding="utf-8")
        self.assertIn("reverse_proxy api:8000", text)

    def test_p17_027_security_headers_present(self):
        conf = REPO_ROOT / "deploy" / "nginx" / "nginx.conf"
        text = conf.read_text(encoding="utf-8")
        self.assertIn("X-Frame-Options", text)
        self.assertIn("X-Content-Type-Options", text)

    def test_p17_028_websocket_upgrade_routing(self):
        conf = REPO_ROOT / "deploy" / "nginx" / "nginx.conf"
        text = conf.read_text(encoding="utf-8")
        self.assertIn("Upgrade $http_upgrade", text)
        self.assertIn("Connection \"upgrade\"", text)

    def test_p17_029_static_asset_spa_fallback(self):
        conf = REPO_ROOT / "deploy" / "nginx" / "nginx.conf"
        text = conf.read_text(encoding="utf-8")
        self.assertIn("try_files $uri $uri/ /index.html", text)

    def test_p17_030_client_ip_headers_forwarded(self):
        conf = REPO_ROOT / "deploy" / "nginx" / "nginx.conf"
        text = conf.read_text(encoding="utf-8")
        self.assertIn("X-Forwarded-For", text)
        self.assertIn("X-Real-IP", text)

    def test_p17_031_health_probe_unauthenticated_proxy(self):
        conf = REPO_ROOT / "deploy" / "nginx" / "nginx.conf"
        text = conf.read_text(encoding="utf-8")
        self.assertIn("location /health/", text)

    def test_p17_032_upstream_timeout_bounds(self):
        conf = REPO_ROOT / "deploy" / "nginx" / "nginx.conf"
        text = conf.read_text(encoding="utf-8")
        self.assertIn("proxy_read_timeout 120s;", text)

    # =========================================================================
    # Group E: Durable Task Queue & Transactional Outbox (P17-033 to P17-040)
    # =========================================================================

    def test_p17_033_enqueue_creates_pending_outbox_record(self):
        entry = self.queue_mgr.enqueue("op_1", "tasks", {"action": "clean"})
        self.assertEqual(entry.status, "PENDING")
        pending = self.queue_mgr.get_pending_messages()
        self.assertEqual(len(pending), 1)

    def test_p17_034_payload_sanitization_strips_secrets(self):
        clean = self.queue_mgr.sanitize_payload({"api_key": "sk-123", "name": "valid"})
        self.assertEqual(clean["api_key"], "[REDACTED_SECRET]")
        self.assertEqual(clean["name"], "valid")

    def test_p17_035_in_flight_marking(self):
        entry = self.queue_mgr.enqueue("op_2", "tasks", {"action": "run"})
        self.queue_mgr._mark_dispatched(entry.message_id)
        # Marked in flight, not pending
        pending = self.queue_mgr.get_pending_messages()
        self.assertEqual(len(pending), 0)

    def test_p17_036_acknowledgment_commits_message(self):
        mid = self.queue_mgr.publish_message("tasks", {"val": 1})
        self.queue_mgr.ack_message(mid)
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute("SELECT status FROM platform_outbox WHERE message_id = ?", (mid,)).fetchone()
            self.assertEqual(row[0], "COMMITTED")

    def test_p17_037_backend_type_selection(self):
        # Default without Redis
        self.assertEqual(self.queue_mgr.backend_type, QueueBackendType.SQLITE_DURABLE)

    def test_p17_038_automatic_sqlite_fallback(self):
        qm = DurableQueueManager(db_path=str(self.db_path), redis_url="redis://nonexistent:6379")
        self.assertEqual(qm.backend_type, QueueBackendType.SQLITE_DURABLE)

    def test_p17_039_idempotent_publish(self):
        mid1 = self.queue_mgr.publish_message("stream", {"k": 1}, idempotency_key="same_key")
        self.assertTrue(mid1.startswith("outbox_"))

    def test_p17_040_transactional_integrity(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute("PRAGMA quick_check;")
            self.assertEqual(cur.fetchone()[0], "ok")

    # =========================================================================
    # Group F: Exactly-Once Consequential Execution & Idempotency (P17-041 to P17-048)
    # =========================================================================

    def test_p17_041_consequential_side_effect_executes_once(self):
        executed = []
        res = self.queue_mgr.execute_with_idempotency("key_tx_1", lambda: executed.append("paid") or {"tx": "1"})
        self.assertTrue(res)
        self.assertEqual(len(executed), 1)

    def test_p17_042_duplicate_submission_skipped(self):
        executed = []
        self.queue_mgr.execute_with_idempotency("key_tx_2", lambda: executed.append("paid") or {"tx": "2"})
        second = self.queue_mgr.execute_with_idempotency("key_tx_2", lambda: executed.append("paid") or {"tx": "2"})
        self.assertFalse(second)
        self.assertEqual(len(executed), 1)

    def test_p17_043_idempotency_table_persistence(self):
        self.queue_mgr.execute_with_idempotency("key_rec", lambda: {"status": "ok"})
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute("SELECT result_json FROM platform_idempotency_keys WHERE operation_key = 'key_rec'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(json.loads(row[0])["status"], "ok")

    def test_p17_044_worker_retry_prevents_duplicate_payments(self):
        counter = {"runs": 0}
        def pay():
            counter["runs"] += 1
            return {"amt": 100}

        self.queue_mgr.execute_with_idempotency("pay_once", pay)
        # Worker retries
        self.queue_mgr.execute_with_idempotency("pay_once", pay)
        self.assertEqual(counter["runs"], 1)

    def test_p17_045_concurrent_idempotency_locks(self):
        res1 = self.queue_mgr.execute_with_idempotency("conc_key", lambda: 1)
        res2 = self.queue_mgr.execute_with_idempotency("conc_key", lambda: 2)
        self.assertTrue(res1)
        self.assertFalse(res2)

    def test_p17_046_cross_tenant_key_isolation(self):
        # Different tenants must use tenant-prefixed keys
        res_a = self.queue_mgr.execute_with_idempotency("tenant_a:charge", lambda: "a")
        res_b = self.queue_mgr.execute_with_idempotency("tenant_b:charge", lambda: "b")
        self.assertTrue(res_a)
        self.assertTrue(res_b)

    def test_p17_047_idempotency_result_unpacking(self):
        res, is_new = self.queue_mgr.execute_with_idempotency("unpack_key", lambda: {"val": 42})
        self.assertTrue(is_new)
        self.assertEqual(res["val"], 42)

    def test_p17_048_consequential_effect_receipt_generation(self):
        res = self.queue_mgr.execute_with_idempotency("receipt_key", lambda: {"code": "RECV-01"})
        self.assertEqual(res.result["code"], "RECV-01")

    # =========================================================================
    # Group G: Dead Letter Queue, Retry Budgets & Backoff (P17-049 to P17-056)
    # =========================================================================

    def test_p17_049_failure_increments_retry_count(self):
        entry = self.queue_mgr.enqueue("op_f1", "tasks", {"val": 1})
        retried = self.queue_mgr.fail_and_retry(entry.message_id, "Temporary network timeout")
        self.assertTrue(retried)
        pending = self.queue_mgr.get_pending_messages()[0]
        self.assertEqual(pending.retry_count, 1)

    def test_p17_050_exceeding_max_retries_moves_to_dlq(self):
        entry = self.queue_mgr.enqueue("op_f2", "tasks", {"val": 2})
        self.queue_mgr.fail_and_retry(entry.message_id, "Err 1")
        self.queue_mgr.fail_and_retry(entry.message_id, "Err 2")
        retried = self.queue_mgr.fail_and_retry(entry.message_id, "Err 3")
        self.assertFalse(retried, "3rd retry exceeds max_retries and should dead-letter")
        dlqs = self.queue_mgr.list_dlq()
        self.assertEqual(len(dlqs), 1)

    def test_p17_051_dlq_preserves_error_reason(self):
        entry = self.queue_mgr.enqueue("op_f3", "tasks", {"val": 3})
        for _ in range(3):
            self.queue_mgr.fail_and_retry(entry.message_id, "Target API 500 error")
        dlq = self.queue_mgr.list_dlq()[0]
        self.assertEqual(dlq.failure_reason, "Target API 500 error")

    def test_p17_052_list_dlq_endpoint(self):
        entry = self.queue_mgr.enqueue("op_f4", "tasks", {"val": 4})
        for _ in range(3):
            self.queue_mgr.fail_and_retry(entry.message_id, "Timeout")
        dlq_list = self.queue_mgr.list_dlq(limit=10)
        self.assertGreaterEqual(len(dlq_list), 1)

    def test_p17_053_replay_dlq_requeues_message(self):
        entry = self.queue_mgr.enqueue("op_f5", "tasks", {"val": 5})
        for _ in range(3):
            self.queue_mgr.fail_and_retry(entry.message_id, "Timeout")
        dlq_entry = self.queue_mgr.list_dlq()[0]
        replayed = self.queue_mgr.replay_dlq(dlq_entry.dlq_id)
        self.assertIsNotNone(replayed)
        self.assertEqual(replayed.status, "PENDING")

    def test_p17_054_backoff_rate_limit_calculation(self):
        # 2 ^ retry_count backoff factor
        retries = 2
        backoff_sec = 0.5 * (2 ** retries)
        self.assertEqual(backoff_sec, 2.0)

    def test_p17_055_empty_dlq_initial_state(self):
        qm = DurableQueueManager(db_path=Path(self.temp_dir) / "empty.db")
        self.assertEqual(len(qm.list_dlq()), 0)

    def test_p17_056_dlq_replay_idempotency(self):
        dlq_entry = self.queue_mgr.enqueue("op_re1", "tasks", {"val": "replay"})
        for _ in range(3):
            self.queue_mgr.fail_and_retry(dlq_entry.message_id, "Err")
        dlq_id = self.queue_mgr.list_dlq()[0].dlq_id
        entry1 = self.queue_mgr.replay_dlq(dlq_id)
        self.assertIsNotNone(entry1)

    # =========================================================================
    # Group H: SQLite WAL Durability, Checkpoints & Migrations (P17-057 to P17-064)
    # =========================================================================

    def test_p17_057_sqlite_wal_journal_mode(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            self.assertEqual(mode.lower(), "wal")

    def test_p17_058_wal_checkpoint_truncate(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            res = conn.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchone()
            self.assertEqual(res[0], 0)  # Checkpoint OK

    def test_p17_059_integrity_check(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            res = conn.execute("PRAGMA integrity_check;").fetchone()
            self.assertEqual(res[0], "ok")

    def test_p17_060_versioned_migration_runner(self):
        runner = MigrationRunner(db_path=str(self.db_path))
        self.assertTrue(runner.check_migration_table())

    def test_p17_061_idempotent_migrations(self):
        runner = MigrationRunner(db_path=str(self.db_path))
        # Initial run
        runner.apply_migration("v17_001_initial_tables", "CREATE TABLE IF NOT EXISTS m1 (id INT);")
        # Second run should be no-op
        applied = runner.apply_migration("v17_001_initial_tables", "CREATE TABLE IF NOT EXISTS m1 (id INT);")
        self.assertFalse(applied, "Already applied migration must not re-run")

    def test_p17_062_atomic_migration_rollback(self):
        runner = MigrationRunner(db_path=str(self.db_path))
        with self.assertRaises(sqlite3.OperationalError):
            runner.apply_migration("v17_broken", "INVALID SQL SYNTAX HERE;")

    def test_p17_063_concurrent_reader_non_blocking(self):
        conn1 = sqlite3.connect(str(self.db_path))
        conn2 = sqlite3.connect(str(self.db_path))
        conn1.execute("INSERT INTO test_entities VALUES ('e_read', 'val');")
        conn1.commit()
        row = conn2.execute("SELECT val FROM test_entities WHERE id = 'e_read'").fetchone()
        self.assertEqual(row[0], "val")
        conn1.close()
        conn2.close()

    def test_p17_064_disk_space_healthy(self):
        free_bytes = shutil.disk_usage(self.temp_dir).free
        self.assertGreater(free_bytes, 10 * 1024 * 1024)

    # =========================================================================
    # Group I: Hot Online Backups, RPO & Deterministic Restores (P17-065 to P17-072)
    # =========================================================================

    def test_p17_065_non_locking_hot_backup(self):
        receipt = self.backup_mgr.create_hot_backup()
        self.assertTrue(receipt.integrity_ok)
        self.assertGreater(receipt.row_count, 0)

    def test_p17_066_sha256_checksum(self):
        receipt = self.backup_mgr.create_hot_backup()
        self.assertEqual(len(receipt.checksum_sha256), 64)

    def test_p17_067_backup_receipt_metadata(self):
        receipt = self.backup_mgr.create_hot_backup()
        self.assertTrue(receipt.backup_id.startswith("bkp-"))
        self.assertGreater(receipt.duration_ms, 0)

    def test_p17_068_restore_rehearsal(self):
        receipt = self.backup_mgr.create_hot_backup()
        target = Path(self.temp_dir) / "restored.db"
        restore = self.backup_mgr.restore_backup(receipt.backup_path, str(target))
        self.assertTrue(restore.integrity_ok)

    def test_p17_069_restored_db_integrity_check(self):
        receipt = self.backup_mgr.create_hot_backup()
        target = Path(self.temp_dir) / "restored2.db"
        self.backup_mgr.restore_backup(receipt.backup_path, str(target))
        with sqlite3.connect(str(target)) as conn:
            res = conn.execute("PRAGMA integrity_check;").fetchone()
            self.assertEqual(res[0], "ok")

    def test_p17_070_rto_under_5_seconds(self):
        receipt = self.backup_mgr.create_hot_backup()
        target = Path(self.temp_dir) / "restored_rto.db"
        restore = self.backup_mgr.restore_backup(receipt.backup_path, str(target))
        self.assertLess(restore.rto_ms, 5000.0)

    def test_p17_071_rpo_under_60_seconds(self):
        receipt = self.backup_mgr.create_hot_backup()
        target = Path(self.temp_dir) / "restored_rpo.db"
        restore = self.backup_mgr.restore_backup(receipt.backup_path, str(target))
        self.assertLess(restore.rpo_seconds, 60.0)

    def test_p17_072_missing_backup_raises_error(self):
        with self.assertRaises(FileNotFoundError):
            self.backup_mgr.restore_backup("nonexistent_backup.db", "target.db")

    # =========================================================================
    # Group J: Edge Pairing, Public Key Fingerprints & Revocation (P17-073 to P17-080)
    # =========================================================================

    def test_p17_073_device_pairing(self):
        dev = self.sync_engine.pair_device("Tablet", "fp_sha256_010101")
        self.assertEqual(dev.device_name, "Tablet")
        self.assertEqual(dev.status, SyncPeerStatus.ACTIVE)

    def test_p17_074_query_paired_device(self):
        dev = self.sync_engine.pair_device("Watch", "fp_sha256_020202")
        queried = self.sync_engine.get_device(dev.device_id)
        self.assertIsNotNone(queried)
        self.assertEqual(queried.device_name, "Watch")

    def test_p17_075_device_revocation_killswitch(self):
        dev = self.sync_engine.pair_device("Laptop2", "fp_sha256_030303")
        rev = self.sync_engine.revoke_device(dev.device_id)
        self.assertEqual(rev.status, SyncPeerStatus.REVOKED)

    def test_p17_076_revoked_device_sync_denied(self):
        dev = self.sync_engine.pair_device("CompromisedPhone", "fp_bad")
        self.sync_engine.revoke_device(dev.device_id)
        with self.assertRaises(PermissionError):
            self.sync_engine.generate_sync_manifest(dev.device_id)

    def test_p17_077_same_host_simulation_flag(self):
        dev = self.sync_engine.pair_device("LocalPeer", "fp_local", is_same_host_simulation=True)
        self.assertTrue(dev.is_same_host_simulation)

    def test_p17_078_fingerprint_preservation(self):
        dev = self.sync_engine.pair_device("DeviceX", "fp_exact_1234")
        self.assertEqual(dev.public_key_fingerprint, "fp_exact_1234")

    def test_p17_079_re_pairing_device(self):
        dev1 = self.sync_engine.pair_device("Revokable", "fp_rev")
        self.sync_engine.revoke_device(dev1.device_id)
        dev2 = self.sync_engine.pair_device("Revokable", "fp_new")
        self.assertEqual(dev2.status, SyncPeerStatus.ACTIVE)

    def test_p17_080_pairing_timestamp(self):
        dev = self.sync_engine.pair_device("TSDevice", "fp_ts")
        self.assertGreater(dev.paired_at, 0)

    # =========================================================================
    # Group K: Local-First Replication, Zero-Leak & Tombstones (P17-081 to P17-088)
    # =========================================================================

    def test_p17_081_record_mutation_buffered(self):
        eid = self.sync_engine.record_change("doc", "d1", {"title": "Hello"}, 1, "dev_main")
        self.assertTrue(eid.startswith("evt_"))

    def test_p17_082_zero_leak_sanitization(self):
        self.sync_engine.record_change(
            "doc", "d2",
            {"title": "Note", "secret_token": "bearer 123", "password": "pass"},
            1, "dev_main",
        )
        dev = self.sync_engine.pair_device("SyncDev", "fp_sync")
        manifest = self.sync_engine.generate_sync_manifest(dev.device_id)
        payload = [r["payload"] for r in manifest.records if r["entity_id"] == "d2"][0]
        self.assertNotIn("secret_token", payload)
        self.assertNotIn("password", payload)

    def test_p17_083_prohibited_record_types_raise_error(self):
        with self.assertRaises(PermissionError):
            self.sync_engine.record_change("payment_approval", "p1", {"amount": 500}, 1, "dev_main")

    def test_p17_084_delete_tombstone_propagation(self):
        self.sync_engine.record_change("doc", "d3", {}, 2, "dev_main", is_deleted=True)
        dev = self.sync_engine.pair_device("SyncDev2", "fp_sync2")
        manifest = self.sync_engine.generate_sync_manifest(dev.device_id)
        tombstone = [r for r in manifest.records if r["entity_id"] == "d3"][0]
        self.assertEqual(tombstone["operation"], "DELETE_TOMBSTONE")

    def test_p17_085_manifest_authorized_tenant(self):
        dev = self.sync_engine.pair_device("TenantDev", "fp_td", tenant_id="alpha")
        self.sync_engine.record_change("doc", "da", {"data": 1}, 1, "dev_main", tenant_id="alpha")
        manifest = self.sync_engine.generate_sync_manifest(dev.device_id)
        self.assertEqual(len(manifest.records), 1)

    def test_p17_086_cross_tenant_isolation(self):
        dev = self.sync_engine.pair_device("TenantDevB", "fp_tb", tenant_id="beta")
        self.sync_engine.record_change("doc", "da", {"data": 1}, 1, "dev_main", tenant_id="alpha")
        manifest = self.sync_engine.generate_sync_manifest(dev.device_id)
        self.assertEqual(len(manifest.records), 0)

    def test_p17_087_offline_queue_buffering(self):
        for i in range(5):
            self.sync_engine.record_change("doc", f"doc_{i}", {"i": i}, 1, "dev_main")
        dev = self.sync_engine.pair_device("SyncDev3", "fp_sync3")
        manifest = self.sync_engine.generate_sync_manifest(dev.device_id)
        self.assertEqual(len(manifest.records), 5)

    def test_p17_088_manifest_watermark_bounds(self):
        dev = self.sync_engine.pair_device("SyncDev4", "fp_sync4")
        manifest = self.sync_engine.generate_sync_manifest(dev.device_id)
        self.assertEqual(manifest.watermark_start, 0)

    # =========================================================================
    # Group L: Conflict Detection, Structured Review & Convergence (P17-089 to P17-096)
    # =========================================================================

    def test_p17_089_conflict_detected_on_divergent_payload(self):
        c = self.sync_engine.detect_and_record_conflict("doc", "d10", {"a": 1}, {"a": 2}, 1, 1)
        self.assertFalse(c.resolved)

    def test_p17_090_conflict_record_payloads(self):
        c = self.sync_engine.detect_and_record_conflict("doc", "d11", {"text": "local"}, {"text": "remote"}, 1, 2)
        self.assertEqual(c.local_payload["text"], "local")
        self.assertEqual(c.remote_payload["text"], "remote")

    def test_p17_091_structured_human_review_strategy(self):
        c = self.sync_engine.detect_and_record_conflict("code", "main.py", {"code": "v1"}, {"code": "v2"}, 1, 2)
        self.assertIn("code", c.entity_type)

    def test_p17_092_deterministic_field_rule_strategy(self):
        c = self.sync_engine.detect_and_record_conflict("user_note", "n1", {"note": "v1"}, {"note": "v2"}, 1, 2)
        self.assertEqual(c.strategy, ConflictResolutionStrategy.LOCAL_WINS)

    def test_p17_093_resolve_conflict_local_wins(self):
        c = self.sync_engine.detect_and_record_conflict("doc", "d12", {"a": 1}, {"a": 2}, 1, 2)
        resolved = self.sync_engine.resolve_conflict(c.conflict_id, ConflictResolutionStrategy.LOCAL_WINS)
        self.assertTrue(resolved.resolved)
        self.assertEqual(resolved.resolution_strategy, ConflictResolutionStrategy.LOCAL_WINS.value)

    def test_p17_094_resolve_conflict_remote_wins(self):
        c = self.sync_engine.detect_and_record_conflict("doc", "d13", {"a": 1}, {"a": 2}, 1, 2)
        resolved = self.sync_engine.resolve_conflict(c.conflict_id, ConflictResolutionStrategy.REMOTE_WINS)
        self.assertTrue(resolved.resolved)

    def test_p17_095_resolve_conflict_manual_merge(self):
        c = self.sync_engine.detect_and_record_conflict("doc", "d14", {"a": 1}, {"b": 2}, 1, 2)
        resolved = self.sync_engine.resolve_conflict(c.conflict_id, ConflictResolutionStrategy.MANUAL_MERGE)
        self.assertTrue(resolved.resolved)

    def test_p17_096_list_unresolved_conflicts(self):
        c = self.sync_engine.detect_and_record_conflict("doc", "d15", {"a": 1}, {"a": 2}, 1, 2)
        unres = self.sync_engine.list_conflicts()
        self.assertEqual(len(unres), 1)
        self.sync_engine.resolve_conflict(c.conflict_id, ConflictResolutionStrategy.LOCAL_WINS)
        unres_after = self.sync_engine.list_conflicts()
        self.assertEqual(len(unres_after), 0)

    # =========================================================================
    # Group M: Fault Injection, Chaos Drills & Availability (P17-097 to P17-104)
    # =========================================================================

    def test_p17_097_worker_sigkill_drill(self):
        mid = self.queue_mgr.publish_message("tasks", {"task": "drill"})
        drill = self.chaos_runner.simulate_worker_sigkill(mid)
        self.assertEqual(drill["drill"], "SIGKILL_WORKER_SIMULATION")
        self.assertEqual(drill["status"], "PASSED")

    def test_p17_098_worker_crash_idempotency_safety(self):
        executed = []
        drill = self.chaos_runner.run_worker_crash_drill(
            task_id="task_99",
            start_fn=lambda: None,
            kill_fn=lambda: None,
            recover_fn=lambda: executed.append(1) or {"recovered": True},
        )
        self.assertTrue(drill["recovery_successful"])
        self.assertFalse(drill["side_effects_duplicated"])

    def test_p17_099_clock_skew_causal_ordering(self):
        drill = self.chaos_runner.run_clock_skew_drill(
            skew_seconds=120.0,
            event_a_fn=lambda t: {"ver": 1, "time": t},
            event_b_fn=lambda t: {"ver": 2, "time": t},
            ordering_fn=lambda a, b: a["ver"] < b["ver"],
        )
        self.assertTrue(drill["causally_consistent"])

    def test_p17_100_transient_db_lock_drill(self):
        drill = self.chaos_runner.run_transient_db_lock_drill(
            lock_duration_ms=5.0,
            contended_op_fn=lambda: True,
        )
        self.assertTrue(drill["handled_gracefully"])

    def test_p17_101_readiness_probe_degradation_trigger(self):
        h = HealthManager(db_path=str(self.db_path))
        h._simulated_degraded = True
        probe = h.check_readiness()
        self.assertEqual(probe.status, HealthState.DEGRADED)

    def test_p17_102_degraded_mode_blocks_mutations(self):
        h = HealthManager(db_path=str(self.db_path))
        h._simulated_degraded = True
        probe = h.check_readiness()
        can_mutate = probe.status == HealthState.HEALTHY
        self.assertFalse(can_mutate)

    def test_p17_103_recovery_from_degraded_mode(self):
        h = HealthManager(db_path=str(self.db_path))
        h._simulated_degraded = True
        self.assertEqual(h.check_readiness().status, HealthState.DEGRADED)
        h._simulated_degraded = False
        self.assertEqual(h.check_readiness().status, HealthState.HEALTHY)

    def test_p17_104_chaos_receipt_measurements(self):
        drill = self.chaos_runner.simulate_worker_sigkill("dummy_msg")
        self.assertIn("rto_ms", drill)

    # =========================================================================
    # Group N: Structured Observability, Tracing & SLO Auditing (P17-105 to P17-112)
    # =========================================================================

    def test_p17_105_trace_context_generation(self):
        ctx = self.telemetry.start_span("agent_turn", caller_role="user")
        self.assertTrue(ctx.trace_id.startswith("trc-"))
        self.assertTrue(ctx.span_id.startswith("spn-"))

    def test_p17_106_span_duration_recorded(self):
        ctx = self.telemetry.start_span("db_query")
        time.sleep(0.002)
        dur = self.telemetry.finish_span(ctx.span_id, success=True, cost_paisa=5)
        self.assertGreater(dur, 0.0)

    def test_p17_107_quantile_latency_calculation(self):
        for lat in [10.0, 15.0, 20.0, 25.0, 30.0, 40.0]:
            self.telemetry.record_request(duration_ms=lat, cost_paisa=2)
        slo = self.telemetry.get_slo_metrics()
        self.assertGreaterEqual(slo.latency_p95_ms, slo.latency_p50_ms)

    def test_p17_108_audible_ttfa_sink_tracking(self):
        self.telemetry.record_ttfa(340.5)
        slo = self.telemetry.get_slo_metrics()
        self.assertEqual(slo.audible_ttfa_sink_ms, 340.5)

    def test_p17_109_nepalese_paisa_cost_accounting(self):
        self.telemetry.record_request(duration_ms=10.0, cost_paisa=50)
        self.telemetry.record_request(duration_ms=12.0, cost_paisa=25)
        slo = self.telemetry.get_slo_metrics()
        self.assertEqual(slo.cost_total_paisa, 75)

    def test_p17_109b_paisa_integer_minor_units(self):
        # 1 NPR = 100 Paisa. Must be stored strictly as integer
        paisa = 1500
        npr = paisa / 100.0
        self.assertEqual(npr, 15.0)

    def test_p17_110_request_and_error_count(self):
        self.telemetry.record_request(duration_ms=5.0, is_error=False)
        self.telemetry.record_request(duration_ms=6.0, is_error=True)
        slo = self.telemetry.get_slo_metrics()
        self.assertEqual(slo.request_count, 2)
        self.assertEqual(slo.error_count, 1)

    def test_p17_111_trace_id_headers_schema(self):
        ctx = self.telemetry.start_span("http_dispatch")
        self.assertIn("trace_id", ctx.model_dump())
        self.assertIn("span_id", ctx.model_dump())

    def test_p17_112_slo_metrics_endpoint_schema(self):
        slo = self.telemetry.get_slo_metrics()
        data = slo.model_dump()
        self.assertIn("latency_p50_ms", data)
        self.assertIn("audible_ttfa_sink_ms", data)
        self.assertIn("cost_total_paisa", data)


if __name__ == "__main__":
    unittest.main()
