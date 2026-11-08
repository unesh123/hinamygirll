"""Lyric-video job lifecycle: async submit, progress, cancel, asset storage."""
# ruff: noqa: E501

from __future__ import annotations

import asyncio
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ...errors import HinaaError
from ..assets.manager import creative_asset_manager
from ..models import CreativeOperation, JobState
from ..policy import CreativeSecurityPolicy
from .renderer import RenderCancelled, render_lyric_video
from .spec import LyricVideoSpec

MAX_RETAINED_JOBS = 200


@dataclass
class LyricVideoJob:
    job_id: str
    tenant_id: str
    user_id: str
    spec: LyricVideoSpec
    state: JobState = JobState.QUEUED
    progress_percent: float = 0.0
    progress_label: str = "Queued"
    error: str | None = None
    asset: dict[str, Any] | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    render_seconds: float | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id, "tenant_id": self.tenant_id, "state": self.state.value,
            "progress_percent": round(self.progress_percent, 1), "progress_label": self.progress_label,
            "error": self.error, "asset": self.asset, "title": self.spec.title, "aspect": self.spec.aspect,
            "draft": self.spec.draft, "created_at": self.created_at, "completed_at": self.completed_at,
            "render_seconds": self.render_seconds,
        }


def _inside(path: str, roots: list[Path]) -> bool:
    p = Path(path).resolve()
    return any(p == r or r in p.parents for r in roots)


class LyricVideoService:
    def __init__(self, allowed_roots: list[Path] | None = None) -> None:
        self._jobs: dict[str, LyricVideoJob] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._allowed_roots = allowed_roots

    def _roots(self) -> list[Path]:
        if self._allowed_roots is not None:
            return [r.resolve() for r in self._allowed_roots]
        from ...config import DATA_DIR

        return [Path(DATA_DIR).resolve(), creative_asset_manager.storage_root.resolve()]

    def _check_paths(self, spec: LyricVideoSpec) -> None:
        for label, value in (("audio_path", spec.audio_path), ("character_image", spec.character_image)):
            if value and not _inside(value, self._roots()):
                raise HinaaError(
                    "LYRIC_VIDEO_PATH_FORBIDDEN",
                    f"{label} must be inside the Hinaa data or creative assets directory.",
                    status_code=403,
                )

    def get(self, job_id: str, tenant_id: str) -> LyricVideoJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise HinaaError("LYRIC_VIDEO_JOB_NOT_FOUND", f"Lyric video job '{job_id}' not found.", status_code=404)
        CreativeSecurityPolicy.verify_tenant_access(tenant_id, job.tenant_id)
        return job

    async def submit(self, spec: LyricVideoSpec, tenant_id: str = "default_tenant", user_id: str = "default_user") -> LyricVideoJob:
        self._check_paths(spec)
        job = LyricVideoJob(job_id=f"job-lv-{uuid.uuid4().hex[:8]}", tenant_id=tenant_id, user_id=user_id, spec=spec)
        self._jobs[job.job_id] = job
        for old in [j for j in self._jobs.values() if j.state not in (JobState.QUEUED, JobState.RUNNING)][:-MAX_RETAINED_JOBS]:
            self._jobs.pop(old.job_id, None)
        self._tasks[job.job_id] = asyncio.create_task(self._run(job))
        return job

    async def cancel(self, job_id: str, tenant_id: str) -> LyricVideoJob:
        job = self.get(job_id, tenant_id)
        if job.state in (JobState.QUEUED, JobState.RUNNING):
            job.cancel_event.set()
            job.progress_label = "Cancelling"
        return job

    async def wait(self, job_id: str) -> None:
        task = self._tasks.get(job_id)
        if task:
            await asyncio.shield(task)

    async def _run(self, job: LyricVideoJob) -> None:
        started = time.monotonic()

        def on_progress(pct: float, label: str) -> None:
            job.progress_percent, job.progress_label = pct, label

        try:
            job.state = JobState.RUNNING
            tmp_dir = creative_asset_manager.storage_root / job.tenant_id / ".lyric_tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=tmp_dir) as work:
                out = Path(work) / f"{job.job_id}.mp4"
                result = await asyncio.to_thread(render_lyric_video, job.spec, out, on_progress, job.cancel_event)
                job.state = JobState.VALIDATING
                meta = creative_asset_manager.store_asset(
                    data=out.read_bytes(), filename=f"lyric_video_{job.job_id}.mp4",
                    operation=CreativeOperation.TIMELINE_EXPORT, provider="lyric_video_html",
                    model_version="html-frame-clock-v1", tenant_id=job.tenant_id, user_id=job.user_id,
                    prompt="; ".join(line["text"] for line in result["lines"])[:500],
                    duration_seconds=result["duration"], fps=float(result["fps"]), codec="h264",
                )
            meta.width, meta.height = result["width"], result["height"]
            job.asset = meta.model_dump(mode="json")
            job.state, job.progress_percent, job.progress_label = JobState.COMPLETED, 100.0, "Complete"
        except RenderCancelled:
            job.state, job.progress_label = JobState.CANCELLED, "Cancelled"
        except Exception as exc:  # surfaced on the job record, not raised into the loop
            job.state, job.error, job.progress_label = JobState.FAILED, str(exc)[:500], "Failed"
        finally:
            job.render_seconds = round(time.monotonic() - started, 1)
            job.completed_at = datetime.now(UTC).isoformat()
            self._tasks.pop(job.job_id, None)


lyric_video_service = LyricVideoService()
