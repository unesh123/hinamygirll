"""
HINAA Agent Scheduler, Multi-Agent Graph Store & Local Agent Message Board.

Implements Codex-grade multi-agent coordination:
1. Persistent AgentGraph: Hierarchical parent-child nodes with depth & concurrency limits.
2. LocalAgentMessageBoard: Inter-agent messaging, task delegation, and broadcast.
3. Cascading cancellation across subtrees.
4. Token budget & execution monitoring.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set
from uuid import uuid4

from .types import (
    AgentMessage,
    AgentNode,
    AgentRole,
    SessionStatus,
)

logger = logging.getLogger(__name__)


class LocalAgentMessageBoard:
    """
    In-memory message board allowing autonomous subagents to communicate asynchronously.
    """

    def __init__(self) -> None:
        self._messages: List[AgentMessage] = []

    def post(
        self,
        sender_id: str,
        recipient_id: str,
        message_type: str,
        payload: Optional[Dict] = None,
    ) -> AgentMessage:
        msg = AgentMessage(
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=message_type,
            payload=payload or {},
        )
        self._messages.append(msg)
        return msg

    def fetch_inbox(self, agent_id: str, unhandled_only: bool = True) -> List[AgentMessage]:
        results = []
        for m in self._messages:
            if m.recipient_id in (agent_id, "broadcast") and m.sender_id != agent_id:
                if not unhandled_only or not m.handled:
                    results.append(m)
        return results

    def mark_handled(self, message_id: str) -> bool:
        for m in self._messages:
            if m.message_id == message_id:
                m.handled = True
                return True
        return False

    def get_all_messages(self, thread_id: Optional[str] = None) -> List[AgentMessage]:
        return list(self._messages)


class AgentScheduler:
    """
    Coordinates multi-agent hierarchies, prevents runaway recursion, and manages agent lifecycles.
    """

    def __init__(
        self,
        max_concurrency: int = 6,
        max_depth: int = 4,
        default_token_budget: int = 50_000,
    ) -> None:
        self.max_concurrency = max_concurrency
        self.max_depth = max_depth
        self.default_token_budget = default_token_budget
        self.nodes: Dict[str, AgentNode] = {}
        self.message_board = LocalAgentMessageBoard()

    def register_root(self, session_id: str, role: AgentRole = AgentRole.ROOT) -> AgentNode:
        """Create root node of an execution tree."""
        root = AgentNode(
            node_id=f"ag_root_{uuid4().hex[:8]}",
            parent_id=None,
            role=role,
            status=SessionStatus.PLANNING,
            session_id=session_id,
            depth=0,
            budget_tokens=self.default_token_budget * 2,
        )
        self.nodes[root.node_id] = root
        return root

    def spawn_subagent(
        self,
        parent_id: str,
        session_id: str,
        role: AgentRole,
        objective: str,
        tool_permissions: Optional[List[str]] = None,
        budget_tokens: Optional[int] = None,
    ) -> AgentNode:
        """
        Spawn a subordinate specialist agent respecting depth and concurrency limits.
        """
        parent = self.nodes.get(parent_id)
        if not parent:
            raise ValueError(f"Parent agent node {parent_id!r} not found in agent graph.")

        # Depth check
        if parent.depth >= self.max_depth:
            raise RuntimeError(
                f"Maximum agent recursion depth ({self.max_depth}) exceeded. Cannot spawn child under depth {parent.depth}."
            )

        # Active concurrency check
        active_count = sum(1 for n in self.nodes.values() if n.status in (SessionStatus.PLANNING, SessionStatus.EXECUTING))
        if active_count >= self.max_concurrency:
            raise RuntimeError(
                f"Maximum concurrent agents ({self.max_concurrency}) reached. Subagent spawn queued or rejected."
            )

        child_id = f"ag_{role.value}_{uuid4().hex[:8]}"
        child = AgentNode(
            node_id=child_id,
            parent_id=parent_id,
            role=role,
            status=SessionStatus.PLANNING,
            session_id=session_id,
            depth=parent.depth + 1,
            budget_tokens=budget_tokens or self.default_token_budget,
            tool_permissions=tool_permissions or [],
        )

        self.nodes[child_id] = child
        parent.children.append(child_id)

        # Notify via Message Board
        self.message_board.post(
            sender_id=parent_id,
            recipient_id=child_id,
            message_type="task_assignment",
            payload={"objective": objective, "role": role.value, "budget": child.budget_tokens},
        )

        logger.info("Spawned agent node %s (role=%s, depth=%d) under parent %s", child_id, role.value, child.depth, parent_id)
        return child

    def cancel_subtree(self, node_id: str, reason: str = "Subtree cancelled") -> List[str]:
        """Cascading cancellation of an agent and all descendant subagents."""
        cancelled = []
        stack = [node_id]

        while stack:
            curr_id = stack.pop()
            node = self.nodes.get(curr_id)
            if node:
                node.status = SessionStatus.CANCELLED
                cancelled.append(curr_id)
                stack.extend(node.children)

        # Post cancellation notification
        self.message_board.post(
            sender_id=node_id,
            recipient_id="broadcast",
            message_type="status_update",
            payload={"status": "cancelled", "cancelled_nodes": cancelled, "reason": reason},
        )
        return cancelled

    def complete_node(self, node_id: str, result_ref: Optional[str] = None) -> None:
        """Mark node completed and notify parent."""
        node = self.nodes.get(node_id)
        if not node:
            return

        node.status = SessionStatus.COMPLETED
        if result_ref:
            node.result_refs.append(result_ref)

        if node.parent_id:
            self.message_board.post(
                sender_id=node_id,
                recipient_id=node.parent_id,
                message_type="status_update",
                payload={"status": "completed", "result_refs": node.result_refs},
            )

    def export_graph_tree(self, root_id: Optional[str] = None) -> Dict:
        """Export serialized tree structure for UI inspection."""
        if not self.nodes:
            return {}

        def _build_tree(nid: str) -> Dict:
            n = self.nodes[nid]
            return {
                "id": n.node_id,
                "role": n.role.value,
                "status": n.status.value,
                "depth": n.depth,
                "budget_tokens": n.budget_tokens,
                "spent_tokens": n.spent_tokens,
                "children": [_build_tree(cid) for cid in n.children if cid in self.nodes],
            }

        target_root = root_id or next((nid for nid, n in self.nodes.items() if n.parent_id is None), None)
        return _build_tree(target_root) if target_root else {}
