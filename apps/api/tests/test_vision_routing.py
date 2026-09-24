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
from hinaa_api.prompts import PromptInput, assemble_prompt
from hinaa_api.prompts.assembly import attachment_directives
from hinaa_api.providers.agent_router import _anthropic_messages
from hinaa_api.providers.openai_llm import _messages
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


# ─── What the attached picture is FOR ────────────────────────────────────────
#
# The composer has always had a Face ID / Style / Inspect picker, and the chosen
# role was written into ``user_contents`` -- which two of the three brains never
# read, because ``openai_llm`` and ``agent_router`` rebuild the turn from
# ``raw_user_text``. So "make it like this" arrived as a bare caption, and a face
# reference got treated as a style reference. These tests pin the instruction to
# each prompt shape, not just to the field that happens to be easiest to fill.

FACE = ResolvedMedia(
    "asset-face", b"\x89PNG\r\n\x1a\nface", "image/png", "sha-face", role="face_reference"
)
STYLE = ResolvedMedia(
    "asset-style", b"\x89PNG\r\n\x1a\nstyle", "image/png", "sha-style", role="style_reference"
)


def _photo_package(attachments: tuple, text: str = "make it like this"):
    return assemble_prompt(
        PromptInput(
            companion_id="hinaa",
            interaction_mode="rest",
            user_text=text,
            language="mixed",
            attachments=attachments,
        )
    )


def _final_user_text(message) -> str:
    content = message["content"]
    if isinstance(content, str):
        return content
    return "\n".join(str(part.get("text", "")) for part in content if isinstance(part, dict))


async def test_the_role_on_the_request_is_what_reaches_the_resolved_media(monkeypatch) -> None:
    from hinaa_api import media as media_pkg

    seen: list[str | None] = []

    async def fake_resolve(self, reference: str, role: str | None = None):
        seen.append(role)
        return FACE

    monkeypatch.setattr(media_pkg.MediaResolver, "resolve", fake_resolve)
    service = ConversationService(ROUTER_AND_GEMINI)
    request = TurnRequest.model_validate(
        {
            "sessionId": "session-vision",
            "text": "make it like this",
            "companionId": "hinaa",
            "imageUrl": "data:image/png;base64,aW1hZ2U=",
            "attachments": [
                {"kind": "image", "role": "face_reference", "url": "data:image/png;base64,aW1hZ2U="}
            ],
        }
    )

    resolved = await service._resolve_turn_media(request)

    assert seen == ["face_reference"], "the picker's value must be the value the resolver gets"
    assert resolved[0].role == "face_reference"


def test_the_face_role_reaches_the_openai_style_prompt() -> None:
    package = _photo_package((FACE,))

    final = _final_user_text(_messages(package)[-1])

    assert "face to keep consistent" in final
    # The instruction is added beside his sentence, never in place of it.
    assert "make it like this" in final


def test_a_style_reference_is_not_read_as_a_face_reference() -> None:
    final = _final_user_text(_messages(_photo_package((STYLE,)))[-1])

    assert "art style" in final
    assert "face to keep consistent" not in final


def test_the_router_anthropic_shape_carries_the_role_too() -> None:
    final = _final_user_text(_anthropic_messages(_photo_package((FACE,)))[-1])

    assert "face to keep consistent" in final
    assert "make it like this" in final


def test_the_gemini_prompt_text_names_the_role_it_always_had() -> None:
    package = _photo_package((PHOTO,))

    assert "the picture to look at" in package.user_contents


def test_the_label_is_printed_verbatim_so_she_can_quote_it_back() -> None:
    final = _final_user_text(_messages(_photo_package((FACE,), "what did I label this as?"))[-1])

    assert 'Image #1 is labelled "face_reference"' in final
    assert "A label outranks what you think the picture shows" in final


def test_the_directive_sits_beside_his_words_not_only_in_the_reference_list() -> None:
    # Measured failure: buried in the list, flash-lite answered from its own read
    # of the pixels and overrode the label. Adjacent to the ask is the position
    # that has to hold.
    text = _photo_package((FACE,)).user_contents

    directive_at = text.index('Image #1 is labelled "face_reference"')
    ask_at = text.index("<user_message")
    refs_at = text.index("Attached Image References:")
    assert refs_at < directive_at < ask_at
    assert text.index("make it like this") > directive_at


def test_the_companion_persona_token_is_not_in_the_turn_she_reads() -> None:
    # "Companion style marker: hinaa-warm-loving-caring" headed the turn text and
    # two of three live probe turns answered that the picture WAS that style.
    text = _photo_package((STYLE,)).user_contents

    assert "hinaa-warm-loving-caring" not in text
    assert "style marker" not in text


def test_a_document_before_a_photo_does_not_renumber_the_photo() -> None:
    note = attachment_directives([CSV, FACE])

    assert 'Image #1 is labelled "face_reference"' in note
    assert "#2" not in note


def test_an_unknown_role_is_named_instead_of_vanishing() -> None:
    odd = ResolvedMedia("asset-x", b"\x89PNG", "image/png", "sha-x", role="vibe")

    assert 'marked by the user as "vibe"' in attachment_directives([odd])


def test_no_note_without_an_attachment_role() -> None:
    unlabelled = ResolvedMedia("asset-n", b"\x89PNG", "image/png", "sha-n")

    assert attachment_directives([]) == ""
    assert attachment_directives([CSV]) == ""
    assert attachment_directives([unlabelled]) == ""
