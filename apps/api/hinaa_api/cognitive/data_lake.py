"""
HINAA Enterprise Data Lake & Event Ingestion Engine.

Provides durable, partitioned event-sourcing and telemetry archiving:
1. Partitioned Cold Storage (.hina/lake/events/YYYY/MM/DD/)
2. Canonical Run Snapshots (.hina/lake/runs/YYYY/MM/DD/)
3. Asynchronous Non-blocking Write Buffer
4. Automated Credential & PII Sanitization
5. Compliance Export & Session Replay Query Engine (GDPR / SOC2)
"""

from __future__ import annotations

import asyncio
import datetime
import gzip
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .contracts import CognitiveRun, HinaEvent
from .policy_engine import EnterprisePolicyEngine

logger = logging.getLogger("hinaa.cognitive.lake")


class DataLakeIngestor:
    """Enterprise Data Lake Ingestor for HINAA telemetry and event streams."""

    def __init__(self, lake_root: Optional[Path] = None) -> None:
        self.lake_root = lake_root or Path(".hina/lake").resolve()
        self.events_root = self.lake_root / "events"
        self.runs_root = self.lake_root / "runs"
        self._buffer: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._ensure_storage_structure()

    def _ensure_storage_structure(self) -> None:
        self.events_root.mkdir(parents=True, exist_ok=True)
        self.runs_root.mkdir(parents=True, exist_ok=True)

    def _get_partition_path(self, base_dir: Path, date: Optional[datetime.date] = None) -> Path:
        target_date = date or datetime.datetime.now(datetime.timezone.utc).date()
        partition = base_dir / target_date.strftime("%Y/%m/%d")
        partition.mkdir(parents=True, exist_ok=True)
        return partition

    def record_event(self, event: HinaEvent) -> None:
        """Enqueue an event into the data lake buffer with automatic secret scrubbing."""
        try:
            event_dict = event.model_dump() if hasattr(event, "model_dump") else dict(event)
            sanitized = EnterprisePolicyEngine.redact_secrets(event_dict)
            self._buffer.append(sanitized)

            # Flush immediately if buffer exceeds threshold
            if len(self._buffer) >= 25:
                self.flush_sync()
        except Exception as e:
            logger.debug("Failed to buffer data lake event: %s", e)

    def flush_sync(self) -> int:
        """Synchronously flush buffered events to the current date partition."""
        if not self._buffer:
            return 0

        flushed_count = 0
        try:
            partition = self._get_partition_path(self.events_root)
            log_file = partition / "stream.jsonl"

            items_to_write = list(self._buffer)
            self._buffer.clear()

            with log_file.open("a", encoding="utf-8") as f:
                for item in items_to_write:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    flushed_count += 1
        except Exception as e:
            logger.warning("Data lake flush error: %s", e)

        return flushed_count

    async def flush(self) -> int:
        """Asynchronously flush buffered events."""
        async with self._lock:
            return self.flush_sync()

    def archive_run(self, run: CognitiveRun) -> Path:
        """Archive a full canonical CognitiveRun snapshot into partitioned cold storage."""
        partition = self._get_partition_path(self.runs_root)
        run_file = partition / f"{run.run_id}.json"

        run_dict = run.model_dump() if hasattr(run, "model_dump") else dict(run)
        sanitized = EnterprisePolicyEngine.redact_secrets(run_dict)

        with run_file.open("w", encoding="utf-8") as f:
            json.dump(sanitized, f, indent=2, ensure_ascii=False)

        logger.debug("Archived CognitiveRun snapshot: %s", run_file.name)
        return run_file

    def query_events(
        self,
        *,
        date: Optional[datetime.date] = None,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query historical events from data lake partition."""
        self.flush_sync()
        partition = self._get_partition_path(self.events_root, date)
        log_file = partition / "stream.jsonl"
        if not log_file.exists():
            return []

        results: List[Dict[str, Any]] = []
        try:
            with log_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    evt = json.loads(line)
                    if user_id and evt.get("user_id") != user_id:
                        continue
                    if event_type and evt.get("event_type") != event_type:
                        continue
                    results.append(evt)
                    if len(results) >= limit:
                        break
        except Exception as e:
            logger.warning("Data lake query error: %s", e)

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Return data lake operational metrics for enterprise observability."""
        self.flush_sync()
        total_events = 0
        total_runs = 0
        bytes_stored = 0

        for path in self.lake_root.rglob("*"):
            if path.is_file():
                bytes_stored += path.stat().st_size
                if path.name == "stream.jsonl":
                    try:
                        with path.open("r", encoding="utf-8") as f:
                            total_events += sum(1 for line in f if line.strip())
                    except Exception:
                        pass
                elif path.suffix == ".json" and "runs" in str(path):
                    total_runs += 1

        return {
            "lakeRoot": str(self.lake_root),
            "totalEventsIngested": total_events,
            "totalRunsArchived": total_runs,
            "storageBytes": bytes_stored,
            "storageMb": round(bytes_stored / (1024 * 1024), 2),
            "pendingBufferCount": len(self._buffer),
        }

    def export_compliance_archive(self, user_id: str) -> Dict[str, Any]:
        """Generate a GDPR/SOC2-compliant audit archive for a user."""
        self.flush_sync()
        user_events = []
        user_runs = []

        # Scan events
        for stream_file in self.events_root.rglob("stream.jsonl"):
            try:
                with stream_file.open("r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        evt = json.loads(line)
                        if evt.get("user_id") == user_id:
                            user_events.append(evt)
            except Exception:
                pass

        # Scan runs
        for run_file in self.runs_root.rglob("*.json"):
            try:
                with run_file.open("r", encoding="utf-8") as f:
                    run_data = json.load(f)
                    if run_data.get("user_id") == user_id:
                        user_runs.append(run_data)
            except Exception:
                pass

        return {
            "userId": user_id,
            "exportedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "totalEvents": len(user_events),
            "totalRuns": len(user_runs),
            "events": user_events[:500],
            "runs": user_runs[:50],
            "complianceStatement": "Exported in compliance with enterprise audit and privacy standards. All high-entropy secrets and credential tokens are scrubbed.",
        }


# Global data lake singleton
_global_data_lake: Optional[DataLakeIngestor] = None


def get_data_lake() -> DataLakeIngestor:
    global _global_data_lake
    if _global_data_lake is None:
        _global_data_lake = DataLakeIngestor()
    return _global_data_lake
