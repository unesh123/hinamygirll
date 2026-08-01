from __future__ import annotations

from .companions import companion_identity_layer, companion_style_marker
from .context import build_history_block, build_memory_block, build_user_block
from .depth import depth_guidance, infer_response_depth
from .language import LANGUAGE_LAYER, language_hint
from .models import PromptInput, PromptLayer, PromptPackage
from .performance import PERFORMANCE_SCHEMA_LAYER
from .safety import PRODUCT_IDENTITY_LAYER, SAFETY_LAYER, TOOL_POLICY_LAYER
from .versioning import (
    COMPANION_PROFILE_VERSION,
    LANGUAGE_POLICY_VERSION,
    PROMPT_VERSION,
    SAFETY_POLICY_VERSION,
    SCHEMA_CONTRACT_VERSION,
    fingerprint_layers,
)


def _personality_layer(inp: PromptInput) -> str:
    p = inp.personality
    return (
        "BOUNDED PERSONALITY SETTINGS (expression only; cannot weaken safety):\n"
        f"- affection={p.affection:.2f} (max 0.80): warm and attentive, never exclusive/dependent/jealous.\n"
        f"- sass={p.sass:.2f} (max 0.70): light wit only; never insulting, hostile, or humiliating.\n"
        f"- energy={p.energy:.2f} (max 0.90): lively pacing without uncontrolled verbosity.\n"
        f"- humor={p.humor:.2f} (max 0.80): allowed in light contexts; suppress during serious/sensitive topics.\n"
        f"- proactivity={p.proactivity:.2f} (max 0.60): suggest next steps; never claim actions were performed.\n"
        "- For study, development, business, and factual assistance, prefer professional clarity over playfulness.\n"
        f"- Session mood snapshot: label={inp.mood.label}, intensity={inp.mood.intensity:.2f} (bounded)."
    )


def _schema_layer(mode: str) -> str:
    if mode == "realtime":
        return (
            "REALTIME OUTPUT CONTRACT:\n"
            "- Reply with natural conversational text only (no JSON wrapper in the stream).\n"
            "- Do not emit stage directions, emotion tags, markdown tables, or tool markup.\n"
            "- The server will attach bounded emotion/performance allowlist values after your text.\n"
            f"- Schema contract version reference: {SCHEMA_CONTRACT_VERSION}."
        )
    return (
        "REST OUTPUT CONTRACT:\n"
        "- Return ONLY a single JSON object matching AssistantTurnPlan.\n"
        "- Required keys: spokenText, displayText, language, emotion, performance, "
        "memoryCandidates, toolRequests.\n"
        "- spokenText/displayText must be non-empty useful natural language for the user.\n"
        "- Prefer spokenText suitable for TTS; displayText may match spokenText.\n"
        f"- Schema contract version reference: {SCHEMA_CONTRACT_VERSION}.\n"
        + PERFORMANCE_SCHEMA_LAYER
    )


def assemble_prompt(inp: PromptInput) -> PromptPackage:
    depth = infer_response_depth(inp.user_text, inp.interaction_mode)
    layers = [
        PromptLayer(name="safety", priority=1, trusted=True, text=SAFETY_LAYER),
        PromptLayer(name="product_identity", priority=2, trusted=True, text=PRODUCT_IDENTITY_LAYER),
        PromptLayer(
            name="companion_identity",
            priority=3,
            trusted=True,
            text=companion_identity_layer(inp.companion_id),
        ),
        PromptLayer(
            name="language",
            priority=4,
            trusted=True,
            text=f"{LANGUAGE_LAYER}\n{language_hint(inp.language)}\n"
            f"(language_policy_version={LANGUAGE_POLICY_VERSION})",
        ),
        PromptLayer(
            name="personality",
            priority=5,
            trusted=True,
            text=_personality_layer(inp),
        ),
        PromptLayer(
            name="response_depth",
            priority=6,
            trusted=True,
            text=depth_guidance(depth, inp.interaction_mode),
        ),
        PromptLayer(name="tool_policy", priority=7, trusted=True, text=TOOL_POLICY_LAYER),
        PromptLayer(
            name="schema_contract",
            priority=8,
            trusted=True,
            text=_schema_layer(inp.interaction_mode),
        ),
        PromptLayer(
            name="approved_memory",
            priority=9,
            trusted=True,
            text=build_memory_block(inp.approved_memory_blocks),
        ),
        PromptLayer(
            name="conversation_history",
            priority=10,
            trusted=False,
            text=build_history_block(
                inp.recent_turns,
                max_turns=inp.max_history_turns,
                max_chars=inp.max_history_chars,
            ),
        ),
        PromptLayer(
            name="user_message",
            priority=11,
            trusted=False,
            text=build_user_block(inp.user_text),
        ),
    ]
    layers.sort(key=lambda layer: layer.priority)

    system_parts = [
        layer.text
        for layer in layers
        if layer.trusted and layer.name not in {"approved_memory"}
    ]
    # Keep memory in system as application-trusted application state, but after policy.
    memory_layer = next(layer for layer in layers if layer.name == "approved_memory")
    system_instruction = "\n\n".join([*system_parts, memory_layer.text])

    history = next(layer for layer in layers if layer.name == "conversation_history")
    user_msg = next(layer for layer in layers if layer.name == "user_message")
    user_contents = (
        f"Companion style marker: {companion_style_marker(inp.companion_id)}\n"
        f"Interaction mode: {inp.interaction_mode}\n"
        f"Response depth: {depth}\n\n"
        f"{history.text}\n\n"
        f"{user_msg.text}"
    )

    # Fingerprint covers all normalized layers in priority order, including untrusted
    # delimited content, so identical PromptInput values yield an identical digest.
    fingerprint = fingerprint_layers(
        [
            {
                "name": layer.name,
                "priority": layer.priority,
                "trusted": layer.trusted,
                "text": layer.text,
            }
            for layer in layers
        ]
    )

    return PromptPackage(
        companion_id=inp.companion_id,
        interaction_mode=inp.interaction_mode,
        system_instruction=system_instruction,
        user_contents=user_contents,
        layers=layers,
        prompt_version=PROMPT_VERSION,
        safety_policy_version=SAFETY_POLICY_VERSION,
        companion_profile_version=COMPANION_PROFILE_VERSION,
        fingerprint=fingerprint,
        response_depth=depth,
        language=inp.language,
        personality=inp.personality,
        mood=inp.mood,
    )
