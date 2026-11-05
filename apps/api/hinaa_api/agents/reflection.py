"""
HINAA OS — Phase 11 Post-Task Reflection & Continuous Learning
Extracts validated execution learnings and stages them into the Phase 10 quarantine pipeline.
Never bypasses quarantine; all staged items require review before permanent memory promotion.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .contracts import TaskResult, TaskSpec, TaskStatus

logger = logging.getLogger("hinaa.agents.reflection")


class AgentReflector:
    """Reflects on multi-agent execution outcomes and stages candidate knowledge."""

    def __init__(self, memory_service: Optional[Any] = None) -> None:
        if memory_service is None:
            try:
                from ..memory.service import MemoryService
                self.memory_service = MemoryService()
            except Exception as e:
                logger.warning(f"MemoryService unavailable for reflection: {e}")
                self.memory_service = None
        else:
            self.memory_service = memory_service

    def extract_learnings(self, task: TaskSpec, result: TaskResult) -> List[Dict[str, Any]]:
        """Extract durable factual or engineering learnings from task outcomes."""
        learnings: List[Dict[str, Any]] = []

        if result.status == TaskStatus.COMPLETED and result.verification_passed:
            # Successful task learning
            fact = f"Workflow '{task.goal}' completed successfully with actions: {', '.join(result.completed_actions[:5])}"
            learnings.append({
                "fact": fact,
                "source_tool": "supervisor_synthesis",
                "evidence": f"Total receipts: {len(result.receipts)}, duration: {result.total_duration_ms}ms",
            })

            # Check if specialized artifacts were produced
            for art in result.artifacts:
                art_name = art.get("filename") or art.get("title") or "artifact"
                art_hash = art.get("sha256") or art.get("digest") or "unknown"
                learnings.append({
                    "fact": f"Generated verified artifact '{art_name}' with SHA256 checksum {art_hash[:16]}...",
                    "source_tool": "independent_verifier",
                    "evidence": f"Artifact path: {art.get('path', 'n/a')}",
                })
        elif result.status in (TaskStatus.FAILED, TaskStatus.PARTIAL):
            # Error / failure prevention learning
            fact = f"Workflow '{task.goal}' experienced failure: {result.summary}"
            learnings.append({
                "fact": fact,
                "source_tool": "verifier_error_catch",
                "evidence": f"Uncompleted actions: {', '.join(result.uncompleted_actions)}",
            })

        return learnings

    def stage_task_reflections(self, task: TaskSpec, result: TaskResult) -> List[str]:
        """Stage extracted learnings into Phase 10 quarantine."""
        learnings = self.extract_learnings(task, result)
        staged_ids: List[str] = []

        if not self.memory_service:
            logger.info("Memory service not available; skipping candidate staging.")
            return staged_ids

        for item in learnings:
            try:
                candidate = self.memory_service.ingestion.stage_candidate(
                    candidate_fact=item["fact"],
                    source_tool=item.get("source_tool", "agent_reflection"),
                    raw_evidence=item.get("evidence", ""),
                    tenant_id=task.tenant_id,
                )
                staged_ids.append(candidate.candidate_id)
                logger.info(f"Staged reflection candidate {candidate.candidate_id} to Phase 10 quarantine.")
            except Exception as e:
                logger.error(f"Failed to stage reflection candidate: {e}")

        return staged_ids
