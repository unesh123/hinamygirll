"""
HINAA OS — Phase 13: Unified Persistent Autopilot Service
Central coordinator providing high-level management of schedules, durable jobs,
human approvals, resource governance, emergency stop kill switch, and health telemetry.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    AutopilotEvent,
    Job,
    JobAttempt,
    JobStatus,
    MisfirePolicy,
    Notification,
    PermissionGrant,
    PermissionTier,
    QuietHours,
    Schedule,
    ScheduleType,
    SeverityLevel,
    TaskTemplate,
)
from .cron_parser import (
    CronSyntaxError,
    ScheduleValidationError,
    calculate_next_fire_time,
    validate_schedule_params,
)
from .governor import ResourceGovernor
from .security import AncestryApprovalVerifier, AutopilotScrubber, GrantScopeChecker
from .store import AutopilotStore
from .worker import AutopilotScheduler, AutopilotWorker

logger = logging.getLogger(__name__)


class AutopilotService:
    def __init__(
        self,
        db_path: str = "hinaa_autopilot.db",
        agent_service: Optional[Any] = None,
    ):
        self.store = AutopilotStore(db_path=db_path)
        self.governor = ResourceGovernor()
        self.worker = AutopilotWorker(
            worker_id=f"worker-{uuid.uuid4().hex[:8]}",
            store=self.store,
            governor=self.governor,
            agent_service=agent_service,
        )
        self.scheduler = AutopilotScheduler(
            store=self.store,
            governor=self.governor,
            worker=self.worker,
        )
        self.quiet_hours = QuietHours(enabled=False)
        self._emergency_stopped_tenants: set[str] = set()

    # -------------------------------------------------------------------------
    # SCHEDULE MANAGEMENT
    # -------------------------------------------------------------------------
    def create_schedule(
        self,
        tenant_id: str,
        owner_user_id: str,
        name: str,
        schedule_type: ScheduleType,
        goal: str,
        cron_expr: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        timezone: str = "Asia/Kathmandu",
        permission_tier: PermissionTier = PermissionTier.TIER_A,
        budget_tokens: int = 100000,
        budget_paisa: int = 25000,
        allowed_tools: Optional[List[str]] = None,
        allowed_domains: Optional[List[str]] = None,
        repo_whitelist: Optional[List[str]] = None,
        misfire_policy: MisfirePolicy = MisfirePolicy.COALESCE,
        max_runs: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Schedule:
        """Create a new validated, durable autonomous schedule."""
        # 1. Idempotency Check
        if idempotency_key:
            existing = self.store.get_schedule_by_idempotency_key(tenant_id, idempotency_key)
            if existing:
                return existing

        # 2. Validate Parameters
        validate_schedule_params(
            schedule_type=schedule_type,
            cron_expr=cron_expr,
            interval_seconds=interval_seconds,
            timezone_name=timezone,
        )

        now = time.time()
        next_fire = calculate_next_fire_time(
            schedule_type=schedule_type,
            cron_expr=cron_expr,
            interval_seconds=interval_seconds,
            timezone_name=timezone,
            ref_time_utc=now,
        )

        schedule_id = f"sch-{uuid.uuid4().hex[:12]}"
        template = TaskTemplate(
            goal=goal,
            permission_tier=permission_tier,
            budget_tokens=budget_tokens,
            budget_paisa=budget_paisa,
            allowed_tools=allowed_tools or [],
            allowed_domains=allowed_domains or [],
            repo_whitelist=repo_whitelist or [],
            ancestry=f"sch:{schedule_id}",
            metadata=metadata or {},
        )

        schedule = Schedule(
            schedule_id=schedule_id,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            name=name,
            description=metadata.get("description", "") if metadata else "",
            schedule_type=schedule_type,
            task_template=template,
            cron_expr=cron_expr,
            interval_seconds=interval_seconds,
            timezone=timezone,
            start_time_utc=now,
            misfire_policy=misfire_policy,
            max_runs=max_runs,
            idempotency_key=idempotency_key,
            created_at_utc=now,
            updated_at_utc=now,
            next_fire_time_utc=next_fire,
            metadata=metadata or {},
        )

        self.store.save_schedule(schedule)
        self.store.append_event(
            event_id=f"evt-{uuid.uuid4().hex[:10]}",
            tenant_id=tenant_id,
            event_type="schedule.created",
            payload={"schedule_id": schedule_id, "name": name, "next_fire_time_utc": next_fire},
            trace_id=f"trc-{uuid.uuid4().hex[:8]}",
            schedule_id=schedule_id,
        )
        return schedule

    def get_schedule(self, schedule_id: str) -> Optional[Schedule]:
        return self.store.get_schedule(schedule_id)

    def list_schedules(self, tenant_id: str, include_paused: bool = True) -> List[Schedule]:
        return self.store.list_schedules(tenant_id, include_paused=include_paused)

    def pause_schedule(self, schedule_id: str) -> bool:
        sched = self.store.get_schedule(schedule_id)
        if not sched:
            return False
        sched.is_paused = True
        sched.updated_at_utc = time.time()
        self.store.save_schedule(sched)
        return True

    def resume_schedule(self, schedule_id: str) -> bool:
        sched = self.store.get_schedule(schedule_id)
        if not sched:
            return False
        if sched.tenant_id in self._emergency_stopped_tenants:
            raise PermissionError("Tenant is under emergency stop; resume blocked")
        sched.is_paused = False
        now = time.time()
        sched.next_fire_time_utc = calculate_next_fire_time(
            schedule_type=sched.schedule_type,
            cron_expr=sched.cron_expr,
            interval_seconds=sched.interval_seconds,
            timezone_name=sched.timezone,
            ref_time_utc=now,
        )
        sched.updated_at_utc = now
        self.store.save_schedule(sched)
        return True

    def delete_schedule(self, schedule_id: str) -> bool:
        return self.store.delete_schedule(schedule_id)

    # -------------------------------------------------------------------------
    # JOB MANAGEMENT
    # -------------------------------------------------------------------------
    def create_job(
        self,
        tenant_id: str,
        owner_user_id: str,
        goal: str,
        schedule_id: Optional[str] = None,
        permission_tier: PermissionTier = PermissionTier.TIER_A,
        budget_tokens: int = 100000,
        budget_paisa: int = 25000,
        allowed_tools: Optional[List[str]] = None,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Job:
        """Create an on-demand ready job in the persistent queue."""
        if tenant_id in self._emergency_stopped_tenants:
            raise PermissionError("Tenant is under emergency stop; job creation blocked")

        if idempotency_key:
            existing = self.store.get_job_by_idempotency_key(tenant_id, idempotency_key)
            if existing:
                return existing

        now = time.time()
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        task_id = f"task-{uuid.uuid4().hex[:10]}"
        ancestry = f"job:{job_id}"
        if schedule_id:
            ancestry = f"schedule:{schedule_id}:{ancestry}"

        job = Job(
            job_id=job_id,
            schedule_id=schedule_id,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            task_id=task_id,
            status=JobStatus.READY,
            scheduled_for_utc=now,
            ancestry=ancestry,
            budget_tokens=budget_tokens,
            budget_paisa=budget_paisa,
            idempotency_key=idempotency_key,
            metadata={
                **(metadata or {}),
                "goal": goal,
                "permission_tier": permission_tier.value,
                "allowed_tools": allowed_tools or [],
            },
        )
        self.store.save_job(job)
        self.store.append_event(
            event_id=f"evt-{uuid.uuid4().hex[:10]}",
            tenant_id=tenant_id,
            event_type="job.created",
            payload={"job_id": job_id, "goal": goal, "permission_tier": permission_tier.value},
            trace_id=job.trace_id,
            job_id=job_id,
            schedule_id=schedule_id,
        )
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self.store.get_job(job_id)

    def list_jobs(self, tenant_id: str, limit: int = 100, status: Optional[JobStatus] = None) -> List[Job]:
        return self.store.list_jobs(tenant_id, limit=limit, status=status)

    def cancel_job(self, job_id: str, reason: str = "Cancelled by user") -> bool:
        job = self.store.get_job(job_id)
        if not job or job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return False

        job.status = JobStatus.CANCELLED
        job.error_message = reason
        job.completed_at_utc = time.time()
        self.store.save_job(job)
        return True

    def retry_job(self, job_id: str) -> bool:
        job = self.store.get_job(job_id)
        if not job:
            return False
        job.status = JobStatus.READY
        job.scheduled_for_utc = time.time()
        job.error_message = None
        self.store.save_job(job)
        return True

    # -------------------------------------------------------------------------
    # APPROVALS (TIER C)
    # -------------------------------------------------------------------------
    def approve_action(
        self,
        job_id: str,
        signature: str,
        action: str,
        arg_digest: str,
        amount_paisa: int,
        nonce: str,
        expires_at: float,
        team_id: str = "main",
    ) -> Tuple[bool, str]:
        job = self.store.get_job(job_id)
        if not job:
            return False, f"Job {job_id} not found"

        if job.status != JobStatus.WAITING_APPROVAL:
            return False, f"Job {job_id} is in status {job.status.value}, not WAITING_APPROVAL"

        # Verify ancestry signature
        is_valid, msg = AncestryApprovalVerifier.verify_signature(
            signature=signature,
            ancestry=job.ancestry,
            tenant_id=job.tenant_id,
            user_id=job.owner_user_id,
            team_id=team_id,
            job_id=job_id,
            action=action,
            arg_digest=arg_digest,
            amount_paisa=amount_paisa,
            nonce=nonce,
            expires_at=expires_at,
        )

        if not is_valid:
            return False, f"Signature rejected: {msg}"

        # Transition to READY with approval mark
        job.status = JobStatus.READY
        job.metadata["is_approved"] = True
        job.metadata["approved_action"] = action
        job.metadata["approved_amount_paisa"] = amount_paisa
        self.store.save_job(job)

        self.store.append_event(
            event_id=f"evt-{uuid.uuid4().hex[:10]}",
            tenant_id=job.tenant_id,
            event_type="job.approved",
            payload={"job_id": job_id, "action": action, "amount_paisa": amount_paisa},
            trace_id=job.trace_id,
            job_id=job_id,
        )
        return True, "Action approved and job resumed"

    # -------------------------------------------------------------------------
    # EMERGENCY STOP / KILL SWITCH
    # -------------------------------------------------------------------------
    def emergency_stop(self, tenant_id: str) -> Dict[str, Any]:
        """Global kill switch: immediately pauses all schedules and halts queued jobs."""
        self._emergency_stopped_tenants.add(tenant_id)
        schedules = self.store.list_schedules(tenant_id, include_paused=False)
        paused_count = 0
        for s in schedules:
            s.is_paused = True
            self.store.save_schedule(s)
            paused_count += 1

        jobs = self.store.list_jobs(tenant_id, status=JobStatus.READY)
        cancelled_count = 0
        for j in jobs:
            j.status = JobStatus.CANCELLED
            j.error_message = "Cancelled by Emergency Stop Kill Switch"
            self.store.save_job(j)
            cancelled_count += 1

        logger.warning(f"EMERGENCY STOP engaged for tenant {tenant_id}: {paused_count} schedules paused, {cancelled_count} jobs cancelled")
        return {
            "tenant_id": tenant_id,
            "is_stopped": True,
            "paused_schedules": paused_count,
            "cancelled_jobs": cancelled_count,
            "timestamp_utc": time.time(),
        }

    def revoke_emergency_stop(self, tenant_id: str) -> bool:
        if tenant_id in self._emergency_stopped_tenants:
            self._emergency_stopped_tenants.remove(tenant_id)
            return True
        return False

    # -------------------------------------------------------------------------
    # NOTIFICATIONS & EVENTS
    # -------------------------------------------------------------------------
    def list_notifications(self, tenant_id: str, user_id: str, limit: int = 50, unread_only: bool = False) -> List[Notification]:
        return self.store.list_notifications(tenant_id, user_id, limit=limit, unread_only=unread_only)

    def mark_notifications_read(self, tenant_id: str, user_id: str, notification_ids: Optional[List[str]] = None) -> int:
        return self.store.mark_notifications_read(tenant_id, user_id, notification_ids=notification_ids)

    def get_events(self, tenant_id: str, since_sequence: int = 0, limit: int = 100) -> List[AutopilotEvent]:
        return self.store.get_events(tenant_id, since_sequence=since_sequence, limit=limit)

    # -------------------------------------------------------------------------
    # HEALTH & TELEMETRY
    # -------------------------------------------------------------------------
    def get_health(self) -> Dict[str, Any]:
        latencies = self.governor.get_latency_stats()
        return {
            "scheduler_alive": self.scheduler._is_running,
            "worker_alive": True,
            "gpu_vram_allocated_mb": self.governor.used_gpu_vram_mb,
            "gpu_vram_max_mb": self.governor.max_gpu_vram_mb,
            "active_browsers": self.governor.active_browsers,
            "active_sandboxes": self.governor.active_sandboxes,
            "latencies": latencies,
            "status": "HEALTHY",
            "timestamp_utc": time.time(),
        }


# Global singleton instance
autopilot_service = AutopilotService()
