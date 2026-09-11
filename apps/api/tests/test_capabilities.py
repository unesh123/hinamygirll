from __future__ import annotations

from hinaa_api.capabilities import build_capability_registry
from hinaa_api.config import Settings


def test_capability_registry_exposes_configured_model_and_truthful_defaults() -> None:
    settings = Settings(
        HINAA_PROVIDER_MODE="real",
        GEMINI_API_KEY="gemini-test-key",
        _env_file=None,
    )

    registry = build_capability_registry(settings)
    by_id = {model.id: model for model in registry.models}

    assert registry.default_brain == settings.gemini_model
    assert by_id[settings.gemini_model].availability == "healthy"
    assert by_id["mock"].availability == "healthy"


def test_capability_registry_marks_unconfigured_remote_models_unavailable() -> None:
    settings = Settings(HINAA_PROVIDER_MODE="mock", _env_file=None)

    registry = build_capability_registry(settings)
    by_id = {model.id: model for model in registry.models}

    assert registry.default_brain == "mock"
    assert by_id[settings.gemini_model].availability == "unavailable"
    assert by_id[settings.active_claude_model].availability == "unavailable"


def test_capability_registry_includes_gateway_catalog() -> None:
    settings = Settings(
        HINAA_PROVIDER_MODE="cx-gateway",
        CX_GATEWAY_API_KEY="gateway-key",
        CX_GATEWAY_BASE_URL="https://gateway.example/v1",
        CX_GATEWAY_MODEL="cx/custom-model",
        CX_GATEWAY_ALLOWED_MODELS="cx/custom-model,cx/fast-model",
        _env_file=None,
    )

    registry = build_capability_registry(settings)
    by_id = {model.id: model for model in registry.models}

    assert registry.default_brain == "cx/custom-model"
    assert by_id["cx/custom-model"].availability == "healthy"
    assert by_id["cx/fast-model"].availability == "healthy"
