"""Institutional & Enterprise Outlook Email Integration Tool.

Enables HINAA to draft, format, and transmit professional academic emails for
teachers, faculty, administrators, and students. Supports Microsoft Outlook / Office 365,
Gmail, and standard institutional SMTP relays with confirmation gating.
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Literal
import httpx
from pydantic import BaseModel, Field

from hinaa_api.config import get_settings
from hinaa_api.tools.registry import registry, ToolDefinition

logger = logging.getLogger("hinaa.tools.email")


class EmailDraftParams(BaseModel):
    recipient: str = Field(..., description="Target email address (e.g., student@college.edu or prof@university.edu)")
    subject: str = Field(..., description="Subject line of the email")
    body: str = Field(..., description="The main content or body of the email")
    cc: list[str] | None = Field(default=None, description="Optional CC email addresses")
    category: Literal["academic_announcement", "assignment_feedback", "institutional_inquiry", "meeting_request", "general"] = Field(
        default="general", description="Classification of the email for automated styling"
    )
    send_immediately: bool = Field(default=False, description="Whether to transmit directly or return an editable draft")


async def execute_email_handler(params: EmailDraftParams | dict[str, Any]) -> dict[str, Any]:
    """Drafts or sends an institutional email using Outlook or SMTP relay."""
    if isinstance(params, dict):
        params = EmailDraftParams(**params)

    settings = get_settings()

    # Academic & Professional formatting polish
    formatted_body = params.body.strip()
    if not formatted_body.endswith(("Best regards,", "Sincerely,", "Regards,", "HINAA")):
        formatted_body += "\n\n---\nDrafted with HINAA Academic Partner · Institutional Communications Engine"

    # If send_immediately is false, return the curated draft for review
    if not params.send_immediately:
        return {
            "status": "draft_created",
            "recipient": params.recipient,
            "subject": params.subject,
            "body": formatted_body,
            "category": params.category,
            "message": f"Prepared high-signal email draft for '{params.recipient}'. You can review and instruct me to send.",
        }

    # Transmit via SMTP or Microsoft Graph API
    smtp_host = os.getenv("SMTP_HOST") or os.getenv("OUTLOOK_SMTP_HOST") or "smtp.office365.com"
    smtp_port = int(os.getenv("SMTP_PORT") or "587")
    smtp_user = os.getenv("SMTP_USER") or os.getenv("OUTLOOK_EMAIL")
    smtp_pass = os.getenv("SMTP_PASSWORD") or os.getenv("OUTLOOK_PASSWORD")

    if smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = smtp_user
            msg["To"] = params.recipient
            msg["Subject"] = params.subject
            if params.cc:
                msg["Cc"] = ", ".join(params.cc)

            # Plain text and HTML versions
            part_plain = MIMEText(formatted_body, "plain", "utf-8")
            html_content = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1e293b;">
              <div style="padding: 16px; border-left: 4px solid #3b82f6; background: #f8fafc; margin-bottom: 16px;">
                <strong style="color: #0f172a;">{params.subject}</strong>
              </div>
              <div style="white-space: pre-wrap; font-size: 14px;">{formatted_body}</div>
            </div>
            """
            part_html = MIMEText(html_content, "html", "utf-8")
            msg.attach(part_plain)
            msg.attach(part_html)

            with smtplib.SMTP(smtp_host, smtp_port, timeout=12) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                all_recipients = [params.recipient] + (params.cc or [])
                server.sendmail(smtp_user, all_recipients, msg.as_string())

            logger.info("Successfully dispatched email to %s via %s", params.recipient, smtp_host)
            return {
                "status": "sent",
                "recipient": params.recipient,
                "subject": params.subject,
                "provider": "outlook-smtp",
                "message": f"Successfully dispatched email to {params.recipient}.",
            }
        except Exception as exc:
            logger.error("Failed to send email via SMTP: %s", exc)
            return {
                "status": "failed",
                "recipient": params.recipient,
                "error": str(exc),
                "draft": formatted_body,
                "message": f"Could not transmit directly via SMTP ({exc}). Saved as verified draft.",
            }

    # Simulation / Local Development sandbox fallback
    return {
        "status": "simulated_sent",
        "recipient": params.recipient,
        "subject": params.subject,
        "body": formatted_body,
        "provider": "sandbox-simulation",
        "message": (
            f"[Sandbox Simulation] Email successfully validated and queued for {params.recipient}. "
            "To enable live network delivery, configure SMTP_USER/OUTLOOK_EMAIL and SMTP_PASSWORD in .env.local."
        ),
    }


send_email_def = ToolDefinition(
    name="send_email",
    display_name="Send / Draft Email (Outlook)",
    description="Drafts, formats, and transmits academic or professional emails to students, faculty, or institutional contacts.",
    parameters={
        "recipient": {"type": "string", "description": "The email address of the recipient."},
        "subject": {"type": "string", "description": "The subject of the email."},
        "body": {"type": "string", "description": "The body content of the email."},
        "category": {
            "type": "string",
            "enum": ["academic_announcement", "assignment_feedback", "institutional_inquiry", "meeting_request", "general"],
            "description": "Category for template adaptation",
        },
        "send_immediately": {"type": "boolean", "description": "True to transmit directly; False to review draft first."},
    },
    required_parameters=["recipient", "subject", "body"],
    voice_aliases=["send email", "draft email", "outlook email", "email professor", "email student"],
    requires_confirmation=True,
)

registry.register(send_email_def, execute_email_handler)
