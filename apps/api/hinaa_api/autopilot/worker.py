"""
HINAA OS — Phase 13: Background Autonomous Scheduler & Worker Pool
Coordinates durable cron/interval schedule evaluations, atomic CAS job claiming with fencing tokens,
heartbeat renewals, retry backoff with jitter, crash recovery, and graceful shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from .contracts import (
    Job,
    JobAttempt,
    JobStatus,
    MisfirePolicy,
    Notification,
    PermissionTier,
    Schedule,
    ScheduleType,
    SeverityLevel,
)
from .cron_parser import calculate_next_fire_time, resolve_misfire
from .governor import ResourceGovernor
from .security import AncestryApprovalVerifier, AutopilotScrubber, GrantScopeChecker
from .store import AutopilotStore, StaleFencingTokenError
from .workflows import WorkflowExecutor

logger = logging.getLogger(__name__)


class AutopilotWorker:
    """
    Autonomous worker node executing claimed background jobs with durable fencing leases.
    """

    def __init__(
        self,
        worker_id: str,
        store: AutopilotStore,
        governor: ResourceGovernor,
        agent_service: Optional[Any] = None,
        lease_duration_seconds: float = 30.0,
    ):
        self.worker_id = worker_id
        self.store = store
        self.governor = governor
        self.agent_service = agent_service
        self.lease_duration_seconds = lease_duration_seconds
        self._is_running = False
        self._active_tasks: List[asyncio.Task] = []

    async def execute_job(self, job: Job) -> JobStatus:
        """Execute a single claimed job with heartbeat leasing and error classification."""
        start_time = time.time()
        attempt_number = job.attempt_count + 1
        attempt_id = f"att-{job.job_id}-{attempt_number}"

        logger.info(f"Worker {self.worker_id} starting job {job.job_id} (attempt {attempt_number}, fencing token {job.fencing_token})")

        # 1. Update job to RUNNING
        job.status = JobStatus.RUNNING
        job.attempt_count = attempt_number
        self.store.save_job(job)

        attempt = JobAttempt(
            attempt_id=attempt_id,
            job_id=job.job_id,
            attempt_number=attempt_number,
            worker_id=self.worker_id,
            started_at_utc=start_time,
            status=JobStatus.RUNNING,
        )
        self.store.record_job_attempt(attempt)

        # 2. Check if job requires Tier C approval
        requires_approval = job.metadata.get("permission_tier") == "TIER_C" or any(
            t in job.metadata.get("allowed_tools", [])
            for t in ["simulate_nepali_payment", "execute_payment", "publish_post", "delete_database", "deploy_production"]
        )

        if requires_approval and not job.metadata.get("is_approved", False):
            # Must transition to WAITING_APPROVAL
            logger.info(f"Job {job.job_id} requires Tier C human authorization; halting in WAITING_APPROVAL")
            try:
                self.store.commit_job_terminal_status(
                    job_id=job.job_id,
                    fencing_token=job.fencing_token,
                    status=JobStatus.WAITING_APPROVAL,
                    error_message="Action requires signed Tier C human authorization",
                )
            except StaleFencingTokenError as e:
                logger.error(f"Fencing token stale on approval transition: {e}")
                return JobStatus.FAILED

            # Emit notification
            notif = Notification(
                notification_id=f"notif-{uuid.uuid4().hex[:10]}",
                tenant_id=job.tenant_id,
                user_id=job.owner_user_id,
                event_type="job.waiting_approval",
                title="Action Requires Approval",
                message=f"Autonomous job {job.job_id} is awaiting your authorization for consequential action.",
                job_id=job.job_id,
                schedule_id=job.schedule_id,
                severity=SeverityLevel.WARNING,
            )
            self.store.save_notification(notif)
            return JobStatus.WAITING_APPROVAL

        # 3. Reserve resource budget
        has_budget, b_msg = self.governor.check_and_reserve_budget(
            tenant_id=job.tenant_id,
            requested_tokens=min(job.budget_tokens, 50000),
            requested_paisa=min(job.budget_paisa, 10000),
        )
        if not has_budget:
            logger.warning(f"Job {job.job_id} halted: {b_msg}")
            self.store.commit_job_terminal_status(
                job_id=job.job_id,
                fencing_token=job.fencing_token,
                status=JobStatus.FAILED,
                error_message=f"Budget exceeded or concurrency ceiling hit: {b_msg}",
            )
            return JobStatus.FAILED

        # 4. Execute work
        error_msg: Optional[str] = None
        artifacts: List[Dict[str, Any]] = []
        exit_code: int = 0
        final_status = JobStatus.COMPLETED

        try:
            workflow_type = job.metadata.get("workflow_type")

            if workflow_type == "repo_health_monitor":
                target = job.metadata.get("target_path", ".")
                cmd = job.metadata.get("test_command")
                res = WorkflowExecutor.run_repo_health_monitor(target, test_command=cmd)
                exit_code = res.get("exit_code", 0)
                artifacts.append({"name": "repo_health_report.json", "path": res.get("report_file", "")})
                if exit_code != 0:
                    final_status = JobStatus.FAILED
                    error_msg = f"Repository health tests reported failures (exit code {exit_code})"

            elif workflow_type == "research_digest":
                topic = job.metadata.get("topic", "HINAA OS Autonomous Intelligence")
                urls = job.metadata.get("source_urls", ["https://en.wikipedia.org/wiki/Artificial_intelligence"])
                res = WorkflowExecutor.run_research_digest(topic, urls)
                artifacts.append({"name": "quarantine_candidate.json", "path": res.get("quarantine_file", "")})

            elif workflow_type == "service_health_watcher":
                res = WorkflowExecutor.run_service_health_watcher()
                if res.get("status") != "HEALTHY":
                    error_msg = "Some monitored services are offline or degraded"

            elif workflow_type == "project_continuation":
                cp = job.metadata.get("checkpoint_data", {})
                res = WorkflowExecutor.run_project_continuation(job.task_id, cp)

            else:
                # Default generic execution: coordinate with AgentOrchestrationService if present
                if self.agent_service:
                    task = self.agent_service.get_task(job.task_id)
                    if task:
                        run_res = self.agent_service.run_task(job.task_id)
                        exit_code = 0 if run_res.get("status") == "COMPLETED" else 1
                        if exit_code != 0:
                            final_status = JobStatus.FAILED
                            error_msg = run_res.get("error")
                else:
                    # Simulated execution
                    await asyncio.sleep(0.01)

            # Record usage
            self.governor.record_usage(
                tenant_id=job.tenant_id,
                tokens_consumed=5000,
                paisa_consumed=500,  # 5 NPR
                is_actual_provider=False,
            )

        except Exception as e:
            logger.exception(f"Unexpected error executing job {job.job_id}: {e}")
            final_status = JobStatus.FAILED
            exit_code = 1
            error_msg = str(e)
        finally:
            self.governor.release_job_slot(job.tenant_id)

        # 5. Handle retries if failed
        now = time.time()
        attempt.ended_at_utc = now
        attempt.status = final_status
        attempt.exit_code = exit_code
        attempt.error_details = AutopilotScrubber.scrub(error_msg or "")
        self.store.record_job_attempt(attempt)

        if final_status == JobStatus.FAILED and attempt_number < job.max_attempts:
            # Check if retryable
            is_retryable = not any(
                perm_err in (error_msg or "").lower()
                for perm_err in ["unauthorized", "prohibited", "revoked", "signature mismatch", "syntax error"]
            )
            if is_retryable:
                backoff = min(60.0, (2 ** attempt_number) + random.uniform(0.1, 1.0))
                logger.info(f"Job {job.job_id} failed; scheduling retry {attempt_number + 1} in {backoff:.2f}s")
                job.status = JobStatus.RETRY_PENDING
                job.scheduled_for_utc = now + backoff
                job.error_message = error_msg
                self.store.save_job(job)
                return JobStatus.RETRY_PENDING

        # 6. Commit final status verified with fencing token
        try:
            self.store.commit_job_terminal_status(
                job_id=job.job_id,
                fencing_token=job.fencing_token,
                status=final_status,
                error_message=AutopilotScrubber.scrub(error_msg or ""),
                artifacts=artifacts,
                consumed_tokens=5000,
                consumed_paisa=500,
            )
        except StaleFencingTokenError as e:
            logger.error(f"Fencing token commit failure for job {job.job_id}: {e}")
            return JobStatus.FAILED

        # 7. Record timings
        self.governor.record_job_timings(
            job_id=job.job_id,
            scheduled_for_utc=job.scheduled_for_utc,
            started_at_utc=start_time,
            completed_at_utc=now,
        )

        return final_status


class AutopilotScheduler:
    """
    Evaluates due schedules, creates ready jobs, and handles misfire/coalescing policies.
    """

    def __init__(
        self,
        store: AutopilotStore,
        governor: ResourceGovernor,
        worker: AutopilotWorker,
        tick_interval_seconds: float = 1.0,
    ):
        self.store = store
        self.governor = governor
        self.worker = worker
        self.tick_interval_seconds = tick_interval_seconds
        self._is_running = False
        self._task: Optional[asyncio.Task] = None

    async def tick_once(self) -> int:
        """Run a single evaluation cycle of due schedules and ready jobs."""
        now = time.time()
        due_schedules = self.store.list_due_schedules(now)
        jobs_created = 0

        for sched in due_schedules:
            # 1. Resolve misfire
            should_run, run_time = resolve_misfire(
                scheduled_for_utc=sched.next_fire_time_utc or now,
                now_utc=now,
                policy=sched.misfire_policy,
                interval_seconds=sched.interval_seconds,
            )

            if should_run:
                job_id = f"job-{uuid.uuid4().hex[:12]}"
                task_id = f"task-{uuid.uuid4().hex[:10]}"
                job = Job(
                    job_id=job_id,
                    schedule_id=sched.schedule_id,
                    tenant_id=sched.tenant_id,
                    owner_user_id=sched.owner_user_id,
                    task_id=task_id,
                    status=JobStatus.READY,
                    scheduled_for_utc=run_time,
                    ancestry=f"schedule:{sched.schedule_id}:{sched.task_template.ancestry}",
                    budget_tokens=sched.task_template.budget_tokens,
                    budget_paisa=sched.task_template.budget_paisa,
                    metadata={
                        **sched.task_template.metadata,
                        "permission_tier": sched.task_template.permission_tier.value,
                        "allowed_tools": sched.task_template.allowed_tools,
                        "goal": sched.task_template.goal,
                    },
                )
                self.store.save_job(job)
                jobs_created += 1

                # Update schedule run count and next fire time
                sched.run_count += 1
                if sched.schedule_type == ScheduleType.ONE_SHOT or (sched.max_runs and sched.run_count >= sched.max_runs):
                    sched.is_paused = True
                    sched.next_fire_time_utc = None
                else:
                    sched.next_fire_time_utc = calculate_next_fire_time(
                        schedule_type=sched.schedule_type,
                        cron_expr=sched.cron_expr,
                        interval_seconds=sched.interval_seconds,
                        timezone_name=sched.timezone,
                        ref_time_utc=now,
                    )
                sched.updated_at_utc = now
                self.store.save_schedule(sched)

                # Append event
                self.store.append_event(
                    event_id=f"evt-{uuid.uuid4().hex[:10]}",
                    tenant_id=sched.tenant_id,
                    event_type="schedule.fired",
                    payload={"schedule_id": sched.schedule_id, "job_id": job_id},
                    trace_id=job.trace_id,
                    job_id=job_id,
                    schedule_id=sched.schedule_id,
                )

        return jobs_created

    async def run_loop(self) -> None:
        self._is_running = True
        logger.info("AutopilotScheduler background loop started")
        while self._is_running:
            try:
                await self.tick_once()
                # Check for crashed / orphaned leases
                self.store.recover_orphaned_jobs(time.time())
            except Exception as e:
                logger.error(f"Error in scheduler tick: {e}")
            await asyncio.sleep(self.tick_interval_seconds)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run_loop(), name="hinaa-autopilot-scheduler")

    def stop(self) -> None:
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
