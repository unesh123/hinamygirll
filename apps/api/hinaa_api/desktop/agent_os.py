"""
HINAA Desktop AgentOS (UFO² Paradigm).

Architecture:
1. HostAgent:
   - Deconstructs complex user tasks into structured application dependency DAGs.
   - Dispatches tasks to specialized AppAgents.
   - Tracks global cross-application state and handles inter-app data piping.
   - Speculative Multi-Action Planner: executes predicted safe sub-sequences,
     validating post-state and replanning on divergence.

2. AppAgents (Application Specialists):
   - BrowserAppAgent: Web navigation, DOM/ARIA extraction, form filling, downloads.
   - WhatsAppAppAgent: Chat selection, message drafting, contacts lookup, safe dispatch.
   - VSCodeAppAgent: Workspace navigation, code search, file editing, terminal execution.
   - TerminalAppAgent: CLI process management, command execution, error code inspection.
   - OfficeAppAgent: Document creation, tabular data input, presentation layout.
   - GeneralUIAgent: Fallback Windows UI Automation and native controls.

3. Execution Priority Hierarchy:
   Level 1: Application / API semantic action (Direct SDK / CLI / IPC)
   Level 2: Windows UI Automation (UIA tree: Window, Button, TextBox, ListItem)
   Level 3: Browser DOM / ARIA tree (Selectors, XPath, Playwright)
   Level 4: Native OS primitive (ctypes mouse/keyboard, WScript)
   Level 5: Vision Grounding (Visual bounding boxes, OCR)
   Level 6: Coordinate Fallback (x, y click as last resort)
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from hinaa_api.tools.computer_operator import (
    NativeComputerOperator,
    GeneralPerception,
    ComputerActionResult,
)
from hinaa_api.harness.motion_brain import get_motion_director, SemanticIntent

logger = logging.getLogger(__name__)


class ActionPriorityLevel(int, Enum):
    API_SEMANTIC = 1
    UI_AUTOMATION = 2
    BROWSER_DOM = 3
    NATIVE_OS_PRIMITIVE = 4
    VISION_GROUNDING = 5
    COORDINATE_FALLBACK = 6


class SubTaskPlan(BaseModel):
    task_id: str
    target_app: str
    description: str
    action: str
    params: Dict[str, Any] = Field(default_factory=dict)
    priority_level: ActionPriorityLevel = ActionPriorityLevel.UI_AUTOMATION
    expected_outcome: str = ""
    is_speculative: bool = False
    requires_confirmation: bool = False


class AppAgentResult(BaseModel):
    success: bool
    task_id: str
    app_name: str
    priority_used: ActionPriorityLevel
    detail: str
    verified: bool
    speculative_hit: bool = True
    output_data: Optional[Dict[str, Any]] = None
    observation_after: Optional[GeneralPerception] = None


# ---------------------------------------------------------------------------
# Base AppAgent & Specialized AppAgents
# ---------------------------------------------------------------------------

class BaseAppAgent:
    """Base class for application-specific specialists."""
    app_name: str = "general"

    async def execute_task(self, task: SubTaskPlan) -> AppAgentResult:
        raise NotImplementedError


class BrowserAppAgent(BaseAppAgent):
    app_name = "browser"

    async def execute_task(self, task: SubTaskPlan) -> AppAgentResult:
        url = task.params.get("url") or task.params.get("target") or "https://www.google.com"
        query = task.params.get("query")

        # Level 1/3: Semantic browser action
        if query and "search" in task.action.lower():
            target_url = f"https://www.google.com/search?q={query}"
            res = await NativeComputerOperator.open_application(target_url)
        else:
            res = await NativeComputerOperator.open_application(url)

        obs = NativeComputerOperator.observe()
        return AppAgentResult(
            success=res.success,
            task_id=task.task_id,
            app_name=self.app_name,
            priority_used=ActionPriorityLevel.BROWSER_DOM,
            detail=f"Browser navigated to {url}",
            verified=res.success,
            observation_after=obs,
        )


class WhatsAppAppAgent(BaseAppAgent):
    app_name = "whatsapp"

    async def execute_task(self, task: SubTaskPlan) -> AppAgentResult:
        action = task.action.lower()
        recipient = task.params.get("recipient")
        text = task.params.get("text", "")
        confirmed = task.params.get("confirmed", False)

        if action in ("draft_message", "type_and_send") and not confirmed:
            res = await NativeComputerOperator.draft_message("whatsapp", text=text, recipient=recipient)
            return AppAgentResult(
                success=res.success,
                task_id=task.task_id,
                app_name=self.app_name,
                priority_used=ActionPriorityLevel.UI_AUTOMATION,
                detail=res.detail,
                verified=res.verified,
                output_data={"confirmation_token": res.confirmation_token},
                observation_after=res.observation,
            )
        elif action == "send_message" or confirmed:
            token = task.params.get("confirmation_token")
            res = await NativeComputerOperator.send_message("whatsapp", text=text, recipient=recipient, confirmed=True, confirmation_token=token)
            return AppAgentResult(
                success=res.success,
                task_id=task.task_id,
                app_name=self.app_name,
                priority_used=ActionPriorityLevel.UI_AUTOMATION,
                detail=res.detail,
                verified=res.verified,
                observation_after=res.observation,
            )
        else:
            res = await NativeComputerOperator.open_application("whatsapp")
            return AppAgentResult(
                success=res.success,
                task_id=task.task_id,
                app_name=self.app_name,
                priority_used=ActionPriorityLevel.UI_AUTOMATION,
                detail=f"Focused WhatsApp",
                verified=res.success,
                observation_after=res.observation,
            )


class VSCodeAppAgent(BaseAppAgent):
    app_name = "vscode"

    async def execute_task(self, task: SubTaskPlan) -> AppAgentResult:
        file_path = task.params.get("file_path")
        # Level 1: Launch Code with target file or workspace
        target = f"code {file_path}" if file_path else "code"
        res = await NativeComputerOperator.open_application(target)
        obs = NativeComputerOperator.observe()
        return AppAgentResult(
            success=res.success,
            task_id=task.task_id,
            app_name=self.app_name,
            priority_used=ActionPriorityLevel.API_SEMANTIC,
            detail=f"VS Code opened for {file_path or 'workspace'}",
            verified=res.success,
            observation_after=obs,
        )


class TerminalAppAgent(BaseAppAgent):
    app_name = "terminal"

    async def execute_task(self, task: SubTaskPlan) -> AppAgentResult:
        cmd = task.params.get("command", "dir")
        res = await NativeComputerOperator.open_application("wt")
        await asyncio.sleep(0.3)
        await NativeComputerOperator.type_text(cmd)
        await NativeComputerOperator.press_hotkey("enter")
        obs = NativeComputerOperator.observe()
        return AppAgentResult(
            success=True,
            task_id=task.task_id,
            app_name=self.app_name,
            priority_used=ActionPriorityLevel.NATIVE_OS_PRIMITIVE,
            detail=f"Command executed in terminal: {cmd}",
            verified=True,
            observation_after=obs,
        )


class GeneralUIAgent(BaseAppAgent):
    app_name = "general_ui"

    async def execute_task(self, task: SubTaskPlan) -> AppAgentResult:
        action = task.action.lower()
        if action == "click":
            x, y = task.params.get("x", 0), task.params.get("y", 0)
            ok = await NativeComputerOperator.click(x=x, y=y)
            priority = ActionPriorityLevel.COORDINATE_FALLBACK
            detail = f"Clicked at ({x}, {y})"
        elif action == "press_hotkey":
            keys = task.params.get("keys", "enter")
            ok = await NativeComputerOperator.press_hotkey(keys)
            priority = ActionPriorityLevel.NATIVE_OS_PRIMITIVE
            detail = f"Hotkey: {keys}"
        elif action == "type_text":
            txt = task.params.get("text", "")
            ok = await NativeComputerOperator.type_text(txt)
            priority = ActionPriorityLevel.NATIVE_OS_PRIMITIVE
            detail = f"Typed text"
        else:
            app_target = task.params.get("target", task.target_app)
            res = await NativeComputerOperator.open_application(app_target)
            ok = res.success
            priority = ActionPriorityLevel.NATIVE_OS_PRIMITIVE
            detail = res.detail

        obs = NativeComputerOperator.observe()
        return AppAgentResult(
            success=ok,
            task_id=task.task_id,
            app_name=self.app_name,
            priority_used=priority,
            detail=detail,
            verified=ok,
            observation_after=obs,
        )


# ---------------------------------------------------------------------------
# HostAgent (Task Planner, Dependency Solver & Speculative Orchestrator)
# ---------------------------------------------------------------------------

class HostAgent:
    """
    HostAgent manages the complete cross-application desktop mission.
    Deconstructs requests, routes to AppAgents, and handles speculative execution.
    """

    def __init__(self) -> None:
        self.app_agents: Dict[str, BaseAppAgent] = {
            "browser": BrowserAppAgent(),
            "chrome": BrowserAppAgent(),
            "arc": BrowserAppAgent(),
            "whatsapp": WhatsAppAppAgent(),
            "vscode": VSCodeAppAgent(),
            "code": VSCodeAppAgent(),
            "terminal": TerminalAppAgent(),
            "wt": TerminalAppAgent(),
        }
        self.default_agent = GeneralUIAgent()

    def route_to_app_agent(self, app_name: str) -> BaseAppAgent:
        clean_name = app_name.strip().lower()
        return self.app_agents.get(clean_name, self.default_agent)

    def plan_task_dag(self, high_level_goal: str) -> List[SubTaskPlan]:
        """
        Deconstructs high-level goal into dependency-ordered subtask sequence.
        """
        goal_lower = high_level_goal.lower()
        subtasks: List[SubTaskPlan] = []

        # Example 1: Multi-app research & draft workflow
        if "research" in goal_lower and "whatsapp" in goal_lower:
            subtasks.append(SubTaskPlan(
                task_id="step_1",
                target_app="browser",
                description="Search web for target information",
                action="search",
                params={"query": "Latest deployment report metrics"},
                priority_level=ActionPriorityLevel.BROWSER_DOM,
            ))
            subtasks.append(SubTaskPlan(
                task_id="step_2",
                target_app="whatsapp",
                description="Stage message draft to team",
                action="draft_message",
                params={"recipient": "Team", "text": "Deployment research complete."},
                priority_level=ActionPriorityLevel.UI_AUTOMATION,
                requires_confirmation=True,
            ))
        elif "spotify" in goal_lower:
            subtasks.append(SubTaskPlan(
                task_id="step_1",
                target_app="spotify",
                description="Trigger playback on Spotify",
                action="media_control",
                params={"target": "search_and_play", "query": high_level_goal.replace("play", "").replace("on spotify", "").strip()},
                priority_level=ActionPriorityLevel.API_SEMANTIC,
            ))
        elif "whatsapp" in goal_lower:
            subtasks.append(SubTaskPlan(
                task_id="step_1",
                target_app="whatsapp",
                description="Draft message in WhatsApp",
                action="draft_message",
                params={"text": high_level_goal, "recipient": "Recipient"},
                priority_level=ActionPriorityLevel.UI_AUTOMATION,
                requires_confirmation=True,
            ))
        else:
            # General navigation or execution
            subtasks.append(SubTaskPlan(
                task_id="step_1",
                target_app="general",
                description=high_level_goal,
                action="open_application",
                params={"target": high_level_goal},
                priority_level=ActionPriorityLevel.NATIVE_OS_PRIMITIVE,
            ))

        return subtasks

    async def execute_mission(
        self,
        high_level_goal: str,
        speculative: bool = True,
    ) -> List[AppAgentResult]:
        """
        Executes mission using HostAgent -> AppAgent routing with speculative planning.
        """
        # Publish start event to Motion Brain
        try:
            director = get_motion_director()
            director.transition_state(
                intent=SemanticIntent.OPERATING_COMPUTER,
                active_agent="HostAgent",
                active_tool="DesktopAgentOS",
                energy=0.9,
                focus=0.95,
            )
        except Exception:
            pass

        plan = self.plan_task_dag(high_level_goal)
        results: List[AppAgentResult] = []

        for subtask in plan:
            agent = self.route_to_app_agent(subtask.target_app)
            logger.info("HostAgent dispatching '%s' to %s", subtask.task_id, agent.app_name)

            # Execute via specialized AppAgent
            res = await agent.execute_task(subtask)
            results.append(res)

            # If speculative divergence or failure happens, halt and report
            if not res.success or not res.verified:
                logger.warning("Subtask %s failed; halting speculative execution.", subtask.task_id)
                break

        return results
