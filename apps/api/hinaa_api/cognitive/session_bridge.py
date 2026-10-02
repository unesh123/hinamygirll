"""
HINAA Session Bridge & Cross-Session Continuity Engine.

Bridges Session N and Session N+1:
1. finalize_session():
   - Extracts completed tasks, key decisions, and open issues.
   - Generates a structured SessionSummary.
   - Updates project state (.hina/current-state.md).
2. bootstrap_session():
   - When a new session or thread starts, loads the latest session summary,
     active plan, unresolved items, and project decisions into the initial context.
   - Eliminates the need to replay thousands of tokens of raw transcript history.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .contracts import SessionSummary

logger = logging.getLogger("hinaa.cognitive.session_bridge")


class SessionBridge:
    """Provides continuity across sessions, threads, and device surfaces."""

    def __init__(self, root_dir: str = ".") -> None:
        self.root_path = Path(root_dir)
        self.hina_dir = self.root_path / ".hina"
        self.sessions_dir = self.hina_dir / "sessions"
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        try:
            self.sessions_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def finalize_session(
        self,
        session_id: str,
        user_id: str,
        *,
        project_id: Optional[str] = None,
        turns: Optional[List[Dict[str, str]]] = None,
        decisions: Optional[List[str]] = None,
        completed_tasks: Optional[List[str]] = None,
        unresolved_items: Optional[List[str]] = None,
    ) -> SessionSummary:
        """Emits session summary and updates durable project state."""
        # Derive concise summary text from recent turns
        turn_texts = []
        if turns:
            for t in turns[-6:]:
                role = t.get("role", "user")
                c = t.get("content", "")
                turn_texts.append(f"{role}: {c[:120]}")

        summary_text = (
            f"Session {session_id} concluded with {len(turns or [])} turns. "
            f"Key discussion: {' | '.join(turn_texts[-3:]) if turn_texts else 'Standard operational discussion.'}"
        )

        summary = SessionSummary(
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            summary_text=summary_text,
            key_decisions=decisions or [],
            completed_tasks=completed_tasks or [],
            unresolved_items=unresolved_items or [],
            learned_facts=[],
        )

        # 1. Persist to .hina/sessions/<session_id>.json
        try:
            session_file = self.sessions_dir / f"{session_id}.json"
            session_file.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to save session summary file: %s", e)

        # 2. Update .hina/current-state.md
        try:
            current_state_file = self.hina_dir / "current-state.md"
            content = (
                f"# HINAA Operational Current State\n\n"
                f"> Last Updated: {datetime.now(UTC).isoformat()}\n"
                f"> Last Active Session: `{session_id}` (User: `{user_id}`)\n\n"
                f"## Recent Session Summary\n{summary_text}\n\n"
                f"## Key Decisions Made\n" +
                ("\n".join([f"- {d}" for d in (decisions or ["None explicitly recorded"])]) + "\n\n") +
                f"## Completed Tasks\n" +
                ("\n".join([f"- [x] {t}" for t in (completed_tasks or ["General session activity"])]) + "\n\n") +
                f"## Open / Unresolved Items\n" +
                ("\n".join([f"- [ ] {u}" for u in (unresolved_items or ["None pending"])]) + "\n")
            )
            current_state_file.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to update current-state.md: %s", e)

        return summary

    def get_latest_session_summary(self, user_id: str) -> Optional[SessionSummary]:
        """Retrieves the most recent session summary for a user."""
        try:
            session_files = sorted(self.sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for f in session_files:
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    if data.get("user_id") == user_id:
                        return SessionSummary.model_validate(data)
                except Exception:
                    continue
        except Exception as e:
            logger.debug("Error searching session files: %s", e)
        return None

    def bootstrap_new_session(
        self,
        user_id: str,
        *,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates bootstrap context for Session N+1 so Hina knows the prior state,
        recent decisions, and unresolved tasks without replay lag.
        """
        latest_summary = self.get_latest_session_summary(user_id)
        current_state_text = ""
        try:
            current_state_file = self.hina_dir / "current-state.md"
            if current_state_file.exists():
                current_state_text = current_state_file.read_text(encoding="utf-8")
        except Exception:
            pass

        return {
            "has_prior_session": latest_summary is not None,
            "last_session_id": latest_summary.session_id if latest_summary else None,
            "last_session_summary": latest_summary.summary_text if latest_summary else None,
            "unresolved_items": latest_summary.unresolved_items if latest_summary else [],
            "current_state_markdown": current_state_text,
        }
