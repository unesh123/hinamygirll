from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

JobStatus = Literal["queued", "submitted", "processing", "completed", "failed"]


@dataclass
class CreativeJob:
    id: str
    prompt: str
    model_id: str
    cost_credits: int
    status: JobStatus = "queued"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    image_url: str | None = None
    remote_job_id: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "modelId": self.model_id,
            "costCredits": self.cost_credits,
            "status": self.status,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "imageUrl": self.image_url,
            "remoteJobId": self.remote_job_id,
            "error": self.error,
            "metadata": self.metadata,
        }


class CreativeJobStore:
    """Thread-safe store for async creative jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, CreativeJob] = {}
        self._lock = asyncio.Lock()

    async def create_job(
        self,
        prompt: str,
        model_id: str,
        cost_credits: int,
        metadata: dict[str, Any] | None = None,
    ) -> CreativeJob:
        job_id = str(uuid4())
        job = CreativeJob(
            id=job_id,
            prompt=prompt,
            model_id=model_id,
            cost_credits=cost_credits,
            metadata=metadata or {},
        )
        async with self._lock:
            self._jobs[job_id] = job
        return job

    async def get_job(self, job_id: str) -> CreativeJob | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        image_url: str | None = None,
        remote_job_id: str | None = None,
        error: str | None = None,
    ) -> CreativeJob | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if status is not None:
                job.status = status
            if image_url is not None:
                job.image_url = image_url
            if remote_job_id is not None:
                job.remote_job_id = remote_job_id
            if error is not None:
                job.error = error
            job.updated_at = datetime.now(timezone.utc)
            return job

    async def list_jobs(self, limit: int = 20) -> list[CreativeJob]:
        async with self._lock:
            sorted_jobs = sorted(
                self._jobs.values(),
                key=lambda j: j.created_at,
                reverse=True,
            )
            return sorted_jobs[:limit]