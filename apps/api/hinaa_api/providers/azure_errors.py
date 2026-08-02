"""Sanitize and classify Azure Speech SDK cancellations without revealing secrets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import HinaaError

AZURE_ERROR_CODES = frozenset(
    {
        "AZURE_KEY_MISSING",
        "AZURE_REGION_MISSING",
        "AZURE_AUTH_FAILED",
        "AZURE_KEY_REGION_MISMATCH",
        "AZURE_SDK_UNAVAILABLE",
        "AZURE_NETWORK_FAILED",
        "AZURE_QUOTA_OR_BILLING",
        "AZURE_VOICE_UNSUPPORTED",
        "AZURE_SYNTHESIS_CANCELLED",
        "AZURE_OUTPUT_WRITE_FAILED",
    }
)

_USER_MESSAGES = {
    "AZURE_KEY_MISSING": "Azure Speech key is not configured.",
    "AZURE_REGION_MISSING": "Azure Speech region is not configured.",
    "AZURE_AUTH_FAILED": "Azure Speech rejected the subscription credentials.",
    "AZURE_KEY_REGION_MISMATCH": (
        "Azure Speech credentials do not match the configured region or resource."
    ),
    "AZURE_SDK_UNAVAILABLE": "Azure Speech SDK is unavailable in this environment.",
    "AZURE_NETWORK_FAILED": "Azure Speech network connection failed.",
    "AZURE_QUOTA_OR_BILLING": "Azure Speech quota or billing prevented the request.",
    "AZURE_VOICE_UNSUPPORTED": "The selected Azure Speech voice is unsupported here.",
    "AZURE_SYNTHESIS_CANCELLED": "Azure Speech synthesis was cancelled.",
    "AZURE_OUTPUT_WRITE_FAILED": "Synthesized audio could not be written safely.",
}


@dataclass(frozen=True, slots=True)
class SanitizedAzureFailure:
    category: str
    sdk_reason: str | None = None
    sdk_error_code: str | None = None
    sdk_error_details_sanitized: str | None = None


def _name(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "name"):
        return str(value.name)
    text = str(value)
    if "." in text:
        return text.rsplit(".", 1)[-1]
    return text


def _sanitize_details(text: str | None, secrets: list[str]) -> str | None:
    if not text:
        return None
    cleaned = str(text)
    for secret in secrets:
        if secret:
            cleaned = cleaned.replace(secret, "[REDACTED]")
    # Never retain long opaque blobs that might embed credentials.
    return cleaned[:240]


def classify_azure_cancellation(
    *,
    reason: Any = None,
    error_code: Any = None,
    error_details: str | None = None,
    secrets: list[str] | None = None,
    operation: str = "synthesis",
) -> SanitizedAzureFailure:
    """Map SDK cancellation fields to a distinct sanitized category.

    Does not treat every CancellationReason.Error as authentication failure.
    """
    secrets = secrets or []
    reason_name = _name(reason)
    code_name = _name(error_code)
    details = _sanitize_details(error_details, secrets) or ""
    lowered = f"{reason_name} {code_name} {details}".lower()

    if code_name in {"AuthenticationFailure", "Forbidden"} or (
        "authentication" in lowered and "failure" in lowered
    ):
        category = "AZURE_AUTH_FAILED"
    elif any(
        token in lowered for token in ("region", "endpoint", "resource not found", "wrong region")
    ) and any(token in lowered for token in ("key", "auth", "subscription", "401", "403")):
        category = "AZURE_KEY_REGION_MISMATCH"
    elif "401" in lowered or "403" in lowered:
        category = "AZURE_AUTH_FAILED"
    elif any(
        token in lowered
        for token in (
            "unauthorized",
            "invalid subscription",
            "subscription key",
            "access denied",
        )
    ):
        category = "AZURE_AUTH_FAILED"
    elif code_name in {"ConnectionFailure", "ServiceTimeout"} or any(
        token in lowered
        for token in ("connection", "network", "dns", "timed out", "timeout", "unreachable")
    ):
        category = "AZURE_NETWORK_FAILED"
    elif code_name in {"TooManyRequests"} or any(
        token in lowered
        for token in ("quota", "billing", "payment", "429", "rate limit", "exceeded")
    ):
        category = "AZURE_QUOTA_OR_BILLING"
    elif any(
        token in lowered
        for token in ("voice", "not found", "unsupported locale", "unsupported voice")
    ):
        category = "AZURE_VOICE_UNSUPPORTED"
    elif code_name in {"BadRequest", "RuntimeError", "ServiceError", "ServiceUnavailable"}:
        category = (
            "AZURE_SYNTHESIS_CANCELLED" if operation == "synthesis" else "AZURE_SYNTHESIS_CANCELLED"
        )
    elif reason_name in {"CancelledByUser", "EndOfStream"}:
        category = "AZURE_SYNTHESIS_CANCELLED"
    else:
        category = "AZURE_SYNTHESIS_CANCELLED"

    return SanitizedAzureFailure(
        category=category,
        sdk_reason=reason_name or None,
        sdk_error_code=code_name or None,
        sdk_error_details_sanitized=details or None,
    )


def azure_failure_to_error(failure: SanitizedAzureFailure, *, status_code: int = 503) -> HinaaError:
    base = _USER_MESSAGES.get(failure.category, _USER_MESSAGES["AZURE_SYNTHESIS_CANCELLED"])
    parts = [base]
    if failure.sdk_error_code:
        parts.append(f"sdkErrorCode={failure.sdk_error_code}")
    if failure.sdk_reason:
        parts.append(f"sdkReason={failure.sdk_reason}")
    return HinaaError(
        failure.category,
        "; ".join(parts),
        status_code,
        retryable=failure.category
        in {"AZURE_NETWORK_FAILED", "AZURE_QUOTA_OR_BILLING", "AZURE_SYNTHESIS_CANCELLED"},
        user_action_required=failure.category
        in {
            "AZURE_KEY_MISSING",
            "AZURE_REGION_MISSING",
            "AZURE_AUTH_FAILED",
            "AZURE_KEY_REGION_MISMATCH",
            "AZURE_QUOTA_OR_BILLING",
            "AZURE_VOICE_UNSUPPORTED",
        },
    )


def extract_synthesis_cancellation(details: Any, secrets: list[str]) -> SanitizedAzureFailure:
    return classify_azure_cancellation(
        reason=getattr(details, "reason", None),
        error_code=getattr(details, "error_code", None) or getattr(details, "code", None),
        error_details=getattr(details, "error_details", None),
        secrets=secrets,
        operation="synthesis",
    )


def extract_recognition_cancellation(details: Any, secrets: list[str]) -> SanitizedAzureFailure:
    return classify_azure_cancellation(
        reason=getattr(details, "reason", None),
        error_code=getattr(details, "error_code", None) or getattr(details, "code", None),
        error_details=getattr(details, "error_details", None),
        secrets=secrets,
        operation="recognition",
    )
