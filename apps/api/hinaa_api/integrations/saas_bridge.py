"""Enterprise SaaS Bridge for HINAA.

Provides unified connectivity and orchestration across:
- GitHub & GitLab (repositories, pull requests, worktrees, commits)
- Outlook & Office 365 (institutional email drafting and delivery)
- Google Calendar (daily scheduling, agenda sync, reminders)
- Notion (engineering workspace synchronization, document capture)
- Media & Audio Bridges (Spotify, local audio cues, ambient background)
"""
from __future__ import annotations

from .outlook_graph import configured as outlook_configured
import datetime
import logging
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("hinaa.integrations.saas_bridge")


class SaaSIntegrationStatus(BaseModel):
    service_id: str
    display_name: str
    category: str
    connected: bool
    status_text: str
    capabilities: List[str]
    icon: str


class SaaSBridgedManager:
    """Coordinates SaaS integrations and surfaces live statuses to the dashboard."""

    def get_all_statuses(self) -> List[SaaSIntegrationStatus]:
        github_token = os.getenv("GITHUB_TOKEN") or ""
        outlook_ready = outlook_configured() or bool((os.getenv("SMTP_USER") or os.getenv("OUTLOOK_EMAIL")) and (os.getenv("SMTP_PASSWORD") or os.getenv("OUTLOOK_PASSWORD")))
        notion_token = os.getenv("NOTION_API_KEY") or ""
        gcal_token = os.getenv("GOOGLE_CALENDAR_CREDENTIALS") or ""
        spotify_client = os.getenv("SPOTIFY_CLIENT_ID") or ""

        return [
            SaaSIntegrationStatus(
                service_id="github",
                display_name="GitHub / GitLab Workspace",
                category="developer",
                connected=bool(github_token),
                status_text="Token configured; repository permissions unverified" if github_token else "Local Git Available (Token Optional)",
                capabilities=["git-status", "read-tree", "create-pr", "commit-changes", "issue-tracker"],
                icon="git-branch",
            ),
            SaaSIntegrationStatus(
                service_id="outlook",
                display_name="Microsoft Outlook & Office 365",
                category="communication",
                connected=outlook_ready,
                status_text="Credentials configured; mailbox verification required" if outlook_ready else "Disconnected — local drafts available; Microsoft sign-in required",
                capabilities=["draft-email", "send-institutional-email", "faculty-feedback", "academic-notices"],
                icon="mail",
            ),
            SaaSIntegrationStatus(
                service_id="google_calendar",
                display_name="Google Calendar & Scheduling",
                category="productivity",
                connected=bool(gcal_token),
                status_text="Credentials configured; calendar sync not implemented" if gcal_token else "Disconnected — connect a calendar provider",
                capabilities=["agenda-overview", "schedule-reminder", "exam-deadlines", "class-timetable"],
                icon="calendar",
            ),
            SaaSIntegrationStatus(
                service_id="notion",
                display_name="Notion Engineering Workspace",
                category="documentation",
                connected=bool(notion_token),
                status_text="Token configured; page sync not implemented" if notion_token else "Markdown Artifacts Active (Local SQLite/Vault)",
                capabilities=["sync-dossier", "export-page", "task-kanban", "knowledge-base"],
                icon="file-text",
            ),
            SaaSIntegrationStatus(
                service_id="spotify_media",
                display_name="MediaBridge & Background Audio",
                category="entertainment",
                connected=bool(spotify_client),
                status_text="High-Res Web Audio Synth & Viseme Engine Active",
                capabilities=["lo-fi-coding-stream", "study-music", "speech-visemes", "ambient-noise"],
                icon="music",
            ),
        ]

    async def execute_github_quick_action(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform quick repository action via GitHub tools or local git fallback."""
        params = params or {}
        try:
            from ..tools.terminal_hands import execute_terminal_hands
            if action == "status":
                return await execute_terminal_hands({"command": "git status --short", "timeout_seconds": 10})
            elif action == "branch":
                return await execute_terminal_hands({"command": "git branch --show-current", "timeout_seconds": 5})
            elif action == "log":
                return await execute_terminal_hands({"command": "git log -n 5 --oneline", "timeout_seconds": 10})
            elif action == "diff":
                return await execute_terminal_hands({"command": "git diff --stat", "timeout_seconds": 10})
            else:
                return {"status": "error", "message": f"Unsupported quick action: {action}"}
        except Exception as exc:
            logger.error("GitHub quick action '%s' failed: %s", action, exc)
            return {"status": "error", "error": str(exc)}

    async def send_outlook_email(self, recipient: str, subject: str, body: str, send_now: bool = False) -> Dict[str, Any]:
        """Drafts or sends an institutional email using the email tool."""
        try:
            from ..tools.email import execute_email_handler
            return await execute_email_handler({
                "recipient": recipient,
                "subject": subject,
                "body": body,
                "send_immediately": send_now,
            })
        except Exception as exc:
            logger.error("Outlook email execution failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    def get_todays_agenda(self) -> List[Dict[str, Any]]:
        """Return today's scheduled curriculum milestones and research agenda."""
        # No fabricated classes or events; an agenda requires a real calendar adapter.
        return []



# Global singleton
saas_bridge_manager = SaaSBridgedManager()
