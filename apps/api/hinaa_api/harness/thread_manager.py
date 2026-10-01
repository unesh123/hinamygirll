"""
HinaThreadManager - The Central Agent Operating Core.

Modeled directly on the public OpenAI Codex ThreadManager (codex-rs/core/src/thread_manager.rs):
1. Coordinates sessions, threads, turns, and event-sourced items.
2. Manages ModelProviders, EnvironmentState, and CapabilityPermissions.
3. Wires AgentGraphStore and LocalAgentMessageBoard for multi-agent delegation.
4. Integrates SandboxPolicyEngine (CVE-2025-59532 / GHSA-w5fx-fh39-j5rw hardened).
5. Provides background CompactionWorker and Repository-as-Memory (.hina/).
6. Supports non-destructive thread forking preserving full parent ancestry.
7. Executes the autonomous VerifierBrain loop.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .agent_scheduler import AgentScheduler
from .compaction_worker import CompactionWorker
from .repository_memory import RepositoryMemoryManager
from .sandbox_policy import SandboxPolicyEngine, SandboxSecurityViolation
from .types import (
    AgentNode,
    AgentRole,
    AgentSession,
    CapabilityPermissions,
    ContextWindowIdentity,
    EnvironmentState,
    ForkInfo,
    HinaThread,
    ReasoningEffort,
    SessionStatus,
    Turn,
    TurnItem,
    TurnItemType,
    VerifierReport,
    WorldModel,
)
from .verifier_brain import VerifierBrain

logger = logging.getLogger(__name__)


class HinaThreadManager:
    """
    Master coordinator for all persistent threads, sessions, environments, and multi-agent graphs.
    """

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root or os.getcwd()))
        
        # Subsystems
        self.scheduler = AgentScheduler(max_concurrency=6, max_depth=4)
        self.compactor = CompactionWorker(token_pressure_threshold=0.75)
        self.repo_memory = RepositoryMemoryManager(workspace_root=self.workspace_root)
        self.verifier = VerifierBrain()
        self.world_model = WorldModel()

        # Thread storage
        self._threads: Dict[str, HinaThread] = {}
        self._sessions: Dict[str, AgentSession] = {}

        # Auto-scaffold .hina/ repository memory if missing
        self.repo_memory.scaffold_if_missing()

    # -----------------------------------------------------------------------
    # 1. Thread & Session Lifecycle
    # -----------------------------------------------------------------------

    def create_thread(
        self,
        project_id: str = "hina-main",
        user_id: str = "default-user",
        title: str = "Autonomous Workspace Session",
        model_name: str = "agnes-2.5-flash",
        provider_mode: str = "agent-router",
        reasoning_effort: ReasoningEffort = ReasoningEffort.MEDIUM,
        workspace_roots: Optional[List[str]] = None,
    ) -> HinaThread:
        """Initializes a new persistent HINA thread with an isolated environment and session."""
        thread_id = f"thr_{uuid4().hex[:12]}"
        roots = workspace_roots or [self.workspace_root]

        env = EnvironmentState(
            cwd=self.workspace_root,
            workspace_roots=roots,
            shell_runtime="auto",
        )

        permissions = CapabilityPermissions(
            filesystem_read=roots,
            filesystem_write=roots,
            network_enabled=True,
            network_domains=["github.com", "api.github.com", "pypi.org", "npmjs.org"],
            process_types=["python", "node", "git", "npm", "pytest", "bash", "uname", "curl"],
        )

        session = AgentSession(
            thread_id=thread_id,
            model_name=model_name,
            provider_mode=provider_mode,
            reasoning_effort=reasoning_effort,
            environment=env,
            permissions=permissions,
            base_instructions="You are HINA, an elite frontier AI companion and autonomous systems engineer.",
        )

        # Register root agent in scheduler
        root_node = self.scheduler.register_root(session.session_id, role=AgentRole.ROOT)
        session.graph_node_id = root_node.node_id

        thread = HinaThread(
            thread_id=thread_id,
            project_id=project_id,
            user_id=user_id,
            title=title,
            active_session=session,
        )

        self._threads[thread_id] = thread
        self._sessions[session.session_id] = session
        
        logger.info("Created HINA Thread %s with session %s", thread_id, session.session_id)
        return thread

    def get_thread(self, thread_id: str) -> Optional[HinaThread]:
        return self._threads.get(thread_id)

    def list_threads(self, limit: int = 50) -> List[HinaThread]:
        return sorted(self._threads.values(), key=lambda t: t.updated_at, reverse=True)[:limit]

    # -----------------------------------------------------------------------
    # 2. Thread Forking (Branching History Non-Destructively)
    # -----------------------------------------------------------------------

    def fork_thread(
        self,
        source_thread_id: str,
        from_turn_ordinal: Optional[int] = None,
        title: Optional[str] = None,
    ) -> HinaThread:
        """
        Forks an existing thread at a specific turn ordinal into a new branch.
        Preserves original thread ancestry without modifying the original.
        """
        parent = self._threads.get(source_thread_id)
        if not parent:
            raise ValueError(f"Source thread {source_thread_id!r} not found for forking.")

        cutoff = from_turn_ordinal if from_turn_ordinal is not None else len(parent.turns)
        forked_turns = [t.model_copy(deep=True) for t in parent.turns[:cutoff]]

        new_thread_id = f"thr_fork_{uuid4().hex[:10]}"
        fork_info = ForkInfo(
            forked_from_thread_id=source_thread_id,
            forked_from_ordinal_exclusive=cutoff,
        )

        # Clone environment and permissions
        p_session = parent.active_session
        new_env = p_session.environment.model_copy(deep=True) if p_session else EnvironmentState()
        new_perms = p_session.permissions.model_copy(deep=True) if p_session else CapabilityPermissions()

        new_session = AgentSession(
            thread_id=new_thread_id,
            parent_thread_id=source_thread_id,
            fork_info=fork_info,
            model_name=p_session.model_name if p_session else "agnes-2.5-flash",
            provider_mode=p_session.provider_mode if p_session else "agent-router",
            environment=new_env,
            permissions=new_perms,
        )

        root_node = self.scheduler.register_root(new_session.session_id, role=AgentRole.ROOT)
        new_session.graph_node_id = root_node.node_id

        forked_thread = HinaThread(
            thread_id=new_thread_id,
            project_id=parent.project_id,
            user_id=parent.user_id,
            parent_thread_id=source_thread_id,
            title=title or f"Fork of {parent.title} (turn {cutoff})",
            turns=forked_turns,
            active_session=new_session,
        )

        self._threads[new_thread_id] = forked_thread
        self._sessions[new_session.session_id] = new_session

        logger.info("Forked thread %s -> %s at turn ordinal %d", source_thread_id, new_thread_id, cutoff)
        return forked_thread

    # -----------------------------------------------------------------------
    # 3. Turns & Event Sourced Items
    # -----------------------------------------------------------------------

    def append_turn_item(
        self,
        thread_id: str,
        item_type: TurnItemType,
        payload: Dict[str, Any],
        provenance: str = "agent",
    ) -> TurnItem:
        """Appends a typed event item to the current active turn."""
        thread = self.get_thread(thread_id)
        if not thread:
            raise ValueError(f"Thread {thread_id!r} not found.")

        if not thread.turns or thread.turns[-1].status == "completed":
            new_ordinal = len(thread.turns)
            new_turn = Turn(ordinal=new_ordinal, status="active")
            thread.turns.append(new_turn)

        item = TurnItem(
            item_type=item_type,
            payload=payload,
            provenance=provenance,
        )
        thread.turns[-1].items.append(item)
        thread.updated_at = datetime.now(timezone.utc)
        return item

    # -----------------------------------------------------------------------
    # 4. Multi-Agent Coordination
    # -----------------------------------------------------------------------

    def spawn_subagent(
        self,
        thread_id: str,
        role: AgentRole,
        objective: str,
        tool_permissions: Optional[List[str]] = None,
    ) -> AgentNode:
        """Spawns subordinate specialist in the thread's agent graph."""
        thread = self.get_thread(thread_id)
        if not thread or not thread.active_session or not thread.active_session.graph_node_id:
            raise ValueError("Thread or active root session not found.")

        parent_node_id = thread.active_session.graph_node_id
        child_node = self.scheduler.spawn_subagent(
            parent_id=parent_node_id,
            session_id=thread.active_session.session_id,
            role=role,
            objective=objective,
            tool_permissions=tool_permissions,
        )

        # Log item to thread
        self.append_turn_item(
            thread_id=thread_id,
            item_type=TurnItemType.AGENT_SPAWN,
            payload={"child_id": child_node.node_id, "role": role.value, "objective": objective},
        )
        return child_node

    # -----------------------------------------------------------------------
    # 5. Security & Verification Engine
    # -----------------------------------------------------------------------

    def assert_path_safety(self, thread_id: str, requested_path: str, is_write: bool = False) -> str:
        """Hardened against GHSA-w5fx-fh39-j5rw / CVE-2025-59532."""
        thread = self.get_thread(thread_id)
        if not thread or not thread.active_session:
            raise ValueError("Thread session not found.")

        sess = thread.active_session
        if is_write:
            return SandboxPolicyEngine.assert_filesystem_write(requested_path, sess.permissions, sess.environment)
        return SandboxPolicyEngine.assert_filesystem_read(requested_path, sess.permissions, sess.environment)

    def verify_output(self, text: str, is_speech: bool = False, file_path: Optional[str] = None) -> VerifierReport:
        """Runs the autonomous verifier brain on speech, code, or answers."""
        return self.verifier.verify_candidate_output(text, is_speech_chunk=is_speech, file_path=file_path)

    # -----------------------------------------------------------------------
    # 6. Repository Memory Prompt Integration
    # -----------------------------------------------------------------------

    def get_composed_system_prompt(self, thread_id: str) -> str:
        """
        Composes model prompt from structured layers:
        Base + Permissions + Repository Memory (.hina/) + Environment State + Tools
        """
        thread = self.get_thread(thread_id)
        sess = thread.active_session if thread else None

        base = sess.base_instructions if sess else "You are HINA."
        repo_block = self.repo_memory.compile_prompt_block()
        
        env_block = ""
        if sess:
            env_block = (
                f"\n<environment_context>\n"
                f"cwd: {sess.environment.cwd}\n"
                f"workspace_roots: {sess.environment.workspace_roots}\n"
                f"shell_runtime: {sess.environment.shell_runtime}\n"
                f"permissions: read={sess.permissions.filesystem_read}, write={sess.permissions.filesystem_write}\n"
                f"</environment_context>"
            )

        return f"{base}\n\n{repo_block}\n{env_block}"


# Global Singleton
_global_thread_manager: Optional[HinaThreadManager] = None


def get_thread_manager(workspace_root: Optional[str] = None) -> HinaThreadManager:
    global _global_thread_manager
    if _global_thread_manager is None:
        _global_thread_manager = HinaThreadManager(workspace_root=workspace_root)
    return _global_thread_manager
