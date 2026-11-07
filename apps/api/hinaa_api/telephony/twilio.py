"""Plain-httpx Twilio helpers: signature validation, number rules, REST call creation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from collections.abc import Iterable

import httpx

from ..config import Settings
from ..errors import HinaaError

_E164 = re.compile(r"^\+[1-9]\d{6,14}$")


def normalize_number(value: str | None) -> str:
    """E.164 or empty string. Strips the usual spacing and punctuation."""
    cleaned = re.sub(r"[\s().-]", "", value or "")
    return cleaned if _E164.match(cleaned) else ""


def mask_number(value: str) -> str:
    if len(value) < 7:
        return "*" * len(value)
    return value[:3] + "*" * (len(value) - 5) + value[-2:]


def compute_signature(auth_token: str, url: str, params: Iterable[tuple[str, str]]) -> str:
    """Twilio spec: HMAC-SHA1 over URL + each POST param (sorted by name) as name+value."""
    payload = url + "".join(k + v for k, v in sorted(params, key=lambda kv: (kv[0], kv[1])))
    digest = hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def validate_signature(auth_token: str, url: str, params: Iterable[tuple[str, str]], header: str | None) -> bool:
    if not auth_token or not header:
        return False
    return hmac.compare_digest(compute_signature(auth_token, url, params), header.strip())


def telephony_configured(settings: Settings) -> bool:
    return not missing_settings(settings)


def missing_settings(settings: Settings) -> list[str]:
    missing = []
    if not settings.twilio_account_sid:
        missing.append("TWILIO_ACCOUNT_SID")
    if not (settings.twilio_auth_token and settings.twilio_auth_token.get_secret_value()):
        missing.append("TWILIO_AUTH_TOKEN")
    if not normalize_number(settings.twilio_from_number):
        missing.append("TWILIO_FROM_NUMBER")
    if not settings.hinaa_public_base_url.startswith("https://"):
        missing.append("HINAA_PUBLIC_BASE_URL (https)")
    return missing


def require_configured(settings: Settings) -> None:
    missing = missing_settings(settings)
    if missing:
        raise HinaaError(
            "TELEPHONY_NOT_CONFIGURED",
            "Telephony is not configured. Missing: " + ", ".join(missing),
            503,
            False,
        )


def allowed_numbers(settings: Settings) -> set[str]:
    numbers = {normalize_number(settings.hinaa_owner_phone_number)}
    numbers.update(normalize_number(n) for n in settings.telephony_allowed_numbers.split(","))
    numbers.discard("")
    return numbers


def public_url(settings: Settings, path: str) -> str:
    return settings.hinaa_public_base_url.rstrip("/") + path


async def create_call(
    settings: Settings,
    *,
    to: str,
    twiml_url: str,
    status_callback_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict:
    sid = settings.twilio_account_sid
    url = settings.twilio_api_base_url.rstrip("/") + "/2010-04-01/Accounts/" + sid + "/Calls.json"
    data = {
        "To": to,
        "From": normalize_number(settings.twilio_from_number),
        "Url": twiml_url,
        "Method": "POST",
        "StatusCallback": status_callback_url,
        "StatusCallbackMethod": "POST",
        "StatusCallbackEvent": ["initiated", "ringing", "answered", "completed"],
    }
    try:
        async with httpx.AsyncClient(transport=transport, timeout=15.0) as client:
            response = await client.post(
                url, data=data, auth=(sid, settings.twilio_auth_token.get_secret_value())
            )
    except httpx.HTTPError as error:
        raise HinaaError("TELEPHONY_PROVIDER_UNREACHABLE", "Twilio request failed: " + type(error).__name__, 502, True)
    if response.status_code >= 300:
        raise HinaaError("TELEPHONY_PROVIDER_ERROR", f"Twilio rejected the call (HTTP {response.status_code}).", 502, False)
    return response.json()
