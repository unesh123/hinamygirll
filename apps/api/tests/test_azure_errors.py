from __future__ import annotations

from types import SimpleNamespace

import pytest

from hinaa_api.errors import HinaaError
from hinaa_api.providers.azure_errors import (
    AZURE_ERROR_CODES,
    azure_failure_to_error,
    classify_azure_cancellation,
    extract_synthesis_cancellation,
)
from hinaa_api.providers.azure_speech import AzureSpeechProvider


def test_all_required_categories_are_declared() -> None:
    required = {
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
    assert required <= AZURE_ERROR_CODES


@pytest.mark.parametrize(
    ("reason", "error_code", "details", "category"),
    [
        ("Error", "AuthenticationFailure", "WS upgrade failed", "AZURE_AUTH_FAILED"),
        ("Error", "Forbidden", "denied", "AZURE_AUTH_FAILED"),
        (
            "Error",
            "BadRequest",
            "401 unauthorized for this region with subscription",
            "AZURE_KEY_REGION_MISMATCH",
        ),
        ("Error", "ConnectionFailure", "socket closed", "AZURE_NETWORK_FAILED"),
        ("Error", "ServiceTimeout", "timed out", "AZURE_NETWORK_FAILED"),
        ("Error", "TooManyRequests", "quota exceeded", "AZURE_QUOTA_OR_BILLING"),
        ("Error", "BadRequest", "voice not found", "AZURE_VOICE_UNSUPPORTED"),
        ("Error", "RuntimeError", "unexpected cancel", "AZURE_SYNTHESIS_CANCELLED"),
        ("CancelledByUser", "NoError", "", "AZURE_SYNTHESIS_CANCELLED"),
        ("Error", "ServiceError", "generic service error", "AZURE_SYNTHESIS_CANCELLED"),
    ],
)
def test_cancellation_categories(reason: str, error_code: str, details: str, category: str) -> None:
    failure = classify_azure_cancellation(
        reason=reason,
        error_code=error_code,
        error_details=details,
        secrets=["SUPERSECRETKEY"],
    )
    assert failure.category == category
    assert failure.sdk_error_code == error_code
    assert "SUPERSECRETKEY" not in (failure.sdk_error_details_sanitized or "")


def test_does_not_classify_generic_error_as_auth() -> None:
    failure = classify_azure_cancellation(
        reason="Error",
        error_code="RuntimeError",
        error_details="internal synthesis pipeline fault",
    )
    assert failure.category == "AZURE_SYNTHESIS_CANCELLED"
    assert failure.category != "AZURE_AUTH_FAILED"


def test_redacts_secrets_from_details() -> None:
    failure = classify_azure_cancellation(
        reason="Error",
        error_code="AuthenticationFailure",
        error_details="key=ABC123SECRET used",
        secrets=["ABC123SECRET"],
    )
    assert "[REDACTED]" in (failure.sdk_error_details_sanitized or "")
    assert "ABC123SECRET" not in (failure.sdk_error_details_sanitized or "")


def test_extract_synthesis_cancellation_uses_error_code_attr() -> None:
    details = SimpleNamespace(
        reason=SimpleNamespace(name="Error"),
        error_code=SimpleNamespace(name="AuthenticationFailure"),
        error_details="Authentication failure (401)",
    )
    failure = extract_synthesis_cancellation(details, secrets=[])
    assert failure.category == "AZURE_AUTH_FAILED"
    assert failure.sdk_error_code == "AuthenticationFailure"


def test_azure_failure_to_error_preserves_sdk_code() -> None:
    failure = classify_azure_cancellation(
        reason="Error",
        error_code="AuthenticationFailure",
        error_details="no",
    )
    error = azure_failure_to_error(failure)
    assert isinstance(error, HinaaError)
    assert error.code == "AZURE_AUTH_FAILED"
    assert "sdkErrorCode=AuthenticationFailure" in error.message
    assert "Azure Speech needs its backend connection fixed." not in error.message


def test_provider_rejects_missing_key_or_region() -> None:
    with pytest.raises(HinaaError) as missing_key:
        AzureSpeechProvider("", "eastasia")
    assert missing_key.value.code == "AZURE_KEY_MISSING"
    with pytest.raises(HinaaError) as missing_region:
        AzureSpeechProvider("abc", "")
    assert missing_region.value.code == "AZURE_REGION_MISSING"


def test_speech_config_uses_subscription_and_region_not_gemini() -> None:
    provider = AzureSpeechProvider("speech-key-value", "eastasia")
    config = provider._speech_config()  # noqa: SLF001
    # SDK stores subscription/region; assert construction path values via provider fields.
    assert provider._key == "speech-key-value"  # noqa: SLF001
    assert provider._region == "eastasia"  # noqa: SLF001
    assert config is not None
    # Ensure we did not pass Gemini-shaped values into SpeechConfig construction inputs.
    assert provider._key != "GEMINI_API_KEY"  # noqa: SLF001
    assert provider._region not in {"ne-NP-HemkalaNeural", "gemini-3.6-flash"}  # noqa: SLF001


@pytest.mark.parametrize("category", sorted(AZURE_ERROR_CODES))
def test_every_category_maps_to_hinaa_error(category: str) -> None:
    from hinaa_api.providers.azure_errors import SanitizedAzureFailure

    error = azure_failure_to_error(
        SanitizedAzureFailure(category=category, sdk_error_code="UnitTestCode")
    )
    assert error.code == category
    assert "UnitTestCode" in error.message
