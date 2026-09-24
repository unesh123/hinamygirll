"""test_runtime_continuity_p0.py — P0 Real Chat Runtime Regression Battery

Tests the 8 exact runtime failure modes reported from production chat:
- Failure A & B: Generated image disappears / cannot be referenced ("tell me about this character")
- Failure C: Assistant denies its own image generation ("haven't generated any image")
- Failure D: Attached image data reaches prompt media attachments
- Failure E: Contextual image prompt compilation ("YEA GENERATE ME IMAGE" -> "Gojo Satoru", not "YEA GENERATE ME")
- Failure F: Slash command routing (/extract without URLs routes to search, /image cleans trailing 'imges')
- Failure G: Leaked UI/SVG and runtime tokens stripped from displayText
- Failure H: Social phrase controller adapts to user frustration and suppresses redundant greetings
- Ordinal resolution: "second one", "last one" resolves against tool_result_sets
"""
from __future__ import annotations

import pytest

from hinaa_api.dialogue_state import (
    AssetReferenceResolver,
    ConversationTurnState,
    DialogueAct,
    DialogueActResolver,
    EntityReferenceResolver,
    ImageRequestCompiler,
    SocialPhraseController,
    StateEvidenceGuard,
)
from hinaa_api.media.asset_store import get_asset_store
from hinaa_api.media.resolver import MediaResolver, ResolvedMedia
from hinaa_api.models import AssistantTurnPlan, ToolRequest, TurnRequest
from hinaa_api.services import (
    ConversationService,
    ParsedCommand,
    _clean_natural_speech_and_display,
)


@pytest.fixture()
def conv_state() -> ConversationTurnState:
    state = ConversationTurnState.empty("conv-runtime-001", "user-42")
    state.active_topic = "Naruto"
    state.active_entities = [
        {"type": "character", "name": "Naruto Uzumaki", "normalized": "naruto uzumaki"}
    ]
    state.last_generated_asset_ids = ["ast-naruto-001"]
    state.last_assistant_action = {
        "action": "image_generate",
        "prompt": "Naruto Uzumaki, sage mode",
        "subject": "Naruto Uzumaki",
        "completed": True,
    }
    state.active_assets = [
        {"asset_id": "ast-naruto-001", "url": "/api/v1/assets/ast-naruto-001", "type": "image"}
    ]
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Failure A & B: Asset Reference Resolution
# ─────────────────────────────────────────────────────────────────────────────

class TestAssetReferenceResolution:
    def test_detects_asset_reference_phrases(self):
        assert AssetReferenceResolver.is_asset_reference("what is the above shown image about")
        assert AssetReferenceResolver.is_asset_reference("tell me about this character")
        assert AssetReferenceResolver.is_asset_reference("what is in this picture")
        assert AssetReferenceResolver.is_asset_reference("the image you just generated")
        assert AssetReferenceResolver.is_asset_reference("second one")

    def test_resolves_latest_generated_asset_id(self, conv_state):
        asset_id = AssetReferenceResolver.resolve_asset_id("tell me about this character", conv_state)
        assert asset_id == "ast-naruto-001"

    def test_resolves_ordinal_reference_from_result_set(self, conv_state):
        conv_state.tool_result_sets = [{
            "result_set_id": "set-1",
            "tool": "image_search",
            "ordered_asset_ids": ["ast-first", "ast-second", "ast-third", "ast-fourth"],
        }]
        assert AssetReferenceResolver.resolve_asset_id("tell me about the second one", conv_state) == "ast-second"
        assert AssetReferenceResolver.resolve_asset_id("show me the last one", conv_state) == "ast-fourth"
        assert AssetReferenceResolver.resolve_asset_id("first one please", conv_state) == "ast-first"


# ─────────────────────────────────────────────────────────────────────────────
# Failure C: State Evidence Guard (Blocks False Denials)
# ─────────────────────────────────────────────────────────────────────────────

class TestStateEvidenceGuard:
    def test_intercepts_false_denial_when_image_was_generated(self, conv_state):
        false_denial = "I haven't actually generated any image in this session yet. Could you upload it?"
        user_text = "tell me about this character"
        guarded = StateEvidenceGuard.guard(false_denial, user_text, conv_state)

        assert "haven't actually generated" not in guarded
        assert "Naruto Uzumaki" in guarded

    def test_intercepts_denial_on_user_frustration(self, conv_state):
        false_denial = "Nothing came through in this session yet. What would you like help with?"
        user_text = "fuck the image you just generated"
        guarded = StateEvidenceGuard.guard(false_denial, user_text, conv_state)

        assert "Nothing came through" not in guarded
        assert "Naruto Uzumaki" in guarded
        assert "fix that" in guarded.lower() or "adjust" in guarded.lower()

    def test_passes_through_normal_grounded_response(self, conv_state):
        normal_response = "Naruto Uzumaki in Sage Mode is one of the strongest forms shown in the Pain arc."
        guarded = StateEvidenceGuard.guard(normal_response, "tell me about this character", conv_state)
        assert guarded == normal_response


# ─────────────────────────────────────────────────────────────────────────────
# Failure D: Attached Media Resolution
# ─────────────────────────────────────────────────────────────────────────────

class TestMediaAttachmentResolution:
    @pytest.mark.asyncio
    async def test_resolves_data_uri_and_stores_in_asset_store(self):
        # 1x1 transparent GIF data URI
        data_uri = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
        resolver = MediaResolver()
        resolved = await resolver.resolve(data_uri)

        assert resolved is not None
        assert resolved.asset_id is not None
        assert resolved.mime_type == "image/gif"
        # Must be retrievable from AssetStore
        stored = get_asset_store().get_asset(resolved.asset_id)
        assert stored is not None
        assert stored.id == resolved.asset_id


def _make_plan() -> AssistantTurnPlan:
    from hinaa_api.models import Emotion, Performance
    return AssistantTurnPlan(
        displayText="Hello",
        spokenText="Hello",
        language="en-US",
        emotion=Emotion(primary="neutral", intensity=0.5, valence=0.5, arousal=0.5),
        performance=Performance(
            facePreset="neutral",
            gesture="none",
            gazeTarget="camera",
            headMotion="none",
            blinkRate=0.5,
        ),
        memoryCandidates=[],
        toolRequests=[],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Failure E: Contextual Image Prompt Compilation
# ─────────────────────────────────────────────────────────────────────────────

class TestImageRequestCompiler:
    def test_compiles_generic_prompt_with_active_character(self):
        state = ConversationTurnState.empty("conv-gojo", "user-1")
        state.active_entities = [{"type": "character", "name": "Gojo Satoru"}]

        prompt, mode, style = ImageRequestCompiler.compile_image_prompt("YEA GENERATE ME IMAGE", state)
        assert "Gojo Satoru" in prompt
        assert "YEA GENERATE ME" not in prompt
        assert style == "anime"

    def test_compiles_expression_with_active_character(self):
        state = ConversationTurnState.empty("conv-gojo", "user-1")
        state.active_entities = [{"type": "character", "name": "Gojo Satoru"}]

        prompt, mode, style = ImageRequestCompiler.compile_image_prompt("make him smiling with blue eyes", state)
        assert "Gojo Satoru" in prompt
        assert "smiling" in prompt

    def test_compiles_explicit_alias_to_canonical(self):
        state = ConversationTurnState.empty("conv-naruto", "user-1")
        prompt, mode, style = ImageRequestCompiler.compile_image_prompt("generate an image of naruto in sage mode", state)
        assert "Naruto Uzumaki" in prompt


# ─────────────────────────────────────────────────────────────────────────────
# Failure F: Slash Command Routing
# ─────────────────────────────────────────────────────────────────────────────

class TestSlashCommandRouting:
    def test_extract_without_urls_routes_to_web_search(self):
        svc = ConversationService.__new__(ConversationService)
        cmd = ParsedCommand(command="extract", args="SOME INFO ABOUT NARUTO ANIME", raw="/extract SOME INFO ABOUT NARUTO ANIME")
        plan = _make_plan()
        svc._map_explicit_command(cmd, plan)

        assert len(plan.toolRequests) == 1
        assert plan.toolRequests[0].toolName == "web_search"
        assert "SOME INFO ABOUT NARUTO ANIME" in plan.toolRequests[0].parameters["query"]

    def test_extract_with_url_routes_to_web_extract(self):
        svc = ConversationService.__new__(ConversationService)
        cmd = ParsedCommand(command="extract", args="https://naruto.fandom.com/wiki/Naruto_Uzumaki", raw="/extract https://naruto.fandom.com/wiki/Naruto_Uzumaki")
        plan = _make_plan()
        svc._map_explicit_command(cmd, plan)

        assert len(plan.toolRequests) == 1
        assert plan.toolRequests[0].toolName == "web_extract"
        assert "https://naruto.fandom.com/wiki/Naruto_Uzumaki" in plan.toolRequests[0].parameters["urls"]

    def test_image_command_cleans_trailing_imges_word(self):
        svc = ConversationService.__new__(ConversationService)
        cmd = ParsedCommand(command="image", args="NARUTO IMGES", raw="/image NARUTO IMGES")
        plan = _make_plan()
        svc._map_explicit_command(cmd, plan)

        assert len(plan.toolRequests) == 1
        req = plan.toolRequests[0]
        assert req.toolName == "image_generate"
        assert "Naruto Uzumaki" in req.parameters["prompt"]
        assert "IMGES" not in req.parameters["prompt"]


# ─────────────────────────────────────────────────────────────────────────────
# Failure G: UI Internal / SVG Stripping
# ─────────────────────────────────────────────────────────────────────────────

class TestInternalTokensStripping:
    def test_strips_full_svg_blocks(self):
        leaked = 'Here is your chart: <svg width="100" height="100"><circle cx="50" cy="50" r="40"/></svg> Done!'
        cleaned, _ = _clean_natural_speech_and_display(leaked)
        assert "<svg" not in cleaned
        assert "</svg>" not in cleaned
        assert "<circle" not in cleaned
        assert "Here is your chart: Done!" in cleaned

    def test_strips_standalone_svg_lines(self):
        leaked = "Here is the response:\nsvg\nHave a great day!"
        cleaned, _ = _clean_natural_speech_and_display(leaked)
        assert "\nsvg\n" not in cleaned

    def test_strips_workflow_mode_tokens(self):
        leaked = "Job started workflow_mode generation_set_id ready!"
        cleaned, _ = _clean_natural_speech_and_display(leaked)
        assert "workflow_mode" not in cleaned
        assert "generation_set_id" not in cleaned


# ─────────────────────────────────────────────────────────────────────────────
# Failure H: Social Phrase Controller
# ─────────────────────────────────────────────────────────────────────────────

class TestSocialPhraseController:
    def test_frustration_strips_babe_and_companion_emojis(self, conv_state):
        response = "Babe! 💜 I'm right here! Let's get this done ✨"
        user_frustrated = "fuck this why is it broken"
        filtered = SocialPhraseController.filter(response, user_frustrated, conv_state)

        assert "Babe" not in filtered
        assert "💜" not in filtered
        assert "✨" not in filtered
        assert "I'm right here!" in filtered

    def test_active_topic_strips_fresh_session_greeting(self, conv_state):
        response = "Babe! What can I help you with today? Here is the Naruto breakdown."
        filtered = SocialPhraseController.filter(response, "tell me more", conv_state)

        assert "What can I help you with today?" not in filtered
        assert "Here is the Naruto breakdown." in filtered
