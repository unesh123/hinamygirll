"""
HINAA Enterprise Agent Lifecycle Hook Pipeline (Directives §1-§28).

Clean-room engineered 28-point deterministic event lifecycle hook system:
Enables observation, auditing, dynamic intervention, and cross-subsystem synchronization
(Motion Brain, telemetry, audit ledger, and subagent state) across all stages of cognitive execution.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .canonical_event_bus import CanonicalEventBus, HinaCanonicalEvent
from .motion_brain import get_motion_director, SemanticIntent

logger = logging.getLogger("hinaa.harness.lifecycle_hooks")


class LifecycleEvent(str, Enum):
    # Session & Turn Lifecycle
    SESSION_START = "session_start"
    SESSION_CLOSE = "session_close"
    PRE_USER_TURN = "pre_user_turn"
    POST_USER_TURN = "post_user_turn"

    # Intent & Gate Lifecycle
    PRE_INTENT_GATE = "pre_intent_gate"
    POST_INTENT_GATE = "post_intent_gate"

    # Context & Retrieval Lifecycle
    PRE_CONTEXT_ROUTING = "pre_context_routing"
    POST_CONTEXT_ROUTING = "post_context_routing"
    PRE_GROUNDING_SEARCH = "pre_grounding_search"
    POST_GROUNDING_SEARCH = "post_grounding_search"

    # Prompt Compilation Lifecycle
    PRE_PROMPT_BUILD = "pre_prompt_build"
    POST_PROMPT_BUILD = "post_prompt_build"

    # Model & Brain Provider Lifecycle
    PRE_MODEL_CALL = "pre_model_call"
    POST_MODEL_CALL = "post_model_call"
    ON_MODEL_FALLBACK = "on_model_fallback"

    # Tool Execution & Verification Lifecycle
    PRE_TOOL_SANCTION = "pre_tool_sanction"
    POST_TOOL_SANCTION = "post_tool_sanction"
    PRE_TOOL_EXECUTE = "pre_tool_execute"
    POST_TOOL_EXECUTE = "post_tool_execute"
    ON_TOOL_ERROR = "on_tool_error"
    ON_TOOL_RETRY = "on_tool_retry"

    # File System & AST Code Intelligence Lifecycle
    PRE_FILE_MUTATION = "pre_file_mutation"
    POST_FILE_MUTATION = "post_file_mutation"
    ON_AST_VERIFICATION = "on_ast_verification"
    ON_MUTATION_ROLLBACK = "on_mutation_rollback"

    # Subagent Delegation & Fork Lifecycle
    ON_SUBAGENT_FORK = "on_subagent_fork"
    ON_SUBAGENT_JOIN = "on_subagent_join"

    # Memory & State Compaction Lifecycle
    PRE_SESSION_COMPACT = "pre_session_compact"
    POST_SESSION_COMPACT = "post_session_compact"


@dataclass
class LifecycleHookContext:
    event: LifecycleEvent
    session_id: str = "default_session"
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    turn_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Exception] = None
    trace_id: Optional[str] = None


HookCallable = Callable[[LifecycleHookContext], Any]


class LifecycleHookManager:
    """Centralized manager for registering, dispatching, and auditing lifecycle events."""

    def __init__(self, event_bus: Optional[CanonicalEventBus] = None) -> None:
        self.event_bus = event_bus or CanonicalEventBus()
        self._hooks: Dict[LifecycleEvent, List[HookCallable]] = {
            evt: [] for evt in LifecycleEvent
        }
        self._execution_history: List[LifecycleHookContext] = []
        self._register_default_telemetry_bridges()

    def _register_default_telemetry_bridges(self) -> None:
        """Bridge lifecycle events to OpenTelemetry-compatible CanonicalEventBus and Motion Brain."""
        
        def _bridge_to_event_bus(ctx: LifecycleHookContext) -> None:
            try:
                action_name = ctx.event.value
                capability_name = ctx.data.get("tool_name") or ctx.data.get("capability") or "cognitive_core"
                err_msg = str(ctx.error) if ctx.error else None
                
                event = HinaCanonicalEvent(
                    run_id=ctx.session_id,
                    actor=ctx.user_id or "user:primary",
                    agent_name=ctx.data.get("agent_role") or "HinaCore",
                    capability=capability_name,
                    action=action_name,
                    resource=ctx.data.get("target_path") or ctx.data.get("url") or ctx.data.get("resource") or "session",
                    policy_decision="allow" if not ctx.error else "deny",
                    trace_id=ctx.trace_id or f"tr_{ctx.session_id[:8]}",
                    result=ctx.data.get("result") if isinstance(ctx.data.get("result"), dict) else None,
                    error=err_msg,
                )
                self.event_bus.publish(event)
            except Exception:
                logger.debug("Failed to bridge lifecycle event to canonical bus", exc_info=True)

        for evt in LifecycleEvent:
            self._hooks[evt].append(_bridge_to_event_bus)

    def register(self, event: LifecycleEvent, callback: HookCallable) -> None:
        """Register a sync or async hook callback."""
        if callback not in self._hooks[event]:
            self._hooks[event].append(callback)

    def unregister(self, event: LifecycleEvent, callback: HookCallable) -> None:
        """Remove a previously registered hook."""
        if callback in self._hooks[event]:
            self._hooks[event].remove(callback)

    def dispatch(self, event: LifecycleEvent, ctx: LifecycleHookContext) -> None:
        """Synchronously dispatches all registered hooks for an event."""
        ctx.event = event
        self._execution_history.append(ctx)
        if len(self._execution_history) > 1000:
            self._execution_history.pop(0)

        for hook in list(self._hooks.get(event, [])):
            try:
                res = hook(ctx)
                if inspect.isawaitable(res):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(res)
                    except RuntimeError:
                        asyncio.run(res)
            except Exception as err:
                logger.warning("Error in lifecycle hook for %s: %s", event.value, err, exc_info=True)

    async def dispatch_async(self, event: LifecycleEvent, ctx: LifecycleHookContext) -> None:
        """Asynchronously dispatches all registered hooks for an event."""
        ctx.event = event
        self._execution_history.append(ctx)
        if len(self._execution_history) > 1000:
            self._execution_history.pop(0)

        for hook in list(self._hooks.get(event, [])):
            try:
                res = hook(ctx)
                if inspect.isawaitable(res):
                    await res
            except Exception as err:
                logger.warning("Error in async lifecycle hook for %s: %s", event.value, err, exc_info=True)

    def recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent lifecycle execution history for inspection and audit."""
        return [
            {
                "event": ctx.event.value,
                "session_id": ctx.session_id,
                "timestamp": ctx.timestamp,
                "has_error": ctx.error is not None,
                "data_keys": list(ctx.data.keys()),
            }
            for ctx in self._execution_history[-limit:]
        ]


# Singleton instance for system-wide lifecycle hooks
default_lifecycle_hooks = LifecycleHookManager()


def dispatch_lifecycle_event(
    event: LifecycleEvent,
    session_id: str = "default_session",
    conversation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    turn_id: Optional[str] = None,
    error: Optional[Exception] = None,
    **data: Any,
) -> None:
    """Convenience helper to construct context and dispatch event synchronously."""
    try:
        ctx = LifecycleHookContext(
            event=event,
            session_id=session_id or "default_session",
            conversation_id=conversation_id,
            user_id=user_id,
            turn_id=turn_id,
            error=error,
            data=data,
        )
        default_lifecycle_hooks.dispatch(event, ctx)
    except Exception as exc:
        logger.debug("Non-blocking lifecycle dispatch error: %s", exc)
