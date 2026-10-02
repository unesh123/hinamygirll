"""
HINAA Operational World Model.

Fuses sensory feeds across:
- Local Windows OS (Active Window, Running Apps, Screen Dimensions, Media playback)
- Browser Automation (Active Tab, DOM Title, Current URL)
- Task Execution (Active Task, Artifacts generated)
- Security & Approvals (Pending tokens, required confirmations)
- System Environment (CPU, Memory, Network connectivity)
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any, Dict, Optional

from .contracts import (
    ApplicationState,
    ApprovalState,
    BrowserState,
    DeviceState,
    EnvironmentState,
    FileSystemState,
    UserState,
    WorldState,
)

logger = logging.getLogger("hinaa.cognitive.world_model")


class WorldModel:
    """Manages hydration, real-time sensory fusion, and state mutation for WorldState."""

    @classmethod
    def hydrate_initial_state(
        cls,
        user_id: str,
        *,
        tenant_id: str = "default",
        preferred_language: str = "en",
        preferences: Optional[Dict[str, Any]] = None,
        working_dir: str = ".",
    ) -> WorldState:
        """Hydrates the initial operational world state with live machine telemetry."""
        # Detect platform and environment
        platform_name = "windows" if sys.platform.startswith("win") else ("macos" if sys.platform == "darwin" else "linux")
        
        cpu_percent = 0.0
        memory_percent = 0.0
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=None)
            memory_percent = psutil.virtual_memory().percent
        except Exception:
            pass

        device_state = DeviceState(
            platform=platform_name,
            active_window="Desktop",
            active_process="unknown",
            screen_width=1920,
            screen_height=1080,
        )

        app_state = ApplicationState(active_app="none")

        # Probe desktop operator if available on Windows
        try:
            from ..tools.computer_operator import NativeComputerOperator
            obs = NativeComputerOperator.observe()
            device_state.active_window = obs.active_window_title or "Desktop"
            device_state.active_process = obs.active_process_name or "unknown"
            if obs.vision:
                device_state.screen_width = obs.vision.screen_width
                device_state.screen_height = obs.vision.screen_height
            app_state.running_apps = list(obs.running_apps)[:10] if obs.running_apps else []
            app_state.active_app = obs.active_process_name or "none"
            app_state.media_playing = obs.media_playing
        except Exception as e:
            logger.debug("Failed to read initial NativeComputerOperator observation: %s", e)

        user_state = UserState(
            user_id=user_id,
            tenant_id=tenant_id,
            preferred_language=preferred_language,
            active_preferences=preferences or {},
        )

        filesystem_state = FileSystemState(working_directory=working_dir)

        env_state = EnvironmentState(
            online=True,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
        )

        return WorldState(
            user=user_state,
            device=device_state,
            app=app_state,
            browser=BrowserState(),
            filesystem=filesystem_state,
            approval=ApprovalState(),
            environment=env_state,
        )

    @classmethod
    def apply_desktop_observation(
        cls,
        state: WorldState,
        observation: Any,
    ) -> WorldState:
        """Updates the world state following a desktop actuation."""
        if not observation:
            return state

        try:
            active_win = getattr(observation, "active_window_title", None)
            if active_win:
                state.device.active_window = active_win

            active_proc = getattr(observation, "active_process_name", None)
            if active_proc:
                state.device.active_process = active_proc
                state.app.active_app = active_proc

            running = getattr(observation, "running_apps", None)
            if running:
                state.app.running_apps = list(running)[:15]

            vision = getattr(observation, "vision", None)
            if vision:
                state.device.screen_width = getattr(vision, "screen_width", state.device.screen_width)
                state.device.screen_height = getattr(vision, "screen_height", state.device.screen_height)

            media_playing = getattr(observation, "media_playing", None)
            if media_playing is not None:
                state.app.media_playing = bool(media_playing)
        except Exception as err:
            logger.warning("Error mutating world state from desktop observation: %s", err)

        state.environment.timestamp = time.time()
        return state

    @classmethod
    def apply_browser_observation(
        cls,
        state: WorldState,
        *,
        url: Optional[str] = None,
        title: Optional[str] = None,
        tabs: Optional[list[str]] = None,
    ) -> WorldState:
        """Mutates browser state based on Playwright/Scraping feeds."""
        if url:
            state.browser.active_url = url
        if title:
            state.browser.dom_title = title
        if tabs:
            state.browser.open_tabs = tabs
        state.environment.timestamp = time.time()
        return state

    @classmethod
    def apply_approval_request(
        cls,
        state: WorldState,
        *,
        token: str,
        action: str,
        resource: Optional[str] = None,
    ) -> WorldState:
        """Marks pending safety confirmation in world state."""
        state.approval.required = True
        state.approval.status = "pending"
        state.approval.pending_token = token
        state.approval.target_action = action
        state.approval.target_resource = resource
        return state

    @classmethod
    def clear_approval(cls, state: WorldState, granted: bool = True) -> WorldState:
        """Resolves confirmation state."""
        state.approval.status = "granted" if granted else "rejected"
        state.approval.required = False
        state.approval.pending_token = None
        return state

    @classmethod
    def summarize_for_prompt(cls, state: WorldState) -> str:
        """Renders a concise, structured operational world model block for model context."""
        parts = [
            f"[Operating System & Platform]: {state.device.platform.upper()}",
            f"[Active Window & Application]: '{state.device.active_window}' ({state.app.active_app})",
            f"[Screen Geometry]: {state.device.screen_width}x{state.device.screen_height}",
        ]
        if state.browser.active_url:
            parts.append(f"[Active Browser URL]: {state.browser.active_url} ('{state.browser.dom_title or ''}')")
        if state.app.media_playing:
            parts.append("[Media Status]: Audio/Media actively playing on device")
        if state.approval.required and state.approval.pending_token:
            parts.append(f"[Pending User Approval]: Action '{state.approval.target_action}' awaiting confirmation token")
        if state.artifact_ids:
            parts.append(f"[Active Artifacts in Session]: {', '.join(state.artifact_ids[-5:])}")
        return "\n".join(parts)
