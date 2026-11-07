"""Let Hina phone the user (reminders, autopilot alerts). Costs money, so it is gated."""

from __future__ import annotations

from typing import Any

from ..config import get_settings
from ..errors import HinaaError
from .registry import ToolDefinition, registry


async def execute_phone_call_user(params: dict[str, Any]) -> dict[str, Any]:
    from ..telephony.calls import place_outbound_call

    try:
        result = await place_outbound_call(
            get_settings(),
            to=params.get("to"),
            reason=params.get("reason"),
            opening_line=params.get("opening_line"),
        )
    except HinaaError as error:
        return {"status": "failed", "code": error.code, "message": error.message}
    return {"status": "calling", **result, "message": "Call placed. She will ring now."}


phone_call_user_def = ToolDefinition(
    name="phone_call_user",
    display_name="Phone Call",
    description=(
        "Phone the user (default: the owner's number) and hold a live two-way voice conversation. "
        "Use only for things worth interrupting them for, such as a due reminder or an urgent alert."
    ),
    parameters={
        "to": {"type": "string", "description": "Optional E.164 number; must be on the allow-list. Defaults to the owner."},
        "reason": {"type": "string", "description": "Why Hina is calling; woven into the opening line."},
        "opening_line": {"type": "string", "description": "Optional exact first sentence to say."},
    },
    required_parameters=[],
    voice_aliases=["call me", "phone me", "ring me"],
    requires_confirmation=True,
    risk_level="high",
    is_concurrency_safe=False,
)

registry.register(phone_call_user_def, execute_phone_call_user)
