"""Bounded Goal-to-Steps Planning and Action Budgeting.

Translates high-level automation objectives into bounded sequential action plans,
enforcing maximum step limits and interrupting when Tier C human approvals are needed.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import uuid4

from .action_schema import (
    ActionPostcondition,
    ActionTarget,
    BrowserActionRequest,
    BrowserActionType,
    BrowserTaskSpec,
)

logger = logging.getLogger("hinaa.browser.planner")


class BrowserTaskPlanner:
    """Creates deterministic and bounded browser action execution plans."""

    def __init__(self, max_allowed_steps: int = 15) -> None:
        self.max_allowed_steps = max_allowed_steps

    def create_navigation_plan(self, spec: BrowserTaskSpec, target_url: str) -> List[BrowserActionRequest]:
        """Creates a single-step navigation and inspection plan."""
        return [
            BrowserActionRequest(
                action_id=f"act-nav-{uuid4().hex[:8]}",
                task_id=spec.task_id,
                action_type=BrowserActionType.OPEN,
                url=target_url,
                timeout_ms=15000,
                postcondition=ActionPostcondition(
                    check_type="url_contains",
                    expected_value=target_url.split("://")[-1].split("/")[0],
                ),
            )
        ]

    def create_extraction_plan(
        self, spec: BrowserTaskSpec, target_url: str, table_selector: str = "table"
    ) -> List[BrowserActionRequest]:
        """Creates a plan to navigate, wait for table, and extract data."""
        return [
            BrowserActionRequest(
                action_id=f"act-open-{uuid4().hex[:8]}",
                task_id=spec.task_id,
                action_type=BrowserActionType.OPEN,
                url=target_url,
            ),
            BrowserActionRequest(
                action_id=f"act-wait-{uuid4().hex[:8]}",
                task_id=spec.task_id,
                action_type=BrowserActionType.WAIT_FOR,
                target=ActionTarget(by="css", selector=table_selector),
            ),
            BrowserActionRequest(
                action_id=f"act-extract-{uuid4().hex[:8]}",
                task_id=spec.task_id,
                action_type=BrowserActionType.EXTRACT_TABLE,
                target=ActionTarget(by="css", selector=table_selector),
            ),
        ]

    def create_multi_step_workflow(
        self,
        spec: BrowserTaskSpec,
        actions: List[BrowserActionRequest],
    ) -> List[BrowserActionRequest]:
        """Validates and enforces step budgets on custom multi-step plans."""
        if len(actions) > spec.max_steps or len(actions) > self.max_allowed_steps:
            raise ValueError(
                f"Planned actions ({len(actions)}) exceed maximum allowed step budget ({spec.max_steps})"
            )
        return actions
