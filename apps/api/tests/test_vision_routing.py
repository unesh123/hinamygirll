"""An attached photo has to reach a brain that can look at it.

The wire format was never the problem: ``providers/openai_llm.py`` builds a
correct ``image_url`` part and ``providers/gemini.py`` a correct ``inlineData``
part from the same bytes. What failed is that nothing asked whether the brain
being called accepts images. With Claude returning 403 the recovery ladder
landed on ``agent-router`` running ``agnes-2.5-flash``, which took the bytes,
ignored them, and answered from the caption line in the prompt -- so a blind
turn arrived as a confident description of a screen nobody had shown her.
"""

from __future__ import annotations

import pytest

from hinaa_api.capabilities import brain_accepts_images
from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.media import ResolvedMedia
from hinaa_api.media.models import AssetKind
from hinaa_api.models import TurnRequest
from hinaa_api.services import ConversationService, _turn_has_image, is_casual_chat

BASE = {
    "HINAA_PROVIDER_MODE": "mock",
    "AZURE_SPEECH_KEY": "",
    "AZURE_SPEECH_REGION": "",
    "GEMINI_API_KEY": "",
    "GROQ_API_KEY": "",
    "OPENAI_API_KEY": "",
    "OPENAI_CODEX_API_KEY": "",
    "OPENAI_CODEX_BASE_URL": "",
    "AGENT_ROUTER_API_KEY": "",
    "AGENT_ROUTER_BASE_URL": "",
    "CX_GATEWAY_API_KEY": "",
    "CX_GATEWAY_BASE_URL": "",
    "ELEVENLABS_API_KEY": "",
    "HINAA_DATABASE_URL": "sqlite+pysqlite:///:memory:",
    "HINAA_AUTH_MODE": "dev",
    "HINAA_PERSISTENCE_ENABLED": False,
    "HINAA_VMC_PORT": 0,
    "_env_file": None,
}

# The shape this deployment actually ran when the bug was reported: a text-only
# router brain configured alongside a Gemini that can see.
ROUTER_AND_GEMINI = Settings(
    **{
        **BASE,
        "HINAA_PROVIDER_MODE": "agent-router",
        "GEMINI_API_KEY": "gemini-key-for-tests",
        "AGENT_ROUTER_API_KEY": "router-key-for-tests",
        "AGENT_ROUTER_BASE_URL": "https://router.example.test/v1",
    }
)

# Nothing here accepts an image, so a photo turn has nowhere correct to go.
BLIND_ONLY = Settings(
    **{
        **BASE,
        "HINAA_PROVIDER_MODE": "agent-router",
        "AGENT_ROUTER_API_KEY": "router-key-for-tests",
        "AGENT_ROUTER_BASE_URL": "https://router.example.test/v1",
    }
)

PHOTO = ResolvedMedia(
    "asset-photo",
    b"\x89PNG\r\n\x1a\nfake-bytes",
    "image/png",
    "sha-photo",
    role="inspection",
)

CSV = ResolvedMedia(
    "asset-sheet",
    b"name,qty\nbolt,40",
    "text/csv",
    "sha-sheet",
    kind=AssetKind.SPREADSHEET,
)


def _photo_request(settings: Settings, **overrides: object) -> TurnRequest:
    payload: dict[str, object] = {
        "sessionId": "session-vision",
        "text": "analyse this image",
        "companionId": "hinaa",
        "providerMode": settings.provider_mode,
        "imageUrl": "data:image/png;base64,aW1hZ2U=",
    }
    payload.update(overrides)
    return TurnRequest.model_validate(payload)


def test_a_text_only_router_model_is_not_a_seeing_brain() -> None:
    assert brain_accepts_images("agent-router", "agnes-2.5-flash") is False
    assert brain_accepts_images("real", "gemini-3.5-flash-lite") is True
    assert brain_accepts_images("claude", "claude-sonnet-4-5") is True
    # The router does have a vision endpoint; naming it is what earns the claim.
    assert brain_accepts_images("agent-router", "deepseek-v4-flash-vision-exp") is True


def test_groq_is_blind_at_the_adapter_not_just_the_model() -> None:
    # ``providers/groq.py::_messages`` returns ``list[dict[str, str]]`` and never
    # reads ``prompt.attachments``, so no model name makes it able to see.
    assert brain_accepts_images("groq", "gemini-ish-vision") is False


def test_a_turn_only_needs_vision_when_image_bytes_really_arrived() -> None:
    assert _turn_has_image([PHOTO]) is True
    assert _turn_has_image([CSV]) is False
    assert _turn_has_image([]) is False
    emptied = ResolvedMedia("asset-photo", b"", "image/png", "sha-photo", role="inspection")
    assert _turn_has_image([emptied]) is False


def test_british_spelling_does_not_send_a_photo_turn_to_the_fast_brain() -> None:
    # Reported verbatim as "analyse this image". The hint list carried only the
    # American spelling, so the sentence read as small talk under 60 chars.
    assert is_casual_chat("analyse this image") is False
    assert is_casual_chat("analyze this image") is False


async def test_image_turn_recovery_does_not_offer_a_blind_brain() -> None:
    service = ConversationService(ROUTER_AND_GEMINI)

    unfiltered = await service._fallback_candidate_modes("real")
    assert ("agent-router", "agnes-2.5-flash") in unfiltered

    seeing = await service._fallback_candidate_modes("real", requires_vision=True)
    assert all(
        brain_accepts_images(mode, model) for mode, model in seeing
    ), "an image turn may only recover onto a brain that takes image input"


async def test_photo_turn_moves_onto_a_seeing_brain_and_reports_the_move() -> None:
    service = ConversationService(ROUTER_AND_GEMINI)
    request = _photo_request(ROUTER_AND_GEMINI)

    required, moved_off = await service._apply_vision_gate(request, [PHOTO])

    assert required is True
    assert moved_off == "agent-router:agnes-2.5-flash"
    assert brain_accepts_images(request.providerMode, request.brainModel), (
        "the turn must end up on a brain that can look at the photo"
    )


async def test_photo_turn_stays_where_the_user_pinned_it_when_that_brain_sees() -> None:
    service = ConversationService(ROUTER_AND_GEMINI)
    request = _photo_request(ROUTER_AND_GEMINI, providerMode="real")

    required, moved_off = await service._apply_vision_gate(request, [PHOTO])

    assert (required, moved_off) == (True, None)
    assert request.providerMode == "real"


async def test_text_turn_without_a_photo_is_left_on_the_router_brain() -> None:
    service = ConversationService(ROUTER_AND_GEMINI)
    request = _photo_request(ROUTER_AND_GEMINI)

    required, moved_off = await service._apply_vision_gate(request, [CSV])

    assert (required, moved_off) == (False, None)
    assert request.providerMode == "agent-router"


async def test_photo_turn_says_it_cannot_see_instead_of_inventing() -> None:
    service = ConversationService(BLIND_ONLY)
    request = _photo_request(BLIND_ONLY)

    with pytest.raises(HinaaError) as refused:
        await service._apply_vision_gate(request, [PHOTO])

    assert "will not guess" in refused.value.message
    assert refused.value.user_action_required is True
    assert refused.value.retryable is False, "a missing capability is not fixed by retrying"
