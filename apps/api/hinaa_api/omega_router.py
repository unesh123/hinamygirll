"""Omega Router: Endpoints for Autonomous Heartbeat, Terminal Hands, VIP College Vault, and SaaS Bridges.

Provides enterprise-grade production REST and SSE APIs for:
- Autonomous Heartbeat Daemon status, manual ticks, and live SSE event stream
- Sandboxed Terminal Hands shell execution with security guardrails
- VIP Deep Vault & College platform registration, gated resource lookup, and admin analytics
- Unified Enterprise SaaS integration statuses (GitHub, Outlook, Google Calendar, Notion, Spotify)
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .intelligence.heartbeat import heartbeat_daemon, HeartbeatPulse
from .college.vault import (
    college_vault_service,
    StudentRegistrationRequest,
    VIPResourceItem,
)
from .integrations.saas_bridge import saas_bridge_manager, SaaSIntegrationStatus
from .tools.terminal_hands import execute_terminal_hands, TerminalExecuteParams

logger = logging.getLogger("hinaa.omega_router")

omega_router = APIRouter(tags=["Omega Super-Pillars"])


# ─────────────────────────────────────────────────────────────────────────────
# 1. Autonomous Heartbeat Daemon & Proactive Stream
# ─────────────────────────────────────────────────────────────────────────────

@omega_router.get("/v1/heartbeat/status")
@omega_router.get("/api/v1/heartbeat/status")
async def get_heartbeat_status() -> Dict[str, Any]:
    """Return live status of the autonomous background heartbeat daemon."""
    return heartbeat_daemon.status


@omega_router.post("/v1/heartbeat/tick")
@omega_router.post("/api/v1/heartbeat/tick")
async def force_heartbeat_tick() -> Dict[str, Any]:
    """Force an immediate heartbeat tick to evaluate background tasks and proactivity."""
    pulse = await heartbeat_daemon.force_tick()
    return {
        "status": "success",
        "tickTriggered": True,
        "pulseEmitted": pulse.model_dump() if pulse else None,
    }


@omega_router.get("/v1/heartbeat/pulses")
@omega_router.get("/api/v1/heartbeat/pulses")
async def list_recent_pulses(limit: int = 15) -> Dict[str, Any]:
    """Return recent proactive heartbeat pulses for the companion notification center."""
    pulses = heartbeat_daemon.get_recent_pulses(limit=min(limit, 50))
    return {
        "pulses": [p.model_dump() for p in pulses],
        "total": len(pulses),
    }


@omega_router.post("/v1/heartbeat/acknowledge/{pulse_id}")
@omega_router.post("/api/v1/heartbeat/acknowledge/{pulse_id}")
async def acknowledge_heartbeat_pulse(pulse_id: str) -> Dict[str, Any]:
    """Mark a proactive heartbeat pulse as read/acknowledged."""
    ok = heartbeat_daemon.acknowledge_pulse(pulse_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Pulse not found")
    return {"status": "success", "acknowledged": True}


@omega_router.get("/v1/heartbeat/events:stream")
@omega_router.get("/api/v1/heartbeat/events:stream")
async def stream_heartbeat_events(request: Request) -> StreamingResponse:
    """Server-Sent Events (SSE) stream for real-time proactive heartbeat notifications."""
    queue = heartbeat_daemon.subscribe()

    async def event_generator():
        try:
            # Yield initial connection heartbeat
            initial_event = {
                "type": "heartbeat_connected",
                "status": "online",
                "daemon": heartbeat_daemon.status,
            }
            yield f"data: {json.dumps(initial_event)}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    pulse: HeartbeatPulse = await asyncio.wait_for(queue.get(), timeout=20.0)
                    payload = {"type": "pulse", "data": pulse.model_dump()}
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive SSE comment
                    yield ": ping\n\n"
        finally:
            heartbeat_daemon.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Terminal Hands & Code Execution Sandbox
# ─────────────────────────────────────────────────────────────────────────────

class TerminalRunRequest(BaseModel):
    command: str = Field(..., description="The shell command or script to execute")
    cwd: Optional[str] = Field(default=None, description="Working directory relative to project root")
    timeout_seconds: int = Field(default=30, ge=1, le=120, description="Max execution timeout in seconds")


@omega_router.post("/v1/terminal/execute")
@omega_router.post("/api/v1/terminal/execute")
async def execute_terminal_command(body: TerminalRunRequest) -> Dict[str, Any]:
    """Execute a sandboxed shell command or test suite with safety guardrails."""
    result = await execute_terminal_hands(
        TerminalExecuteParams(
            command=body.command,
            cwd=body.cwd,
            timeout_seconds=body.timeout_seconds,
        )
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 3. VIP Deep Vault & College Platform Engine ("DIP World")
# ─────────────────────────────────────────────────────────────────────────────

@omega_router.post("/v1/college/register", status_code=201)
@omega_router.post("/api/v1/college/register", status_code=201)
async def register_student(req: StudentRegistrationRequest) -> Dict[str, Any]:
    """Verify college student identity and grant VIP Deep Vault access."""
    return college_vault_service.register_student(req)


@omega_router.get("/v1/college/verify/{student_id}")
@omega_router.get("/api/v1/college/verify/{student_id}")
async def verify_student(student_id: str) -> Dict[str, Any]:
    """Check enrollment status of a student ID."""
    student = college_vault_service.verify_student(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student ID not found in institutional directory")
    return {"status": "verified", "student": student}


@omega_router.get("/v1/college/resources")
@omega_router.get("/api/v1/college/resources")
async def list_college_resources(category: Optional[str] = None) -> Dict[str, Any]:
    """List curated VIP Deep Vault resources across cybersecurity, AI scripts, videos, and syllabus."""
    items = college_vault_service.list_vip_resources(category=category)
    return {
        "resources": items,
        "total": len(items),
        "categories": ["cybersecurity", "python_ai_scripts", "lecture_videos", "academic_syllabus", "research_dossiers"],
    }


@omega_router.get("/v1/college/resources/{resource_id}")
@omega_router.get("/api/v1/college/resources/{resource_id}")
async def get_college_resource(resource_id: str) -> Dict[str, Any]:
    """Retrieve full content and download links for a specific VIP resource."""
    item = college_vault_service.get_resource_by_id(resource_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"VIP resource '{resource_id}' not found")
    return {"resource": item}


@omega_router.get("/v1/college/admin/stats")
@omega_router.get("/api/v1/college/admin/stats")
async def get_college_admin_stats() -> Dict[str, Any]:
    """Analytics dashboard for college faculty and administrators."""
    return college_vault_service.get_admin_dashboard_stats()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Unified Enterprise SaaS Bridges
# ─────────────────────────────────────────────────────────────────────────────

@omega_router.get("/v1/integrations/status")
@omega_router.get("/api/v1/integrations/status")
async def get_integrations_status() -> Dict[str, Any]:
    """Return live connection status for GitHub, Outlook, Calendar, Notion, and Spotify."""
    services = saas_bridge_manager.get_all_statuses()
    return {
        "integrations": [s.model_dump() for s in services],
        "total": len(services),
    }


class GitHubActionRequest(BaseModel):
    action: str = Field(..., description="Action: status, branch, log, diff")
    params: Optional[Dict[str, Any]] = None


@omega_router.post("/v1/integrations/github/action")
@omega_router.post("/api/v1/integrations/github/action")
async def execute_github_action(body: GitHubActionRequest) -> Dict[str, Any]:
    """Execute rapid repository inspect or branch action."""
    return await saas_bridge_manager.execute_github_quick_action(body.action, body.params)


class OutlookSendRequest(BaseModel):
    recipient: str
    subject: str
    body: str
    send_now: bool = False


@omega_router.post("/v1/integrations/email/send")
@omega_router.post("/api/v1/integrations/email/send")
async def send_outlook_email(body: OutlookSendRequest) -> Dict[str, Any]:
    """Draft or deliver institutional Outlook / Office 365 email."""
    return await saas_bridge_manager.send_outlook_email(
        recipient=body.recipient,
        subject=body.subject,
        body=body.body,
        send_now=body.send_now,
    )


@omega_router.get("/v1/integrations/agenda")
@omega_router.get("/api/v1/integrations/agenda")
async def get_today_agenda() -> Dict[str, Any]:
    """Return daily engineering schedule and academic timetable."""
    agenda = saas_bridge_manager.get_todays_agenda()
    return {"agenda": agenda, "count": len(agenda)}
