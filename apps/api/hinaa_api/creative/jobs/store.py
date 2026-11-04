"""
HINAA OS — Phase 09: Persistent Creative Job Store
Safely persists jobs, tracks idempotency keys, and buffers SSE events across restarts.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from ..models import CreativeEvent, CreativeJobRecord, JobState

logger = logging.getLogger("hinaa.creative.jobs.store")


class PersistentJobStore:
    """Thread-safe persistent store for creative jobs and SSE events."""

    def __init__(self, storage_file: Optional[Path] = None) -> None:
        if storage_file is None:
            from ...config import DATA_DIR
            self.storage_file = DATA_DIR / "creative_jobs.json"
        else:
            self.storage_file = Path(storage_file)

        self._jobs: Dict[str, CreativeJobRecord] = {}
        self._idempotency_map: Dict[str, str] = {}  # key -> job_id
        self._events: Dict[str, List[CreativeEvent]] = {}  # job_id -> events
        self._lock = asyncio.Lock()
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Restores persisted jobs on startup."""
        if not self.storage_file.exists():
            return
        try:
            raw = self.storage_file.read_text(encoding="utf-8")
            data = json.loads(raw)
            for item in data:
                record = CreativeJobRecord.model_validate(item)
                self._jobs[record.job_id] = record
                if record.idempotency_key:
                    self._idempotency_map[f"{record.tenant_id}:{record.idempotency_key}"] = record.job_id
            logger.info("Restored %d creative jobs from persistent store.", len(self._jobs))
        except Exception as e:
            logger.warning("Failed to restore creative jobs from %s: %s", self.storage_file, e)

    def _save_to_disk_sync(self) -> None:
        """Serializes jobs to disk."""
        try:
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
            data = [j.model_dump() for j in self._jobs.values()]
            self.storage_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to save creative jobs: %s", e)

    async def put_job(self, record: CreativeJobRecord) -> None:
        async with self._lock:
            self._jobs[record.job_id] = record
            if record.idempotency_key:
                self._idempotency_map[f"{record.tenant_id}:{record.idempotency_key}"] = record.job_id
            self._save_to_disk_sync()

    async def get_job(self, job_id: str) -> Optional[CreativeJobRecord]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def find_by_idempotency_key(self, tenant_id: str, key: str) -> Optional[CreativeJobRecord]:
        async with self._lock:
            job_id = self._idempotency_map.get(f"{tenant_id}:{key}")
            if job_id:
                return self._jobs.get(job_id)
            return None

    async def list_jobs(self, tenant_id: str, limit: int = 50) -> List[CreativeJobRecord]:
        async with self._lock:
            matching = [j for j in self._jobs.values() if j.tenant_id == tenant_id]
            matching.sort(key=lambda j: j.created_at, reverse=True)
            return matching[:limit]

    async def append_event(self, event: CreativeEvent) -> None:
        async with self._lock:
            if event.job_id not in self._events:
                self._events[event.job_id] = []
            self._events[event.job_id].append(event)
            # Update job state if present
            job = self._jobs.get(event.job_id)
            if job:
                job.state = event.state
                job.progress_percent = event.progress_percent
                job.progress_label = event.label
                job.updated_at = event.timestamp
                self._save_to_disk_sync()

    async def get_events_since(self, job_id: str, last_sequence_id: int = 0) -> List[CreativeEvent]:
        async with self._lock:
            evs = self._events.get(job_id, [])
            return [e for e in evs if e.sequence_id > last_sequence_id]


persistent_creative_job_store = PersistentJobStore()
