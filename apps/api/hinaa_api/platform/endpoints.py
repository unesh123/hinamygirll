"""
HINAA OS — Phase 17 Platform, Probes & Edge Sync FastAPI Endpoints.

Mounts:
- /health/live, /health/ready, /health/startup, /health/dependencies
- /api/platform/profile
- /api/platform/queue/*
- /api/platform/backup/*
- /api/platform/sync/*
- /api/platform/slo
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel

from hinaa_api.platform.backup import BackupManager
from hinaa_api.platform.config_schema import load_environment_config
from hinaa_api.platform.contracts import (
    BackupReceipt,
    DetailedDependencyHealth,
    DLQEntry,
    OutboxEntry,
    PairedDevice,
    ProbeResponse,
    RestoreReceipt,
    SLOMetrics,
    SyncConflict,
)
from hinaa_api.platform.health import get_health_manager
from hinaa_api.platform.metrics import get_telemetry_collector
from hinaa_api.platform.queue import DurableQueueManager
from hinaa_api.platform.sync import EdgeSyncEngine

platform_router = APIRouter(tags=["Platform & Production Hardening"])
health_router = APIRouter(tags=["Health & Probes"])

_queue_manager = DurableQueueManager()
_backup_manager = BackupManager()
_sync_engine = EdgeSyncEngine()


# --- Probes ---

@health_router.get("/health/live", response_model=ProbeResponse)
def get_liveness():
    return get_health_manager().check_liveness()


@health_router.get("/health/ready", response_model=ProbeResponse)
def get_readiness():
    resp = get_health_manager().check_readiness()
    if resp.status.value in ("UNHEALTHY", "STARTING"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=resp.model_dump())
    return resp


@health_router.get("/health/startup", response_model=ProbeResponse)
def get_startup():
    resp = get_health_manager().check_startup()
    if resp.status.value in ("UNHEALTHY", "STARTING"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=resp.model_dump())
    return resp


@health_router.get("/health/dependencies", response_model=DetailedDependencyHealth)
def get_dependencies(authorization: Optional[str] = Header(None)):
    # P17-021: Unauthenticated clients cannot inspect internal diagnostics
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to inspect detailed dependencies diagnostics.",
        )
    role = "operator" if "operator" in authorization.lower() or "admin" in authorization.lower() else "user"
    try:
        return get_health_manager().check_dependencies(caller_role=role)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# --- Platform Profile & Telemetry ---

@platform_router.get("/api/platform/profile")
def get_deployment_profile():
    cfg = load_environment_config()
    return {
        "deployment_profile": cfg.deployment_profile.value,
        "verification_status": cfg.get_verification_status().value,
        "offline_mode": cfg.offline_mode,
        "tls_enabled": cfg.tls_enabled,
        "debug": cfg.debug,
        "enable_gpu": cfg.enable_gpu,
        "queue_backend": _queue_manager.backend_type.value,
    }


@platform_router.get("/api/platform/slo", response_model=SLOMetrics)
def get_slo():
    return get_telemetry_collector().get_slo_metrics()


# --- Queue & DLQ Endpoints ---

@platform_router.get("/api/platform/queue/status")
def get_queue_status():
    pending = _queue_manager.get_pending_messages(limit=100)
    dlq = _queue_manager.list_dlq()
    return {
        "backend": _queue_manager.backend_type.value,
        "pending_count": len(pending),
        "dlq_count": len(dlq),
        "status": "HEALTHY",
    }


@platform_router.get("/api/platform/queue/dlq", response_model=List[DLQEntry])
def list_dlq_entries():
    return _queue_manager.list_dlq()


class ReplayDLQRequest(BaseModel):
    dlq_id: str


@platform_router.post("/api/platform/queue/replay")
def replay_dlq_entry(req: ReplayDLQRequest):
    success = _queue_manager.replay_dlq(req.dlq_id)
    if not success:
        raise HTTPException(status_code=404, detail="DLQ entry not found")
    return {"replayed": True, "dlq_id": req.dlq_id}


# --- Backup & Restore Endpoints ---

class BackupRequest(BaseModel):
    source_db: Optional[str] = None


@platform_router.post("/api/platform/backup/create", response_model=BackupReceipt)
def create_backup(req: BackupRequest):
    src = req.source_db or os.environ.get("HINAA_AUTOPILOT_DB", "hinaa_autopilot.db")
    try:
        return _backup_manager.create_hot_backup(src)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hot backup failed: {str(e)}")


class RestoreRequest(BaseModel):
    backup_path: str
    target_db: str


@platform_router.post("/api/platform/backup/restore", response_model=RestoreReceipt)
def restore_backup(req: RestoreRequest):
    try:
        return _backup_manager.restore_backup(req.backup_path, req.target_db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")


# --- Edge Sync & Pairing Endpoints ---

@platform_router.get("/api/platform/sync/devices", response_model=List[PairedDevice])
def list_devices():
    with _sync_engine._lock:
        with _sync_engine._get_conn() as conn:
            cur = conn.execute("SELECT * FROM platform_paired_devices;")
            devices = []
            for r in cur.fetchall():
                import json
                from hinaa_api.platform.contracts import SyncPeerStatus
                devices.append(
                    PairedDevice(
                        device_id=r["device_id"],
                        device_name=r["device_name"],
                        public_key_fingerprint=r["public_key_fingerprint"],
                        paired_at=r["paired_at"],
                        status=SyncPeerStatus(r["status"]),
                        last_sync_watermark=r["last_sync_watermark"],
                        allowed_tenants=json.loads(r["allowed_tenants_json"]),
                        is_same_host_simulation=bool(r["is_same_host_simulation"]),
                    )
                )
            return devices


class PairDeviceRequest(BaseModel):
    device_id: str
    device_name: str
    public_key_fingerprint: str
    allowed_tenants: Optional[List[str]] = None
    is_same_host_simulation: bool = False


@platform_router.post("/api/platform/sync/pair", response_model=PairedDevice)
def pair_device(req: PairDeviceRequest):
    return _sync_engine.pair_device(
        device_id=req.device_id,
        device_name=req.device_name,
        public_key_fingerprint=req.public_key_fingerprint,
        allowed_tenants=req.allowed_tenants,
        is_same_host_simulation=req.is_same_host_simulation,
    )


class RevokeDeviceRequest(BaseModel):
    device_id: str


@platform_router.post("/api/platform/sync/revoke")
def revoke_device(req: RevokeDeviceRequest):
    revoked = _sync_engine.revoke_device(req.device_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"revoked": True, "device_id": req.device_id}


@platform_router.get("/api/platform/sync/conflicts", response_model=List[SyncConflict])
def list_conflicts():
    return _sync_engine.list_conflicts()


class ResolveConflictRequest(BaseModel):
    conflict_id: str
    winner: str  # "local", "remote", "merged"


@platform_router.post("/api/platform/sync/resolve")
def resolve_conflict(req: ResolveConflictRequest):
    if req.winner not in ("local", "remote", "merged"):
        raise HTTPException(status_code=400, detail="Invalid winner choice; must be 'local', 'remote', or 'merged'")
    resolved = _sync_engine.resolve_conflict(req.conflict_id, req.winner)
    if not resolved:
        raise HTTPException(status_code=404, detail="Conflict not found")
    return {"resolved": True, "conflict_id": req.conflict_id, "winner": req.winner}
