"""
HINAA OS — Phase 09: Creative Service & Job Orchestrator
Coordinates multi-modal task execution, admission control, telemetry, and event streaming.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List, Optional

from ..assets.manager import creative_asset_manager
from ..models import (
    CapabilityStatus,
    CreativeEvent,
    CreativeJobRecord,
    CreativeJobSpec,
    CreativeOperation,
    JobState,
    MediaType,
)
from ..policy import CreativeSecurityPolicy
from ..providers.comfy_provider import comfyui_provider
from ..providers.local_engine import local_creative_engine
from ..providers.timeline_exporter import timeline_video_exporter
from ..providers.video_generative_provider import generative_video_provider
from ..registry import creative_registry
from .store import persistent_creative_job_store


class CreativeService:
    """End-to-end orchestrator for creative jobs, telemetry, and asset delivery."""

    def __init__(self) -> None:
        self.store = persistent_creative_job_store
        self.asset_mgr = creative_asset_manager
        self.registry = creative_registry
        self._running_tasks: Dict[str, asyncio.Task] = {}

    def _next_event(
        self,
        job_id: str,
        seq: int,
        state: JobState,
        pct: float,
        label: str,
        details: Optional[Dict] = None,
    ) -> CreativeEvent:
        return CreativeEvent(
            event_id=f"evt-{uuid.uuid4().hex[:8]}",
            job_id=job_id,
            sequence_id=seq,
            timestamp=datetime.now(timezone.utc).isoformat(),
            state=state,
            progress_percent=pct,
            label=label,
            details=details or {},
        )

    async def submit_job(self, spec: CreativeJobSpec) -> CreativeJobRecord:
        """Validates and registers a new creative job, enforcing idempotency."""
        # 1. Defang prompt
        spec.prompt = CreativeSecurityPolicy.defang_prompt(spec.prompt)
        if spec.prompt_ne:
            spec.prompt_ne = CreativeSecurityPolicy.defang_prompt(spec.prompt_ne)

        # 2. Policy validation
        CreativeSecurityPolicy.validate_job_spec(spec)

        # 3. Check idempotency
        if spec.idempotency_key:
            existing = await self.store.find_by_idempotency_key(spec.tenant_id, spec.idempotency_key)
            if existing:
                return existing

        # 4. Resolve capability status
        matrix = self.registry.matrix
        cap_entry = matrix.capabilities.get(spec.operation)
        if not cap_entry:
            raise ValueError(f"Unknown creative operation: {spec.operation}")

        job_id = f"job-cr-{uuid.uuid4().hex[:8]}"
        trace_id = f"trace-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        job = CreativeJobRecord(
            job_id=job_id,
            tenant_id=spec.tenant_id,
            user_id=spec.user_id,
            trace_id=trace_id,
            idempotency_key=spec.idempotency_key,
            spec=spec,
            state=JobState.QUEUED,
            provider=cap_entry.provider,
            created_at=now_iso,
            updated_at=now_iso,
            progress_percent=0.0,
            progress_label="Job queued",
        )

        await self.store.put_job(job)
        await self.store.append_event(self._next_event(job_id, 1, JobState.QUEUED, 0.0, "Job received in queue"))

        # If operation is BLOCKED, fail immediately with diagnostic record
        if cap_entry.status in (CapabilityStatus.BLOCKED, CapabilityStatus.UNAVAILABLE):
            job.state = JobState.BLOCKED_UNAVAILABLE
            job.error_reason = (
                f"Operation '{spec.operation.value}' is currently {cap_entry.status.value}: "
                f"{cap_entry.description_en}"
            )
            job.error_code = "CAPABILITY_BLOCKED"
            job.completed_at = datetime.now(timezone.utc).isoformat()
            await self.store.put_job(job)
            await self.store.append_event(
                self._next_event(
                    job_id,
                    2,
                    JobState.BLOCKED_UNAVAILABLE,
                    0.0,
                    f"Blocked: {cap_entry.status.value}",
                    {"reason": job.error_reason},
                )
            )
            return job

        # Spawn asynchronous execution task
        t = asyncio.create_task(self._execute_job_pipeline(job))
        self._running_tasks[job_id] = t
        return job

    async def _execute_job_pipeline(self, job: CreativeJobRecord) -> None:
        """Executes the stages of creative generation, encoding, and validation."""
        start_time = time.time()
        job_id = job.job_id
        seq = 2

        try:
            # Stage 1: PREPARING
            job.state = JobState.PREPARING
            job.started_at = datetime.now(timezone.utc).isoformat()
            await self.store.append_event(
                self._next_event(job_id, seq, JobState.PREPARING, 10.0, "Preparing resources and inputs")
            )
            seq += 1

            # Stage 2: RUNNING
            job.state = JobState.RUNNING
            await self.store.append_event(
                self._next_event(job_id, seq, JobState.RUNNING, 30.0, f"Running generation via {job.provider}")
            )
            seq += 1

            op = job.spec.operation
            out_bytes: bytes

            if op == CreativeOperation.TEXT_TO_IMAGE:
                out_bytes = await local_creative_engine.execute_job(job)
            elif op == CreativeOperation.IMAGE_TO_IMAGE:
                out_bytes = await local_creative_engine.execute_job(job)
            elif op == CreativeOperation.INPAINT:
                # Retrieve source image and mask bytes from asset manager
                src_bytes = self.asset_mgr.get_asset_bytes(job.spec.source_asset_id, job.tenant_id)
                mask_bytes = self.asset_mgr.get_asset_bytes(job.spec.mask_asset_id, job.tenant_id)
                if not src_bytes or not mask_bytes:
                    raise FileNotFoundError("Source image or mask asset could not be located for inpainting.")
                out_bytes = local_creative_engine.inpaint_image(src_bytes, mask_bytes)
            elif op == CreativeOperation.REMOVE_BACKGROUND:
                src_bytes = self.asset_mgr.get_asset_bytes(job.spec.source_asset_id, job.tenant_id)
                if not src_bytes:
                    raise FileNotFoundError("Source asset not found for background removal.")
                out_bytes = local_creative_engine.remove_background(src_bytes)
            elif op == CreativeOperation.TIMELINE_EXPORT:
                job.state = JobState.ENCODING
                await self.store.append_event(
                    self._next_event(job_id, seq, JobState.ENCODING, 60.0, "Encoding video frames via FFmpeg")
                )
                seq += 1
                out_bytes, probe = await timeline_video_exporter.render_timeline_to_mp4(
                    frame_images=[],
                    width=job.spec.width,
                    height=job.spec.height,
                    fps=job.spec.fps,
                    title=job.spec.prompt,
                )
                job.telemetry["ffmpeg_probe"] = probe
            else:
                raise NotImplementedError(f"Operation {op} execution handler not implemented.")

            # Stage 3: VALIDATING
            job.state = JobState.VALIDATING
            await self.store.append_event(
                self._next_event(job_id, seq, JobState.VALIDATING, 85.0, "Validating output raster and headers")
            )
            seq += 1

            if len(out_bytes) == 0:
                raise ValueError("Engine produced 0-byte corrupt media output.")

            # Stage 4: STORE ASSET
            is_video = (op == CreativeOperation.TIMELINE_EXPORT)
            ext = ".mp4" if is_video else ".png"
            filename = f"gen_{job_id}{ext}"

            meta = self.asset_mgr.store_asset(
                data=out_bytes,
                filename=filename,
                operation=op,
                provider=job.provider,
                model_version="1.0",
                tenant_id=job.tenant_id,
                user_id=job.user_id,
                prompt=job.spec.prompt,
                prompt_ne=job.spec.prompt_ne,
                seed=job.spec.seed,
                parent_asset_id=job.spec.source_asset_id,
                duration_seconds=job.spec.duration_seconds if is_video else None,
                fps=job.spec.fps if is_video else None,
            )

            # Stage 5: COMPLETED
            duration_ms = int((time.time() - start_time) * 1000)
            job.state = JobState.COMPLETED
            job.completed_at = datetime.now(timezone.utc).isoformat()
            job.output_asset_ids.append(meta.asset_id)
            job.output_assets.append(meta)
            job.telemetry["duration_ms"] = duration_ms
            job.telemetry["output_sha256"] = meta.sha256_hash

            await self.store.put_job(job)
            await self.store.append_event(
                self._next_event(
                    job_id,
                    seq,
                    JobState.COMPLETED,
                    100.0,
                    "Generation completed successfully",
                    {"asset_id": meta.asset_id, "sha256": meta.sha256_hash, "duration_ms": duration_ms},
                )
            )

        except asyncio.CancelledError:
            job.state = JobState.CANCELLED
            job.error_reason = "Job was cancelled by user."
            job.completed_at = datetime.now(timezone.utc).isoformat()
            await self.store.put_job(job)
            await self.store.append_event(
                self._next_event(job_id, seq, JobState.CANCELLED, job.progress_percent, "Job cancelled by user")
            )
        except Exception as exc:
            job.state = JobState.FAILED
            job.error_reason = str(exc)
            job.error_code = "GENERATION_ERROR"
            job.completed_at = datetime.now(timezone.utc).isoformat()
            await self.store.put_job(job)
            await self.store.append_event(
                self._next_event(
                    job_id,
                    seq,
                    JobState.FAILED,
                    job.progress_percent,
                    f"Job failed: {exc}",
                    {"error": str(exc)},
                )
            )
        finally:
            self._running_tasks.pop(job_id, None)

    async def cancel_job(self, job_id: str, tenant_id: str) -> CreativeJobRecord:
        """Idempotently cancels an active or queued job."""
        job = await self.store.get_job(job_id)
        if not job:
            raise KeyError(f"Job {job_id} not found.")
        CreativeSecurityPolicy.verify_tenant_access(tenant_id, job.tenant_id)

        if job.state in (JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED, JobState.BLOCKED_UNAVAILABLE):
            return job

        task = self._running_tasks.get(job_id)
        if task and not task.done():
            task.cancel()

        job.state = JobState.CANCELLED
        job.error_reason = "Job was cancelled by user request."
        job.completed_at = datetime.now(timezone.utc).isoformat()
        await self.store.put_job(job)
        await self.store.append_event(
            self._next_event(job_id, 999, JobState.CANCELLED, job.progress_percent, "Job cancelled")
        )
        return job

    async def retry_job(self, job_id: str, tenant_id: str) -> CreativeJobRecord:
        """Safely retries a failed or cancelled job respecting original budget and specs."""
        job = await self.store.get_job(job_id)
        if not job:
            raise KeyError(f"Job {job_id} not found.")
        CreativeSecurityPolicy.verify_tenant_access(tenant_id, job.tenant_id)

        if job.retry_count >= job.max_retries:
            raise RuntimeError(f"Job {job_id} has exceeded maximum allowed retries ({job.max_retries}).")

        new_spec = job.spec.model_copy()
        new_spec.idempotency_key = f"retry-{job_id}-{job.retry_count + 1}"
        new_job = await self.submit_job(new_spec)
        new_job.retry_count = job.retry_count + 1
        await self.store.put_job(new_job)
        return new_job

    async def stream_events(self, job_id: str, tenant_id: str) -> AsyncGenerator[str, None]:
        """Streams SSE events with monotonic sequence IDs and re-connection support."""
        job = await self.store.get_job(job_id)
        if not job:
            return
        CreativeSecurityPolicy.verify_tenant_access(tenant_id, job.tenant_id)

        last_seq = 0
        while True:
            events = await self.store.get_events_since(job_id, last_seq)
            for ev in events:
                last_seq = ev.sequence_id
                data_json = ev.model_dump_json()
                yield f"id: {ev.sequence_id}\nevent: creative_event\ndata: {data_json}\n\n"

            job = await self.store.get_job(job_id)
            if job and job.state in (
                JobState.COMPLETED,
                JobState.FAILED,
                JobState.CANCELLED,
                JobState.BLOCKED_UNAVAILABLE,
                JobState.TIMED_OUT,
            ):
                break
            await asyncio.sleep(0.5)


creative_service = CreativeService()
