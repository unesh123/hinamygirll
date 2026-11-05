"""
HINAA OS — Phase 10 Memory Lifecycle Governance
Handles deletion cascades, derived cache invalidation,
TTL expiration cleanup, and scoped data export (JSON/CSV).
"""

from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any, Optional

from .privacy import MemoryPrivacyGuard
from .repository import MemoryRepository
from .schemas import (
    MemoryRecord,
    MemoryScope,
    _now_iso,
)

logger = logging.getLogger("hinaa.memory.lifecycle")


class MemoryLifecycleCoordinator:
    """Manages memory retention, hard deletions with cascades, and compliant data exports."""

    def __init__(self, repository: MemoryRepository) -> None:
        self.repo = repository

    def delete_with_cascade(self, memory_id: str, tenant_id: str = "default") -> bool:
        """
        Hard-deletes a memory record and invalidates:
        1. Memory row in SQLite
        2. FTS5 full-text index
        3. Derived knowledge edges linking this memory as evidence
        """
        return self.repo.delete_memory(memory_id=memory_id, tenant_id=tenant_id, cascade=True)

    def run_ttl_maintenance(self, current_time: Optional[str] = None) -> int:
        """Sweep and deactivate expired memories past their TTL expiration date."""
        return self.repo.purge_expired(current_time=current_time)

    def export_data(
        self,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        scope: Optional[MemoryScope] = None,
        format_type: str = "json",
    ) -> str:
        """Export scoped memory records in JSON or CSV format."""
        records = self.repo.query_memories(
            tenant_id=tenant_id,
            user_id=user_id,
            project_id=project_id,
            scope=scope,
            include_contradicted=True,
            limit=1000,
        )

        if format_type.lower() == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "id", "tenant_id", "user_id", "project_id", "scope", "memory_type",
                "content", "trust_tier", "confidence", "is_active", "is_contradicted",
                "created_at", "updated_at", "source_url"
            ])
            for r in records:
                writer.writerow([
                    r.id, r.tenant_id, r.user_id, r.project_id, r.scope.value, r.memory_type.value,
                    r.content, r.trust_tier.value, r.confidence, r.is_active, r.is_contradicted,
                    r.created_at, r.updated_at, r.source_url
                ])
            return output.getvalue()
        else:
            export_payload = {
                "tenant_id": tenant_id,
                "exported_at": _now_iso(),
                "total_records": len(records),
                "memories": [r.model_dump() for r in records],
            }
            return json.dumps(export_payload, indent=2, ensure_ascii=False)
