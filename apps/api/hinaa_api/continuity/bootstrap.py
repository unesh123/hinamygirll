from __future__ import annotations

import logging
from typing import Any
from sqlalchemy.orm import Session, sessionmaker

from .models import UserContinuitySnapshot
from .retriever import CrossSessionMemoryRetriever

logger = logging.getLogger("hinaa.continuity.bootstrap")


class ConversationBootstrapper:
    """Bootstraps new conversations with global user continuity context."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory
        self.retriever = CrossSessionMemoryRetriever(session_factory)

    def bootstrap_new_conversation(
        self,
        owner_id: str,
        *,
        conversation_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Loads compact continuity snapshot and builds the bootstrap context block."""
        snapshot = self.retriever.get_continuity_snapshot(owner_id)

        # Build compact context lines
        context_lines: list[str] = []

        if snapshot.preferred_name:
            context_lines.append(f"- User preferred name: {snapshot.preferred_name}")
        if snapshot.communication_style:
            context_lines.append(f"- Communication style preference: {snapshot.communication_style}")
        if snapshot.verbosity_preferences:
            context_lines.append(f"- Verbosity preference: {snapshot.verbosity_preferences}")

        # Active or recent projects
        projects = list(snapshot.recent_projects or snapshot.important_projects)
        if project_id and project_id not in projects:
            projects.insert(0, project_id)
        if projects:
            context_lines.append(f"- Active/Recent projects: {', '.join(projects[:3])}")

        # Unfinished tasks
        if snapshot.active_long_running_tasks:
            top_task = snapshot.active_long_running_tasks[0]
            context_lines.append(
                f"- Open unfinished task: {top_task.get('goal', 'task')} (status: {top_task.get('status')})"
            )

        # Approved character assets
        for ent in snapshot.important_entities:
            name = ent.get("name")
            face = ent.get("approved_face") or ent.get("approved_reference")
            if name and face:
                context_lines.append(f"- Approved reference for {name}: {face}")

        # Persistent preferences
        for pref in snapshot.persistent_preferences[:4]:
            if isinstance(pref, dict):
                context_lines.append(f"- Preference: {pref.get('rule', pref.get('content', ''))}")
            elif isinstance(pref, str):
                context_lines.append(f"- Preference: {pref}")

        # Construct greeting hint
        greeting_hint = None
        if snapshot.active_long_running_tasks:
            t = snapshot.active_long_running_tasks[0]
            goal = t.get("goal")
            if goal:
                greeting_hint = f"Hey — I'm here. We still have the {goal} open if you want to pick that up."
        elif projects:
            greeting_hint = f"Hey — good to see you again. Want to continue with {projects[0]}?"
        else:
            greeting_hint = "Hey — good to see you again."

        bootstrap_block = ""
        if context_lines:
            bootstrap_block = "## Cross-Session User Continuity\n" + "\n".join(context_lines)

        return {
            "snapshot": snapshot,
            "bootstrap_block": bootstrap_block,
            "greeting_hint": greeting_hint,
            "context_lines": context_lines,
        }
