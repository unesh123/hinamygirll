"""
HINAA OS - Autopilot and Persistent Background Operations Router.
Phase 13: Schedules, Jobs, Human Approvals, Emergency Stop, and Events.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..autopilot import autopilot_service, ScheduleType, PermissionTier, MisfirePolicy

logger = logging.getLogger("hinaa.routers.autopilot")

router = APIRouter(tags=["Autopilot"])

# =========================================================================
# PHASE 13 — AUTOPILOT & PERSISTENT BACKGROUND OPERATIONS
# =========================================================================

@router.post("/api/autopilot/schedules")
async def create_autopilot_schedule(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
    
    name = body.get("name")
    goal = body.get("goal")
    schedule_type_str = body.get("schedule_type", "INTERVAL")
    if not name or not goal:
        return JSONResponse({"error": "Fields 'name' and 'goal' are required"}, status_code=400)

    tenant_id = body.get("tenant_id", "default")
    user_id = body.get("user_id", "user-default")
    cron_expr = body.get("cron_expr")
    interval_seconds = body.get("interval_seconds")
    timezone = body.get("timezone", "Asia/Kathmandu")
    tier_str = body.get("permission_tier", "TIER_A")
    try:
        stype = ScheduleType(schedule_type_str)
    except Exception:
        return JSONResponse({"error": f"Invalid schedule_type: {schedule_type_str}"}, status_code=400)
    try:
        tier = PermissionTier(tier_str)
    except Exception:
        tier = PermissionTier.TIER_A

    try:
        sched = autopilot_service.create_schedule(
            tenant_id=tenant_id,
            owner_user_id=user_id,
            name=name,
            schedule_type=stype,
            goal=goal,
            cron_expr=cron_expr,
            interval_seconds=interval_seconds,
            timezone=timezone,
            permission_tier=tier,
            budget_tokens=body.get("budget_tokens", 100000),
            budget_paisa=body.get("budget_paisa", 25000),
            allowed_tools=body.get("allowed_tools"),
            allowed_domains=body.get("allowed_domains"),
            repo_whitelist=body.get("repo_whitelist"),
            misfire_policy=MisfirePolicy(body.get("misfire_policy", "COALESCE")),
            max_runs=body.get("max_runs"),
            idempotency_key=body.get("idempotency_key"),
            metadata=body.get("metadata"),
        )
        return JSONResponse({"schedule": sched.to_dict()})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

@router.get("/api/autopilot/schedules")
async def list_autopilot_schedules(request: Request, tenant_id: str = "default"):
    schedules = autopilot_service.list_schedules(tenant_id=tenant_id)
    return JSONResponse({"schedules": [s.to_dict() for s in schedules]})

@router.get("/api/autopilot/schedules/{schedule_id}")
async def get_autopilot_schedule(schedule_id: str):
    sched = autopilot_service.get_schedule(schedule_id)
    if not sched:
        return JSONResponse({"error": f"Schedule {schedule_id} not found"}, status_code=404)
    return JSONResponse({"schedule": sched.to_dict()})

@router.post("/api/autopilot/schedules/{schedule_id}/pause")
async def pause_autopilot_schedule(schedule_id: str):
    ok = autopilot_service.pause_schedule(schedule_id)
    if not ok:
        return JSONResponse({"error": f"Schedule {schedule_id} not found"}, status_code=404)
    return JSONResponse({"status": "PAUSED", "schedule_id": schedule_id})

@router.post("/api/autopilot/schedules/{schedule_id}/resume")
async def resume_autopilot_schedule(schedule_id: str):
    try:
        ok = autopilot_service.resume_schedule(schedule_id)
        if not ok:
            return JSONResponse({"error": f"Schedule {schedule_id} not found"}, status_code=404)
        return JSONResponse({"status": "RESUMED", "schedule_id": schedule_id})
    except PermissionError as pe:
        return JSONResponse({"error": str(pe)}, status_code=403)

@router.delete("/api/autopilot/schedules/{schedule_id}")
async def delete_autopilot_schedule(schedule_id: str):
    ok = autopilot_service.delete_schedule(schedule_id)
    if not ok:
        return JSONResponse({"error": f"Schedule {schedule_id} not found"}, status_code=404)
    return JSONResponse({"status": "DELETED", "schedule_id": schedule_id})

@router.post("/api/autopilot/jobs")
async def create_autopilot_job(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
    goal = body.get("goal")
    if not goal:
        return JSONResponse({"error": "Field 'goal' is required"}, status_code=400)
    tenant_id = body.get("tenant_id", "default")
    user_id = body.get("user_id", "user-default")
    tier_str = body.get("permission_tier", "TIER_A")
    try:
        tier = PermissionTier(tier_str)
    except Exception:
        tier = PermissionTier.TIER_A
    try:
        job = autopilot_service.create_job(
            tenant_id=tenant_id,
            owner_user_id=user_id,
            goal=goal,
            schedule_id=body.get("schedule_id"),
            permission_tier=tier,
            budget_tokens=body.get("budget_tokens", 100000),
            budget_paisa=body.get("budget_paisa", 25000),
            allowed_tools=body.get("allowed_tools"),
            idempotency_key=body.get("idempotency_key"),
            metadata=body.get("metadata"),
        )
        return JSONResponse({"job": job.to_dict()})
    except PermissionError as pe:
        return JSONResponse({"error": str(pe)}, status_code=403)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

@router.get("/api/autopilot/jobs")
async def list_autopilot_jobs(tenant_id: str = "default", limit: int = 100):
    jobs = autopilot_service.list_jobs(tenant_id=tenant_id, limit=limit)
    return JSONResponse({"jobs": [j.to_dict() for j in jobs]})

@router.get("/api/autopilot/jobs/{job_id}")
async def get_autopilot_job(job_id: str):
    job = autopilot_service.get_job(job_id)
    if not job:
        return JSONResponse({"error": f"Job {job_id} not found"}, status_code=404)
    return JSONResponse({"job": job.to_dict()})

@router.post("/api/autopilot/jobs/{job_id}/cancel")
async def cancel_autopilot_job(job_id: str, request: Request):
    try:
        body = await request.json()
        reason = body.get("reason", "Cancelled by user")
    except Exception:
        reason = "Cancelled by user"
    ok = autopilot_service.cancel_job(job_id, reason=reason)
    if not ok:
        return JSONResponse({"error": f"Job {job_id} cannot be cancelled or not found"}, status_code=400)
    return JSONResponse({"status": "CANCELLED", "job_id": job_id})

@router.post("/api/autopilot/jobs/{job_id}/retry")
async def retry_autopilot_job(job_id: str):
    ok = autopilot_service.retry_job(job_id)
    if not ok:
        return JSONResponse({"error": f"Job {job_id} not found"}, status_code=404)
    return JSONResponse({"status": "READY", "job_id": job_id})

@router.post("/api/autopilot/approvals/{job_id}/decide")
async def decide_autopilot_approval(job_id: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
    approved = body.get("approved", False)
    if not approved:
        autopilot_service.cancel_job(job_id, reason="Rejected by user")
        return JSONResponse({"status": "REJECTED", "job_id": job_id})

    signature = body.get("signature", "")
    action = body.get("action", "")
    arg_digest = body.get("arg_digest", "")
    amount_paisa = body.get("amount_paisa", 0)
    nonce = body.get("nonce", "")
    expires_at = body.get("expires_at", time.time() + 300)

    ok, msg = autopilot_service.approve_action(
        job_id=job_id,
        signature=signature,
        action=action,
        arg_digest=arg_digest,
        amount_paisa=amount_paisa,
        nonce=nonce,
        expires_at=expires_at,
    )
    if not ok:
        return JSONResponse({"error": msg}, status_code=400)
    return JSONResponse({"status": "APPROVED", "job_id": job_id, "message": msg})

@router.post("/api/autopilot/emergency-stop")
async def trigger_emergency_stop(request: Request):
    try:
        body = await request.json()
        tenant_id = body.get("tenant_id", "default")
    except Exception:
        tenant_id = "default"
    res = autopilot_service.emergency_stop(tenant_id)
    return JSONResponse(res)

@router.post("/api/autopilot/emergency-stop/revoke")
async def revoke_emergency_stop(request: Request):
    try:
        body = await request.json()
        tenant_id = body.get("tenant_id", "default")
    except Exception:
        tenant_id = "default"
    ok = autopilot_service.revoke_emergency_stop(tenant_id)
    return JSONResponse({"tenant_id": tenant_id, "revoked": ok})

@router.get("/api/autopilot/notifications")
async def list_autopilot_notifications(tenant_id: str = "default", user_id: str = "user-default", unread_only: bool = False):
    notifs = autopilot_service.list_notifications(tenant_id, user_id, unread_only=unread_only)
    return JSONResponse({"notifications": [n.to_dict() for n in notifs]})

@router.post("/api/autopilot/notifications/mark-read")
async def mark_autopilot_notifications_read(request: Request):
    try:
        body = await request.json()
        tenant_id = body.get("tenant_id", "default")
        user_id = body.get("user_id", "user-default")
        ids = body.get("notification_ids")
    except Exception:
        tenant_id = "default"
        user_id = "user-default"
        ids = None
    count = autopilot_service.mark_notifications_read(tenant_id, user_id, ids)
    return JSONResponse({"marked_read_count": count})

@router.get("/api/autopilot/events")
async def get_autopilot_events(tenant_id: str = "default", since_sequence: int = 0):
    events = autopilot_service.get_events(tenant_id, since_sequence=since_sequence)
    return JSONResponse({"events": [e.to_dict() for e in events]})

@router.get("/api/autopilot/health")
async def get_autopilot_health():
    health = autopilot_service.get_health()
    return JSONResponse(health)

