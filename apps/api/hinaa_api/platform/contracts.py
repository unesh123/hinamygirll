"""
HINAA OS — Phase 17 Production Hardening, Edge Distribution & High Availability Contracts.

Defines schemas, deployment profiles, verification statuses, and data models for:
- Multi-environment configurations and capability validation.
- Health probes (/health/live, /health/ready, /health/startup, /health/dependencies).
- Redis Streams outbox/inbox with SQLite durable queue fallback.
- Online hot backups and deterministic restore rehearsals.
- Zero-leak offline edge synchronization with cryptographic peer pairing.
- Distributed traces, SLO performance metrics, and cost accounting.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# --- Deployment & Verification Topologies ---

class DeploymentProfile(str, Enum):
    LOCAL_DESKTOP = "LOCAL_DESKTOP"      # Local Windows 11 / WSL2 laptop, SQLite WAL, single GPU
    LOCAL_LAN = "LOCAL_LAN"              # Multi-device home LAN / local collaboration
    CLOUD_STAGING = "CLOUD_STAGING"      # Single/multi-instance Linux container on staging
    CLOUD_PRODUCTION = "CLOUD_PRODUCTION"  # Hardened multi-tenant production cluster


class VerificationStatus(str, Enum):
    LOCAL_VERIFIED = "LOCAL_VERIFIED"
    MULTI_PROCESS_SAME_HOST_VERIFIED = "MULTI_PROCESS_SAME_HOST_VERIFIED"
    MULTI_HOST_VERIFIED = "MULTI_HOST_VERIFIED"
    CONFIG_REQUIRED = "CONFIG_REQUIRED"
    BLOCKED_UNAVAILABLE = "BLOCKED_UNAVAILABLE"
    CONTAINER_BUILD_BLOCKED = "CONTAINER_BUILD_BLOCKED"
    NOT_TESTED = "NOT_TESTED"


class HealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    STARTING = "STARTING"


class QueueBackendType(str, Enum):
    SQLITE_DURABLE = "SQLITE_DURABLE"
    REDIS_STREAMS = "REDIS_STREAMS"


class SyncPeerStatus(str, Enum):
    ACTIVE = "PAIRED"
    PAIRED = "PAIRED"
    PAIRING_PENDING = "PAIRING_PENDING"
    REVOKED = "REVOKED"
    BLOCKED = "BLOCKED"


class ConflictResolutionStrategy(str, Enum):
    LOCAL_WINS = "DETERMINISTIC_FIELD_RULE"
    REMOTE_WINS = "TOMBSTONE_PRECEDENCE"
    MANUAL_MERGE = "STRUCTURED_HUMAN_REVIEW"
    DETERMINISTIC_FIELD_RULE = "DETERMINISTIC_FIELD_RULE"
    STRUCTURED_HUMAN_REVIEW = "STRUCTURED_HUMAN_REVIEW"
    TOMBSTONE_PRECEDENCE = "TOMBSTONE_PRECEDENCE"


# --- Probes & Health Schemas ---

class ProbeResponse(BaseModel):
    status: HealthState
    timestamp: float = Field(default_factory=time.time)
    service: str = "hinaa_os"
    version: str = "17.0.0"
    deployment_profile: DeploymentProfile = DeploymentProfile.LOCAL_DESKTOP
    details: Dict[str, Any] = Field(default_factory=dict)


class DetailedDependencyHealth(BaseModel):
    overall_status: HealthState
    timestamp: float = Field(default_factory=time.time)
    deployment_profile: DeploymentProfile
    sqlite_status: HealthState
    redis_status: HealthState
    gpu_status: HealthState
    queue_status: HealthState
    sync_status: HealthState
    dependencies: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


# --- Queue & Exactly-Once Delivery Schemas ---

class OutboxEntry(BaseModel):
    message_id: str
    operation_key: str  # Unique idempotency key (tenant + action + nonce)
    topic: str
    payload: Dict[str, Any]
    status: str = "PENDING"  # PENDING, IN_FLIGHT, COMMITTED, DEAD_LETTER
    retry_count: int = 0
    max_retries: int = 3
    created_at: float = Field(default_factory=time.time)
    dispatched_at: Optional[float] = None
    committed_at: Optional[float] = None


class DLQEntry(BaseModel):
    dlq_id: str
    operation_key: str
    topic: str
    payload: Dict[str, Any]
    failure_reason: str
    retry_count: int
    dead_lettered_at: float = Field(default_factory=time.time)
    replayed_at: Optional[float] = None


# --- Persistence, Backup & Restore Schemas ---

class BackupReceipt(BaseModel):
    backup_id: str
    source_db: str
    backup_path: str
    row_count: int
    checksum_sha256: str
    integrity_ok: bool
    duration_ms: float
    created_at: float = Field(default_factory=time.time)
    wal_checkpointed: bool = True
    size_bytes: int = 0
    tables_included: List[str] = Field(default_factory=list)

    @property
    def integrity_passed(self) -> bool:
        return self.integrity_ok


class RestoreReceipt(BaseModel):
    restore_id: str
    backup_id: str
    target_db: str
    recovered_tables: List[str]
    integrity_ok: bool
    rpo_seconds: float  # Recovery Point Objective (age of snapshot)
    rto_ms: float       # Recovery Time Objective (duration to restore)
    restored_at: float = Field(default_factory=time.time)
    tables_verified: int = 0
    rto_seconds: float = 0.0


# --- Edge Sync & Device Pairing Schemas ---

class PairedDevice(BaseModel):
    device_id: str
    device_name: str
    public_key_fingerprint: str
    paired_at: float = Field(default_factory=time.time)
    status: SyncPeerStatus = SyncPeerStatus.PAIRED
    last_sync_watermark: int = 0
    allowed_tenants: List[str] = Field(default_factory=lambda: ["default"])
    is_same_host_simulation: bool = False
    tenant_id: str = "default"


class SyncConflict(BaseModel):
    conflict_id: str
    record_id: str = ""
    record_type: str = "document"  # "document", "knowledge_graph", "code", "permission"
    entity_type: str = "document"
    entity_id: str = ""
    local_version: int = 1
    remote_version: int = 1
    local_data: Dict[str, Any] = Field(default_factory=dict)
    remote_data: Dict[str, Any] = Field(default_factory=dict)
    local_payload: Dict[str, Any] = Field(default_factory=dict)
    remote_payload: Dict[str, Any] = Field(default_factory=dict)
    strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.LOCAL_WINS
    detected_at: float = Field(default_factory=time.time)
    resolved: bool = False
    resolution_strategy: Optional[str] = None


class SyncManifest(BaseModel):
    manifest_id: str
    origin_device_id: str
    target_device_id: str
    watermark_start: int
    watermark_end: int
    records: List[Dict[str, Any]]
    generated_at: float = Field(default_factory=time.time)


# --- Observability & SLO Performance Metrics ---

class SLOMetrics(BaseModel):
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    audible_ttfa_sink_ms: float
    cost_total_paisa: int
    request_count: int
    error_count: int
    timestamp: float = Field(default_factory=time.time)
