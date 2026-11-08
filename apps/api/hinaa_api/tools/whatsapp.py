"""whatsapp_send / whatsapp_status — strictly allow-listed WhatsApp Web messenger.

See integrations/whatsapp_guard.py for the allow-list rule. This module is
layer 1 (argument validation); tools/policy.py is layer 2 and
integrations/whatsapp_web.py is layer 3 (DOM header check before send).
"""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from ..integrations import whatsapp_web
from ..integrations.whatsapp_guard import (
    MAX_MESSAGE_CHARS,
    configured_allowed_chats,
    validate_message,
    validate_recipient,
)
from ..run_ledger import get_run_ledger
from .registry import ToolDefinition, registry

# Tests replace these to inject a fake page / ledger.
_page_provider = None
_ledger_provider = get_run_ledger


async def _get_page():
    if _page_provider is not None:
        return await _page_provider()
    return await whatsapp_web.get_browser().page()


def _audit(recipient: str, length: int, status: str, error: str | None = None) -> None:
    """Metadata only: recipient, length, timestamp. Never the message body."""
    ledger = _ledger_provider()
    if ledger is None or not getattr(ledger, "available", False):
        return
    ledger.record_receipt(
        turn_id="whatsapp",
        step_type="whatsapp_send",
        step_name="whatsapp_send",
        status=status,
        input_summary=f"recipient={recipient} length={length}",
        error=error,
        metadata={"recipient": recipient, "length": length, "timestamp": time.time()},
    )


class WhatsAppSendParams(BaseModel):
    recipient: str = Field(..., description='Exact chat name: "Unesh" or "AI Hub" (allow-listed).')
    message: str = Field(..., description=f"Plain text, at most {MAX_MESSAGE_CHARS} characters.")


class WhatsAppStatusParams(BaseModel):
    check_login: bool = Field(
        True, description="Open WhatsApp Web to check whether the session is linked."
    )


async def whatsapp_send(params: WhatsAppSendParams) -> dict[str, Any]:
    recipient = validate_recipient(params.recipient)  # layer 1
    validate_message(params.message)
    length = len(params.message)
    try:
        page = await _get_page()
        result = await whatsapp_web.send_to_allowed_chat(page, recipient, params.message)  # layer 3
    except Exception as exc:
        _audit(recipient, length, "failed", getattr(exc, "code", type(exc).__name__))
        raise
    _audit(recipient, length, "sent")
    return {"success": True, "recipient": recipient, "length": length, "sent_at": result["sent_at"]}


async def whatsapp_status(params: WhatsAppStatusParams) -> dict[str, Any]:
    browser = whatsapp_web.get_browser()
    out: dict[str, Any] = {
        "profile_present": browser.profile_present(),
        "allowed_chats": list(configured_allowed_chats()),
        "logged_in": None,
    }
    if params.check_login:
        try:
            out["logged_in"] = await (await _get_page()).is_logged_in()
        except Exception as exc:  # noqa: BLE001
            out["error"] = type(exc).__name__
    return out


whatsapp_send_def = ToolDefinition(
    name="whatsapp_send",
    display_name="WhatsApp: Send Message",
    description='Send a text message on WhatsApp Web. ONLY the chats "Unesh" and "AI Hub" are allowed; any other recipient is refused.',
    parameters={
        "recipient": {"type": "string", "description": 'Exact chat name: "Unesh" or "AI Hub".'},
        "message": {"type": "string", "description": "Plain text message."},
    },
    required_parameters=["recipient", "message"],
    requires_confirmation=True,
    risk_level="high",
    is_concurrency_safe=False,
)
whatsapp_status_def = ToolDefinition(
    name="whatsapp_status",
    display_name="WhatsApp: Status",
    description="Report whether Hina's WhatsApp Web profile exists and is logged in.",
    parameters={
        "check_login": {"type": "boolean", "description": "Open WhatsApp Web to check login."}
    },
    required_parameters=[],
    requires_confirmation=True,
    risk_level="low",
    is_read_only=True,
)
registry.register(whatsapp_send_def, whatsapp_send)
registry.register(whatsapp_status_def, whatsapp_status)
