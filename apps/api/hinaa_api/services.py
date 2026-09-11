from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .config import Settings
from .errors import HinaaError
from .memory import SessionMemory
from .models import AssistantTurnPlan, CompanionId, ProviderMode, SpeechRequest, TurnRequest, ToolRequest, Emotion

if TYPE_CHECKING:  # pragma: no cover
    from .persistence.memory_service import MemoryService

from .prompts import PROMPT_VERSION, neutral_fallback_plan
from .prompts.turn_prompt import build_turn_prompt
from .providers.agent_router import AgentRouterOpenAIProvider, AgentRouterAnthropicProvider, ClaudeLLMProvider
from .providers.azure_speech import AzureSpeechProvider
from .providers.base import (
    LLMProvider,
    ProviderResult,
    STTProvider,
    TTSProvider,
)
from .providers.gemini import GeminiLLMProvider
from .providers.groq import GroqLLMProvider
from .providers.local import LocalLLMProvider, make_local_stt, make_local_tts
from .providers.mock import MockLLMProvider, MockSTTProvider, MockTTSProvider
from .providers.elevenlabs import ElevenLabsConfig, ElevenLabsHTTPStreamingProvider, ElevenLabsSTTProvider
from .providers.fish_audio import FishAudioConfig, FishAudioTTSProvider
from .providers.openai_llm import OpenAILLMProvider
from .providers.deepgram_voice import DeepgramTTSProvider, DeepgramSTTProvider
from .voice_profiles import resolve_calibration, resolve_voice

logger = logging.getLogger("hinaa.conversation")


@dataclass
class ParsedCommand:
    command: str
    args: str
    raw: str


@dataclass
class ParsedContext:
    kind: str
    source_id: str
    raw: str


def parse_composer_input(text: str) -> tuple[str, list[ParsedContext], ParsedCommand | None]:
    """Parse composer input for @context references and /commands.

    Returns: (plain_text, context_references, explicit_command)
    """
    if not text:
        return "", [], None

    contexts: list[ParsedContext] = []
    command: ParsedCommand | None = None
    plain_parts: list[str] = []

    parts = text.split(" ")
    i = 0
    while i < len(parts):
        part = parts[i]

        if part.startswith("@") and len(part) > 1:
            context_spec = part[1:]
            if ":" in context_spec:
                kind, source_id = context_spec.split(":", 1)
            else:
                kind, source_id = context_spec, "current"
            contexts.append(ParsedContext(kind=kind, source_id=source_id, raw=part))
            i += 1
            continue

        if part.startswith("/") and len(part) > 1:
            cmd_name = part[1:]
            args_parts: list[str] = []
            i += 1
            while i < len(parts):
                next_part = parts[i]
                if next_part.startswith("@") or next_part.startswith("/"):
                    break
                args_parts.append(next_part)
                i += 1
            command = ParsedCommand(
                command=cmd_name,
                args=" ".join(args_parts),
                raw=part + " " + " ".join(args_parts) if args_parts else part,
            )
            continue

        plain_parts.append(part)
        i += 1

    plain_text = " ".join(plain_parts).strip()
    return plain_text, contexts, command


def _durable_content(block: str) -> str:
    """Strip the ``memory:{id}: `` prefix from an approved durable block."""
    if ": " in block:
        return block.split(": ", 1)[1].strip()
    return block.strip()


CHARACTER_ENTITY_MAP: dict[str, str] = {
    "mikasa": "Mikasa Ackerman",
    "mikasa ackerman": "Mikasa Ackerman",
    "gojo": "Gojo Satoru",
    "gojo satoru": "Gojo Satoru",
    "levi": "Levi Ackerman",
    "levi ackerman": "Levi Ackerman",
    "eren": "Eren Yeager",
    "eren yeager": "Eren Yeager",
    "tanjiro": "Tanjiro Kamado",
    "tanjiro kamado": "Tanjiro Kamado",
    "nezuko": "Nezuko Kamado",
    "nezuko kamado": "Nezuko Kamado",
    "naruto": "Naruto Uzumaki",
    "naruto uzumaki": "Naruto Uzumaki",
    "sasuke": "Sasuke Uchiha",
    "sasuke uchiha": "Sasuke Uchiha",
    "luffy": "Monkey D. Luffy",
    "monkey d luffy": "Monkey D. Luffy",
    "zoro": "Roronoa Zoro",
    "roronoa zoro": "Roronoa Zoro",
    "sukuna": "Ryomen Sukuna",
    "ryomen sukuna": "Ryomen Sukuna",
    "itadori": "Yuji Itadori",
    "yuji itadori": "Yuji Itadori",
    "goku": "Son Goku",
    "son goku": "Son Goku",
}


def _dedupe_session_facts(
    session_memories: tuple[str, ...], approved_blocks: tuple[str, ...]
) -> tuple[str, ...]:
    """Drop ephemeral session facts already stored durably (avoid double injection)."""
    if not approved_blocks:
        return session_memories
    durable_keys = {_durable_content(block).lower() for block in approved_blocks}
    return tuple(fact for fact in session_memories if fact.strip().lower() not in durable_keys)


def _fact_category(fact: str) -> str:
    lowered = fact.lower()
    if lowered.startswith("user's name"):
        return "identity"
    if lowered.startswith(("user likes", "user dislikes")):
        return "preference"
    if lowered.startswith("user context"):
        return "context"
    return "other"


def _comparison_key(text: str) -> str:
    """Create a tolerant key for checking accidental response repetition."""
    return re.sub(r"[^\w]+", "", text.casefold(), flags=re.UNICODE)


def _remove_repeated_passages(text: str) -> str:
    """Keep the first copy of an identical paragraph or sentence.

    Provider output can occasionally repeat its answer during schema recovery or
    streaming completion. This guard is intentionally conservative: it removes
    only identical normalized passages and leaves differently worded details,
    Markdown lists, and code intact.
    """
    chunks = re.split(r"(\n{2,}|(?<=[.!?])\s+)", text.strip())
    seen: set[str] = set()
    kept: list[str] = []
    pending_separator = ""
    for chunk in chunks:
        if not chunk:
            continue
        if re.fullmatch(r"\n{2,}|\s+", chunk):
            pending_separator = chunk
            continue
        key = _comparison_key(chunk)
        if len(key) >= 20 and key in seen:
            continue
        if key:
            seen.add(key)
        if kept and pending_separator:
            kept.append(pending_separator)
        kept.append(chunk)
        pending_separator = ""
    return "".join(kept).strip()


def _spoken_summary_from_display(text: str, *, limit: int = 420) -> str:
    """Create a short natural voice route without reading Markdown syntax aloud."""
    plain = re.sub(r"```[\s\S]*?```", "", text)
    plain = re.sub(r"^\s{0,3}#{1,6}\s*", "", plain.strip(), flags=re.MULTILINE)
    plain = re.sub(r"^\s*[-*+]\s+", "", plain, flags=re.MULTILINE)
    plain = re.sub(r"^\|.*\|\s*$", "", plain, flags=re.MULTILINE)
    plain = plain.replace("`", "").replace("**", "").replace("__", "")
    plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
    sentences = [piece.strip() for piece in re.split(r"(?<=[.!?।])\s+", plain) if piece.strip()]
    summary: list[str] = []
    current_length = 0
    for sentence in sentences:
        if summary and current_length + len(sentence) + 1 > limit:
            break
        summary.append(sentence)
        current_length += len(sentence) + 1
        if len(summary) >= 3:
            break
    res = " ".join(summary).strip()
    if not res:
        res = plain[:limit].strip()
    return res


def _clean_natural_speech_and_display(text: str) -> tuple[str, bool]:
    """Clean leaked XML, thinking blocks, and stage directions (*laughs*, *मुस्कुराते हुए*, etc.).
    Returns (cleaned_text, had_laughter_or_smile)."""
    if not text:
        return "", False
    # Strip <think>...</think> or <thought>...</thought>
    cleaned = re.sub(r"<(?:think|thought)>[\s\S]*?</(?:think|thought)>", "", text, flags=re.IGNORECASE)
    # Strip any leaked XML tags
    cleaned = re.sub(
        r"</?(?:response|spokenText|displayText|content|message|language|emotion|performance|memoryCandidates|toolRequests)[^>]*>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Check for laughter or smile in stage directions or cues
    had_laughter = bool(
        re.search(
            r"[*(\[](?:[^*()\]]*?(?:laugh|chuckle|giggle|smile|smiling|haha|hehe|हंस|मुस्कुरा|ख़ुश)[^*()\]]*?)[*)\]]",
            cleaned,
            re.IGNORECASE,
        )
    )
    # Strip all asterisk stage directions, e.g. *laughs*, *मुस्कुराते हुए*, *smiles gently*, *sighs*
    cleaned = re.sub(r"\*[^*]+\*", "", cleaned)
    # Strip stage direction parentheses, e.g. (laughs), (giggles), (smiling softly), (मुस्कुराते हुए)
    cleaned = re.sub(
        r"\(\s*(?:laughs?|chuckles?|giggles?|smiles?|smiling|मुस्कुराते हुए|हंसते हुए|धीमे से मुस्कुराते हुए)[^)]*\)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Strip trailing emotion annotations like (happy=0.8, valence=0.5)
    cleaned = re.sub(
        r"\s*\([a-zA-Z_]+=[0-9.]+(?:,\s*[a-zA-Z_]+=[0-9.]+)*\)\s*$",
        "",
        cleaned,
    )
    # Normalize leftover whitespace
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned)
    return cleaned.strip(), had_laughter


def _apply_response_quality_guard(plan: AssistantTurnPlan, is_live: bool = False) -> None:
    """Normalize a completed plan without changing meaning or tool requests."""
    clean_display, display_laughed = _clean_natural_speech_and_display(plan.displayText)
    clean_spoken, spoken_laughed = _clean_natural_speech_and_display(plan.spokenText)

    plan.displayText = _remove_repeated_passages(clean_display)
    plan.spokenText = _remove_repeated_passages(clean_spoken)

    had_laughter = display_laughed or spoken_laughed
    if had_laughter:
        if not getattr(plan, "emotion", None) or getattr(plan.emotion, "primary", None) in {"neutral", "calm", None}:
            plan.emotion.primary = "happy"
            plan.emotion.intensity = max(getattr(plan.emotion, "intensity", 0.5), 0.75)
            plan.emotion.valence = 0.8
            plan.emotion.arousal = 0.6
        if not getattr(plan, "performance", None) or getattr(plan.performance, "facePreset", None) in {"neutral", "idle", None}:
            plan.performance.facePreset = "soft_smile"

    # Voice should complement a long display answer, not replay it verbatim.
    # Spoken text must NEVER recite long essays, outlines, bullet points, or code.
    if not is_live:
        has_pdf = any(t.toolName == "pdf_generate" for t in plan.toolRequests)
        has_image = any(t.toolName in {"image_search", "image_generate"} for t in plan.toolRequests)

        if has_pdf:
            plan.spokenText = "I've generated your assignment PDF! You can download it right below. ✨"
            return
        elif has_image:
            plan.spokenText = "Here are some pictures for you! ✨"
            return

        raw_spoken = plan.spokenText or ""
        # Check if spoken text contains structured markdown, code, or outlines that should never be spoken aloud
        has_forbidden_speech_structure = any(
            marker in raw_spoken for marker in ("```", "\n", "•", "|", "- ", "1. ")
        )
        is_verbatim_echo = len(plan.displayText) > 160 and (
            _comparison_key(plan.displayText) == _comparison_key(raw_spoken)
        )

        if has_forbidden_speech_structure or is_verbatim_echo:
            cleaned = _spoken_summary_from_display(raw_spoken or plan.displayText, limit=280)
            if cleaned:
                # Remove any stray newlines or bullet markers that slipped through
                cleaned = " ".join(cleaned.split())
                plan.spokenText = cleaned
            elif plan.displayText:
                plan.spokenText = " ".join(plan.displayText.split())[:280]



# ── Casual-chat fast path ──────────────────────────────────────────────────
# Reasoning brains (cx/gpt-5.6-sol, agent-router) spend hidden tokens before
# the first visible token, which is why social small talk feels slow. Short,
# conversational turns are routed to a fast non-reasoning model (OpenAI fast
# model while healthy, else Gemini flash) when one is configured; deep work
# keeps the reasoning brain. The heuristic biases toward "deep" — a mis-route
# here only costs latency, never answer quality. A dead fast-brain key is
# negative-cached so the turn falls through to the reasoning brain instead of
# failing (see ConversationService._fast_casual_provider).
_DEEP_TASK_HINTS = (
    "```",
    "code",
    "python",
    "typescript",
    "javascript",
    "react",
    "api",
    "sql",
    "database",
    "deploy",
    "bug",
    "error",
    "script",
    "function",
    "class",
    "write",
    "build",
    "create",
    "explain",
    "refactor",
    "fix",
    "debug",
    "test",
    "file",
    "folder",
    "project",
    "github",
    "git",
    "docker",
    "server",
    "config",
    "schema",
    "webhook",
    "branch",
    "commit",
    "pipeline",
    "agent",
    "llm",
    "model",
    "prompt",
    "how to",
    "setup",
    "install",
    "configure",
    "analyze",
    "review",
    "generate",
    "implement",
    "otakuxwear",
    "business",
    "price",
    "report",
    "strategy",
)
_CASUAL_HINTS = (
    "hi",
    "hello",
    "hey",
    "yo",
    "namaste",
    "namaskar",
    "\u0928\u092e\u0938\u094d\u0924\u0947",
    "\u0928\u092e\u0938\u094d\u0915\u093e\u0930",
    "kasto",
    "\u0915\u0938\u094d\u0924\u094b",
    "k cha",
    "\u0915\u0947 \u091b",
    "ke chha",
    "mood",
    "tired",
    "\u0925\u093e\u0915\u0947",
    "happy",
    "\u0916\u0941\u0938\u0940",
    "sad",
    "\u0926\u0941\u0916",
    "miss",
    "love",
    "\u092e\u093e\u092f\u093e",
    "maya",
    "thank",
    "\u0927\u0928\u094d\u092f\u0935\u093e\u0926",
    "bro",
    "ok",
    "okay",
    "hmm",
    "cool",
    "nice",
    "wow",
    "good morning",
    "good night",
    "good evening",
    "good afternoon",
    "how are",
    "how's",
    "hw r u",
    "haha",
    "lol",
)


# Casual hints match on word boundaries so "hi" never matches "this" and
# "miss" never matches "mission". Deep hints stay substring-matched on purpose:
# a false "deep" costs only latency, never answer quality.
_CASUAL_HINT_RE = re.compile(
    r"(?<![a-z0-9])(" + "|".join(re.escape(h) for h in _CASUAL_HINTS) + r")(?![a-z0-9])"
)


def _text_has_deep_hint(text: str | None) -> bool:
    lowered = (text or "").lower()
    return any(hint in lowered for hint in _DEEP_TASK_HINTS)


def is_casual_chat(
    text: str | None,
    history: tuple[tuple[str, str], ...] = (),
) -> bool:
    """True for short social turns that do not need the reasoning brain.

    Conservative by design: any deep-task hint, a long message, or recent
    history that is itself deep work keeps the reasoning brain — so the fast
    path can only make replies faster, never dumber. The history check stops
    a short continuation ("ok, do it now") from jumping to the fast model
    mid-refactor.
    """
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if len(lowered) > 140:
        return False
    if _text_has_deep_hint(lowered):
        return False
    # A brief follow-up can continue a deep task started in recent history.
    for _, history_text in history[-2:]:
        if _text_has_deep_hint(history_text):
            return False
    if len(lowered) <= 60:
        return True
    return _CASUAL_HINT_RE.search(lowered) is not None


class ProviderRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.mock_stt = MockSTTProvider()
        self.mock_llm = MockLLMProvider()
        self.mock_tts = MockTTSProvider()
        self.local_stt = make_local_stt(settings)
        self.local_llm = LocalLLMProvider()
        self.local_tts = make_local_tts(settings)

    def _require_real(self) -> None:
        if missing := self.settings.missing_real_configuration():
            raise HinaaError(
                "PROVIDER_CONFIGURATION_MISSING",
                f"Real mode is not configured. Missing backend variables: {', '.join(missing)}.",
                503,
                user_action_required=True,
            )

    def _require_openai_brain(self) -> None:
        if self.settings.active_openai_key is None:
            raise HinaaError(
                "PROVIDER_CONFIGURATION_MISSING",
                "OpenAI brain is not configured. Missing backend variable: OPENAI_API_KEY.",
                503,
                user_action_required=True,
            )

    def _require_custom_brain(self) -> None:
        if self.settings.active_custom_key is None or self.settings.active_custom_base_url is None:
            raise HinaaError(
                "PROVIDER_CONFIGURATION_MISSING",
                "Custom model gateway is not configured. Missing backend variables: "
                "OPENAI_CODEX_API_KEY and OPENAI_CODEX_BASE_URL.",
                503,
                user_action_required=True,
            )

    def _require_claude_brain(self) -> None:
        if self.settings.active_claude_key is None or self.settings.active_claude_base_url is None:
            raise HinaaError(
                "PROVIDER_CONFIGURATION_MISSING",
                "Claude is not configured. Add HINAA_CLAUDE_API_KEY (or ANTHROPIC_API_KEY) to apps/api/.env.local. "
                "Configure HINAA_CLAUDE_BASE_URL only when you intentionally use a compatible gateway.",
                503,
                user_action_required=True,
            )

    def _require_qwen_brain(self) -> None:
        if self.settings.active_qwen_key is None or self.settings.active_qwen_base_url is None:
            raise HinaaError(
                "PROVIDER_CONFIGURATION_MISSING",
                "Qwen is not configured. Add HINAA_QWEN_API_KEY (or QWEN_API_KEY) to apps/api/.env.local and restart the backend.",
                503,
                user_action_required=True,
            )

    def _require_agent_router_brain(self) -> None:
        if self.settings.active_agent_router_key is None or self.settings.active_agent_router_base_url is None:
            raise HinaaError(
                "PROVIDER_CONFIGURATION_MISSING",
                "Agent Router is not configured. Missing backend variables: "
                "AGENT_ROUTER_API_KEY and AGENT_ROUTER_BASE_URL.",
                503,
                user_action_required=True,
            )

    def stt(self, mode: str) -> STTProvider:
        if mode == "mock":
            return self.mock_stt
        if mode == "local":
            return self.local_stt
        if self.settings.deepgram_configured:
            assert self.settings.deepgram_api_key
            return DeepgramSTTProvider(
                api_key=self.settings.deepgram_api_key.get_secret_value(),
                base_url=self.settings.deepgram_base_url
            )
        if self.settings.elevenlabs_configured:
            assert self.settings.elevenlabs_api_key
            config = ElevenLabsConfig(
                api_key=self.settings.elevenlabs_api_key.get_secret_value(),
                base_url=self.settings.elevenlabs_base_url,
                voice_id=self.settings.elevenlabs_voice_id,
                model_id=self.settings.elevenlabs_stt_model_id,
            )
            return ElevenLabsSTTProvider(config)
        return self.local_stt

    def llm(
        self,
        mode: str,
        brain_model: str | None = None,
    ) -> LLMProvider:
        if mode == "mock":
            return self.mock_llm
        if mode == "local":
            return self.local_llm
        if mode == "groq":
            if not self.settings.groq_configured:
                raise HinaaError(
                    "PROVIDER_CONFIGURATION_MISSING",
                    "Groq mode is not configured. Missing backend variable: GROQ_API_KEY.",
                    503,
                    user_action_required=True,
                )
            assert self.settings.groq_api_key
            return GroqLLMProvider(
                self.settings.groq_api_key.get_secret_value(), self.settings.groq_model
            )
        if mode == "openai":
            self._require_openai_brain()
            active_openai_key = self.settings.active_openai_key
            assert active_openai_key
            try:
                model = self.settings.resolve_openai_model(brain_model)
            except ValueError as error:
                raise HinaaError(
                    "OPENAI_MODEL_NOT_ALLOWED",
                    str(error),
                    422,
                    retryable=False,
                    user_action_required=True,
                ) from error
            return OpenAILLMProvider(active_openai_key.get_secret_value(), model)
        if mode == "custom":
            self._require_custom_brain()
            active_custom_key = self.settings.active_custom_key
            active_custom_base_url = self.settings.active_custom_base_url
            assert active_custom_key and active_custom_base_url
            try:
                model = self.settings.resolve_custom_model(brain_model)
            except ValueError:
                # A stale saved model (e.g. removed from the gateway plan) must
                # not kill the whole voice turn — fall back to the default.
                logger.warning(
                    "custom gateway model %r not allowed; falling back to default %r",
                    brain_model,
                    self.settings.active_custom_model,
                )
                model = self.settings.active_custom_model
            return OpenAILLMProvider(
                active_custom_key.get_secret_value(),
                model,
                base_url=active_custom_base_url,
                provider_id="custom",
            )
        if mode == "claude":
            self._require_claude_brain()
            active_claude_key = self.settings.active_claude_key
            active_claude_base_url = self.settings.active_claude_base_url
            assert active_claude_key and active_claude_base_url
            try:
                model = self.settings.resolve_claude_model(brain_model)
            except ValueError as error:
                raise HinaaError(
                    "CLAUDE_MODEL_NOT_ALLOWED",
                    str(error),
                    422,
                    retryable=False,
                    user_action_required=True,
                ) from error
            if self.settings.active_claude_protocol == "openai-compatible":
                return OpenAILLMProvider(
                    active_claude_key.get_secret_value(),
                    model,
                    base_url=active_claude_base_url,
                    provider_id="claude",
                )
            return ClaudeLLMProvider(
                api_key=active_claude_key.get_secret_value(),
                model=model,
                base_url=active_claude_base_url,
            )
        if mode == "qwen":
            self._require_qwen_brain()
            active_qwen_key = self.settings.active_qwen_key
            active_qwen_base_url = self.settings.active_qwen_base_url
            assert active_qwen_key and active_qwen_base_url
            try:
                model = self.settings.resolve_qwen_model(brain_model)
            except ValueError as error:
                raise HinaaError(
                    "QWEN_MODEL_NOT_ALLOWED",
                    str(error),
                    422,
                    retryable=False,
                    user_action_required=True,
                ) from error
            return OpenAILLMProvider(
                active_qwen_key.get_secret_value(),
                model,
                base_url=active_qwen_base_url,
                provider_id="qwen",
            )
        if mode == "agent-router":
            self._require_agent_router_brain()
            active_agent_router_key = self.settings.active_agent_router_key
            active_agent_router_base_url = self.settings.active_agent_router_base_url
            assert active_agent_router_key and active_agent_router_base_url
            try:
                model = self.settings.resolve_agent_router_model(brain_model)
            except ValueError as error:
                raise HinaaError(
                    "AGENT_ROUTER_MODEL_NOT_ALLOWED",
                    str(error),
                    422,
                    retryable=False,
                    user_action_required=True,
                ) from error
            return AgentRouterOpenAIProvider(
                api_key=active_agent_router_key.get_secret_value(),
                model=model,
                base_url=active_agent_router_base_url,
            )
        if mode == "cx-gateway":
            if not self.settings.cx_gateway_configured:
                raise HinaaError(
                    "PROVIDER_CONFIGURATION_MISSING",
                    "CX Gateway needs CX_GATEWAY_API_KEY and CX_GATEWAY_BASE_URL.",
                    503,
                    user_action_required=True,
                )
            active_cx_key = self.settings.active_cx_key
            active_cx_base_url = self.settings.active_cx_base_url
            assert active_cx_key and active_cx_base_url
            try:
                model = self.settings.resolve_cx_model(brain_model)
            except ValueError:
                model = self.settings.cx_gateway_model
            return OpenAILLMProvider(
                active_cx_key.get_secret_value(),
                model,
                base_url=active_cx_base_url,
                provider_id="cx-gateway",
            )
        if mode == "real":
            # The historical "real" mode means Gemini brain + a voice provider.
            # Gate on full real-mode configuration so a missing key raises a
            # typed, user-actionable error instead of an AssertionError that
            # surfaces as an opaque 500 in the stream.
            self._require_real()

        assert self.settings.gemini_api_key
        try:
            model = self.settings.resolve_gemini_model(brain_model)
        except ValueError as error:
            raise HinaaError(
                "GEMINI_MODEL_NOT_ALLOWED",
                str(error),
                422,
                retryable=False,
                user_action_required=True,
            ) from error
        return GeminiLLMProvider(self.settings.gemini_api_key.get_secret_value(), model)

    def tts(self, mode: str, companion_id: CompanionId | None = None) -> TTSProvider:
        if mode == "mock":
            return self.mock_tts
        if mode == "local":
            return self.local_tts
        if companion_id == "hiro" and self.settings.deepgram_configured:
            assert self.settings.deepgram_api_key
            return DeepgramTTSProvider(
                api_key=self.settings.deepgram_api_key.get_secret_value(),
                base_url=self.settings.deepgram_base_url
            )
        # Fish Audio is the preferred multilingual TTS (Nepali/English)
        # when configured WITH a voice id; ElevenLabs and Azure remain
        # fallbacks when the key exists but no voice is chosen yet.
        if self.settings.fish_audio_configured and self.settings.fish_audio_voice_ids[0]:
            assert self.settings.fish_audio_api_key
            return FishAudioTTSProvider(
                FishAudioConfig(
                    api_key=self.settings.fish_audio_api_key.get_secret_value(),
                    base_url=self.settings.fish_audio_base_url,
                    voice_id=self.settings.fish_audio_voice_ids[0],
                    model_id=self.settings.fish_audio_model_id,
                    output_format=self.settings.fish_audio_output_format,
                    request_timeout_s=self.settings.fish_audio_timeout_seconds,
                )
            )
        if self.settings.elevenlabs_configured:
            assert self.settings.elevenlabs_api_key
            config = ElevenLabsConfig(
                api_key=self.settings.elevenlabs_api_key.get_secret_value(),
                base_url=self.settings.elevenlabs_base_url,
                voice_id=self.settings.elevenlabs_voice_id,
                model_id=self.settings.elevenlabs_model_id,
                output_format=self.settings.elevenlabs_output_format,
            )
            return ElevenLabsHTTPStreamingProvider(config)
        if self.settings.azure_configured:
            assert self.settings.azure_speech_key and self.settings.azure_speech_region
            return AzureSpeechProvider(
                self.settings.azure_speech_key.get_secret_value(),
                self.settings.azure_speech_region,
            )
        return self.local_tts


class ConversationService:
    def __init__(
        self,
        settings: Settings,
        memory_service: MemoryService | None = None,
    ) -> None:
        self.settings = settings
        self.router = ProviderRouter(settings)
        self.memory = SessionMemory(settings.session_limit, settings.session_turn_limit)
        self.memory_service = memory_service
        # (user_id, session_id) -> set[str] of facts already pushed to the
        # durable store, so per-turn appends never rewrite the same facts.
        # OrderedDict + cap so long-running servers cannot leak memory here
        # even though SessionMemory evicts its own sessions.
        self._persisted_facts: OrderedDict[tuple[str, str], set[str]] = OrderedDict()
        # Fast-brain key health cache: provider_id -> monotonic time until which
        # the key is treated as bad. Prevents hammering a deactivated/expired
        # key (401) on every casual turn when a working brain is available.
        self._fast_key_bad_until: dict[str, float] = {}

    def _fast_key_bad(self, provider_id: str) -> bool:
        return self._fast_key_bad_until.get(provider_id, 0.0) > time.monotonic()

    def _mark_fast_key_bad(self, provider_id: str) -> None:
        # 10-minute negative cache: a dead key is retried only after the window
        # lapses (in case the user fixes their account mid-session).
        self._fast_key_bad_until[provider_id] = time.monotonic() + 600

    def _mark_persisted(self, user_id: str, session_id: str, fact: str) -> None:
        key = (user_id, session_id)
        if key not in self._persisted_facts:
            self._persisted_facts[key] = set()
            while len(self._persisted_facts) > 512:
                self._persisted_facts.popitem(last=False)
        else:
            self._persisted_facts.move_to_end(key)
        self._persisted_facts[key].add(fact)

    def _fast_casual_provider(
        self,
        mode: str,
        text: str,
        history: tuple[tuple[str, str], ...] = (),
    ) -> LLMProvider | None:
        """Route short social turns around reasoning brains to a fast model.

        Reasoning brains (cx-gateway / agent-router) spend hidden tokens before
        the first visible one; casual chat does not need that depth. Fast-brain
        order: OpenAI fast model (while its key is healthy) -> Gemini flash
        (working key) -> None, which leaves the turn on the reasoning brain.
        A deactivated OpenAI key therefore never fails a turn: it is negative-
        cached and casual chat silently uses Gemini, and if neither fast brain
        is available the configured reasoning brain answers as before.
        """
        if mode not in {"cx-gateway", "agent-router"}:
            return None
        if not is_casual_chat(text, history):
            return None
        # 1) OpenAI fast model while its key is known-good.
        if self.settings.openai_configured and not self._fast_key_bad("openai"):
            key = self.settings.active_openai_key
            if key is not None:
                try:
                    model = self.settings.resolve_openai_model(
                        self.settings.openai_fast_model
                    )
                except ValueError:
                    model = self.settings.openai_model
                logger.info(
                    "casual fast path engaged (%s -> openai:%s)",
                    mode,
                    model,
                )
                return OpenAILLMProvider(key.get_secret_value(), model)
        # 2) Gemini flash as the fast brain when OpenAI is unavailable.
        if self.settings.gemini_configured and not self._fast_key_bad("gemini"):
            key = self.settings.gemini_api_key
            if key is not None:
                model = self.settings.gemini_model
                logger.info(
                    "casual fast path engaged (%s -> gemini:%s)",
                    mode,
                    model,
                )
                return GeminiLLMProvider(key.get_secret_value(), model)
        return None

    def _approved_blocks(self, user_id: str | None) -> tuple[str, ...]:
        """Durable approved memory blocks for this user, or () when not available."""
        if user_id is None or self.memory_service is None:
            return ()
        try:
            return self.memory_service.approved_memory_blocks(user_id)
        except HinaaError:
            # Unknown/disabled user must never break a conversation turn.
            return ()

    def _persist_learned_memories(self, user_id: str | None, session_id: str) -> None:
        """Push this session's self-learned facts into the durable store (best effort).

        Consent contract (ADR-007): the store logs a consent event per write, the
        user's memory toggle is enforced by ``remember()``, sensitive content is
        blocked by the store, and a store failure never fails the live turn.
        """
        if user_id is None or self.memory_service is None:
            return
        facts = self.memory.learned_memories(session_id)
        if not facts:
            return
        key = (user_id, session_id)
        persisted = self._persisted_facts.get(key)
        if persisted is None:
            persisted = set()
            self._persisted_facts[key] = persisted
            while len(self._persisted_facts) > 512:
                self._persisted_facts.popitem(last=False)
        else:
            self._persisted_facts.move_to_end(key)
        for fact in facts:
            if fact in persisted:
                continue
            try:
                self.memory_service.remember(
                    user_id,
                    fact,
                    category=_fact_category(fact),
                    # source_turn_ref column is String(80); session ids may be
                    # up to 80 chars, so bound the ref to never overflow on
                    # PostgreSQL (SQLite ignores length, Postgres does not).
                    source_turn_ref=f"session:{session_id[:60]}",
                    explicit=True,
                )
            except HinaaError as error:
                # MEMORY_DISABLED / MEMORY_SENSITIVE_BLOCKED / MEMORY_INVALID:
                # durable memory is best-effort; the conversation continues.
                logger.debug("durable memory persist skipped (%s): %r", error.code, fact)
                if error.code != "MEMORY_DISABLED":
                    # Content-level rejections will never succeed on retry;
                    # mark them attempted to avoid re-trying every turn. The
                    # disabled case is left retryable so re-enabling mid-session
                    # still picks up facts.
                    self._mark_persisted(user_id, session_id, fact)
                continue
            except Exception as error:  # pragma: no cover - defensive
                # Any store failure (DB outage, constraint, lock) must never
                # fail the live turn — the docstring guarantee.
                logger.warning(
                    "durable memory persist failed unexpectedly (%s): %r",
                    type(error).__name__,
                    fact,
                )
                continue
            self._mark_persisted(user_id, session_id, fact)

    async def transcribe(self, pcm: bytes, language: str, mode: str) -> ProviderResult[str]:
        try:
            async with asyncio.timeout(self.settings.provider_timeout_seconds):
                return await self.router.stt(mode).transcribe(pcm, language)
        except TimeoutError as error:
            raise HinaaError(
                "PROVIDER_TIMEOUT", "Speech transcription took too long.", 504, True
            ) from error

    def _inject_deterministic_tool_intents(
        self,
        text: str,
        plan: AssistantTurnPlan,
        session_id: str | None = None,
        turn_request: Any = None,
    ) -> None:
        """Add only unambiguous, imperative local tool requests.

        This deliberately does not behave like a keyword detector.  Explanations,
        negations, quoted examples, capability questions, and historical wording
        remain conversational text.  Ambiguous requests are left to the selected
        model rather than causing an unexpected side effect.
        """
        # First, parse explicit commands from composer
        plain_text, parsed_contexts, parsed_command = parse_composer_input(text)
        
        # If there's an explicit command, map it to a tool request
        if parsed_command:
            self._map_explicit_command(parsed_command, plan)
        
        # Detect artifact follow-up questions (e.g., "where is the pdf file?")
        self._detect_artifact_lookup(plain_text, plan)

        # Forward any turn attachments and image engine to image-related tool requests
        if turn_request:
            has_attachment = bool(
                getattr(turn_request, "attachment_ids", None)
                or getattr(turn_request, "reference_images", None)
                or getattr(turn_request, "imageUrl", None)
                or getattr(turn_request, "attachments", None)
            )
            image_engine = getattr(turn_request, "imageEngine", None)
            att_ids = getattr(turn_request, "attachment_ids", [])
            ref_imgs = getattr(turn_request, "reference_images", [])
            img_url = getattr(turn_request, "imageUrl", None)
            raw_atts = getattr(turn_request, "attachments", [])

            for tr in plan.toolRequests:
                if tr.toolName in ("image_generate", "image_upscale", "image_relight"):
                    if image_engine and "engine" not in tr.parameters:
                        tr.parameters["engine"] = image_engine
                    if has_attachment:
                        if att_ids and "attachment_ids" not in tr.parameters:
                            tr.parameters["attachment_ids"] = att_ids
                        if ref_imgs and "reference_images" not in tr.parameters:
                            tr.parameters["reference_images"] = ref_imgs
                        if img_url and "imageUrl" not in tr.parameters:
                            tr.parameters["imageUrl"] = img_url
                        if raw_atts and "references" not in tr.parameters:
                            tr.parameters["references"] = raw_atts
        
        # Continue with existing deterministic intent detection on plain text
        lower_text = plain_text.casefold().strip()
        unquoted = re.sub(r"[\"'“”‘’][^\"'“”‘’]*[\"'“”‘’]", "", lower_text).strip()
        blocked_framing = (
            r"\b(do not|don't|dont|never|not\s+(?:want|need|search|fetch|generate|show|use|take|include|rely)|don't\s+use|dont\s+use|may|might|later|example|phrase|"
            r"explain|why did|how does|how to|can hinaa|is it possible)\b"
        )
        if re.search(blocked_framing, lower_text):
            return

        if re.search(r"\b(?:not|don't|dont)\s+(?:use|take|include|fetch|search|display|show)\b", unquoted, re.I):
            return

        def is_command(patterns: list[str], *, target: str) -> bool:
            if not re.search(target, unquoted, re.IGNORECASE):
                return False
            return any(re.search(pattern, unquoted, re.IGNORECASE) for pattern in patterns)

        # Flexible, natural image search trigger supporting prefixes, typos (sho/show), and mid-sentence entities
        has_image_kw = bool(re.search(r"\b(images?|pictures?|photos?|pics?|imgs?|wallpaper|wallpapers?|तस्वीरें|चित्र|फोटो)\b", unquoted, re.I))
        has_fetch_verb = bool(re.search(r"\b(show|sho|display|find|search|get|fetch|bring|see|load|look\s+for|ढूँढ|खोज|दिखा|लाओ)\b", unquoted, re.I))
        is_followup_fetch = bool(re.search(r"\b(?:fetch|show|sho|get|see|display|load|bring)\s+(?:them|it|these|those)\b", unquoted, re.I))
        is_generate_action = bool(re.search(r"\b(generate|genrate|fenerate|generat|create|creat|make|draw|paint|render|बनाओ|बनाऊ|बनाइदेऊ|गर)\b", unquoted, re.I))
        has_reference_intent = bool(re.search(r"\b(reference|refrence|referance|as\s+ref|referencing|refer to)\b", unquoted, re.I))
        has_art_platform = bool(re.search(r"\b(pinterest|pintrest|pintrens|deviantart|safebooru|danbooru|pixiv|artstation)\b", unquoted, re.I))
        is_character_visual = bool(
            (has_fetch_verb or has_image_kw or len(unquoted.split()) <= 4)
            and any(k in unquoted.lower().split() or k in unquoted.lower() for k in CHARACTER_ENTITY_MAP)
            and not is_generate_action
            and not has_reference_intent
            and not bool(re.search(r"\b(search the web|google search|information about|article|who is|wiki|history)\b", unquoted, re.I))
        )

        has_research_or_web_intent = bool(re.search(
            r"\b(research|investigate|study|paper|quantum|breakthrough|overview|summarize|documentation|tutorial|learn about|news about|latest development)\b",
            unquoted,
            re.I,
        ))

        is_image_refinement = False
        if session_id and not has_research_or_web_intent:
            try:
                history = self.memory.context(session_id)
                for role, content in reversed(history):
                    if content.strip().casefold() == plain_text.strip().casefold():
                        continue
                    if role == "user":
                        if re.search(r"\b(images?|pictures?|photos?|pics?|wallpaper|pinterest|pintrest|pintrens)\b", content, re.I):
                            # Must be a short refinement asking for different/more visual items
                            is_image_refinement = (
                                len(unquoted.split()) <= 7
                                and bool(re.search(r"\b(different|more|another|instead|next|pinterest|pintrest|wallpaper)\b", unquoted, re.I))
                            )
                        break
            except Exception:
                pass

        speech_text = str(getattr(plan, "speech", "") or "")
        speech_promised_images = False
        if re.search(r"(?:image results?|तस्वीरें|ढूँढ रही हूँ|खोज रही हूँ|searching for (?:public )?images?|here are (?:some )?images?)", speech_text, re.I):
            speech_promised_images = True

        image_search_command = (
            not is_generate_action
            and not has_reference_intent
            and not (has_research_or_web_intent and not has_image_kw and not has_art_platform)
            and (
                is_character_visual
                or (has_image_kw and (has_fetch_verb or len(unquoted.split()) <= 4))
                or is_followup_fetch
                or has_art_platform
                or is_image_refinement
                or speech_promised_images
            )
        )

        if image_search_command and not any(t.toolName == "image_search" for t in plan.toolRequests):
            query_candidate = re.sub(
                r"(?i)^\s*(?:like|please|pls|can\s+you|could\s+you|hey|babe|no\s*,?\s*|i\s+(?:just\s+)?(?:want|ont)\s+to\s+(?:see|view)?|what\s+about|how\s+about|what\s+of|and\s+what\s+about|and|now)\s*",
                "",
                plain_text,
            ).strip()
            query_candidate = re.sub(
                r"(?i)^\s*(?:search|find|look\s+for|show|sho|display|give\s+me|get|fetch|bring|see)\s+(?:me\s+)?(?:some\s+)?(?:public\s+)?(?:images?|pictures?|photos?|pics?|imgs?)?\s*(?:of|for|about)?\s*",
                "",
                query_candidate,
            ).strip()
            query_candidate = re.sub(r"(?i)\s+(?:too|as\s+well|please|pls)$", "", query_candidate).strip()
            # Strip trailing image and platform words (e.g. "mikasa images" -> "mikasa")
            query_candidate = re.sub(
                r"(?i)\s+(?:images?|pictures?|photos?|pics?|imgs?|wallpaper|wallpapers?|fanart|art|portrait|drawings?)$",
                "",
                query_candidate,
            ).strip()
            query_candidate = re.sub(
                r"(?i)\s+(?:on|from|in)?\s*(?:pinterest|pintrest|pintrens|safebooru|google|bro|please|pls|too|as\s+well)$",
                "",
                query_candidate,
            ).strip()
            query_candidate = re.sub(r"(?i)^(?:some\s+|me\s+|them\s+|these\s+|those\s+|a\s+few\s+)", "", query_candidate).strip()

            for alias, canonical in sorted(CHARACTER_ENTITY_MAP.items(), key=lambda x: -len(x[0])):
                if re.search(rf"\b{re.escape(alias)}\b", query_candidate, re.IGNORECASE):
                    query_candidate = re.sub(rf"\b{re.escape(alias)}\b", canonical, query_candidate, flags=re.IGNORECASE).strip()
                    break
            if query_candidate.lower() in CHARACTER_ENTITY_MAP:
                query_candidate = CHARACTER_ENTITY_MAP[query_candidate.lower()]

            if has_art_platform or is_image_refinement:
                clean_refine = re.sub(r"(?i)\b(bro|and|from|not\s+youtube|not\s+yt|youtube|please|pls|too|like|me|some)\b", "", plain_text).strip()
                clean_refine = re.sub(r"\s+", " ", clean_refine).strip()
                clean_refine = re.sub(r"(?i)\b(pintrens|pintrest)\b", "pinterest", clean_refine)
                if clean_refine:
                    query_candidate = clean_refine

            is_generic = (
                not query_candidate
                or bool(re.search(r"(?i)^(?:them|it|these|those|fetch\s+them|see\s+them|show\s+them|images?|pics?)$", query_candidate))
                or bool(re.search(r"(?i)^(?:i\s+)?(?:just\s+)?(?:want|ont)\s+to\s+.*(?:see|fetch|show|get)", query_candidate))
            )

            resolved_query = "" if is_generic else query_candidate
            if not resolved_query and session_id:
                try:
                    history = self.memory.context(session_id)
                    for role, content in reversed(history):
                        if role == "user":
                            # Skip the current turn if it was already appended before intent injection
                            if content.strip().casefold() == plain_text.strip().casefold():
                                continue
                            clean_prev = re.sub(r"^/[a-zA-Z0-9_-]+\s*", "", content).strip()
                            for _ in range(3):
                                clean_prev = re.sub(
                                    r"(?i)^(?:like|please|pls|can\s+you|could\s+you|sho\s+me|show\s+me|give\s+me|get\s+me|some|who is|what is|tell me about|explain|describe)\s+",
                                    "",
                                    clean_prev,
                                ).strip()
                            clean_prev = re.sub(r"(?i)\s+(?:too|as\s+well|please|pls)$", "", clean_prev).strip()
                            img_match = re.search(r"^(.*?)(?:\s+images?(?:\s+of|\s+from)?\s*(.*))?$", clean_prev, re.I)
                            if img_match and img_match.group(1).strip():
                                subject = img_match.group(1).strip()
                                extra = (img_match.group(2) or "").strip()
                                resolved_query = f"{subject} {extra}".strip()
                                break
                            elif clean_prev and not re.search(r"^(?:images?|pictures?|fetch them|see them)$", clean_prev, re.I):
                                resolved_query = clean_prev
                                break
                except Exception:
                    pass

            if not resolved_query and speech_text:
                subject_match = re.search(r"([A-Z][a-zA-Z0-9\s]+?)(?:\s+की|\s+के|\s+image|\s+pictures|\s+photos)", speech_text)
                if subject_match:
                    resolved_query = subject_match.group(1).strip()
                else:
                    entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", speech_text)
                    if entities:
                        resolved_query = entities[0]

            final_query = resolved_query or query_candidate or plain_text or text
            final_query = re.sub(r"(?i)^\s*(?:what\s+about|how\s+about|what\s+of|and\s+what\s+about|and|now)\s+", "", final_query).strip()
            for alias, canonical in sorted(CHARACTER_ENTITY_MAP.items(), key=lambda x: -len(x[0])):
                if re.search(rf"\b{re.escape(alias)}\b", final_query, re.IGNORECASE):
                    final_query = re.sub(rf"\b{re.escape(alias)}\b", canonical, final_query, flags=re.IGNORECASE).strip()
                    break
            if final_query.lower() in CHARACTER_ENTITY_MAP:
                final_query = CHARACTER_ENTITY_MAP[final_query.lower()]

            plan.toolRequests.append(ToolRequest(
                toolName="image_search",
                parameters={"query": final_query, "count": 6},
            ))

            clean_subject = final_query.title()
            if re.search(r"[\u0900-\u097F]", plain_text):
                plan.displayText = f"यहाँ {clean_subject} की कुछ तस्वीरें हैं! ✨"
                plan.spokenText = f"यहाँ {clean_subject} की कुछ तस्वीरें हैं!"
                plan.language = "hi-IN"
            else:
                plan.displayText = f"Here are some {clean_subject} pictures for you! ✨"
                plan.spokenText = f"Here are some {clean_subject} pictures for you!"
                plan.language = "en-US"
            plan.emotion = Emotion(primary="happy", intensity=0.7, valence=0.7, arousal=0.5)

        image_command = bool(
            re.search(r"\b(?:generate|create|make|draw|paint|render|बनाओ|बनाऊ|बनाइदेऊ|गर)\b.*\b(?:image|images|picture|pictures|photo|photos|portrait|artwork|wallpaper|चित्र|तस्वीर)\b", unquoted, re.I)
            or re.search(r"\b(?:image|images|picture|pictures|photo|photos|चित्र|तस्वीर)\s+(?:generate|create|make|draw|करो|गर)\b", unquoted, re.I)
            or re.search(r"^\s*(?:(?:hey\s+)?hinaa?[\s,]+)?(?:please\s+)?(?:draw|paint)\s+[a-z0-9]", unquoted, re.I)
            or is_command(
                [
                    r"^\s*(please\s+)?(generate|create|make|draw|paint|render|बनाओ|बनाऊ|बनाइदेऊ)\b",
                    r"^\s*(?:\d+|one|two|three|four|चार|एक|दुई|एउटा)?\s*(?:fast\s+|quality\s+)?(?:images?|pictures?|photos?|चित्र|तस्वीर)\s+(?:generate|create|make|करो|गर)\b",
                    r"^\s*(?:generate|create|make|बनाओ|बनाऊ|बनाइदेऊ)\b.*(?:image|picture|photo|चित्र|तस्वीर)",
                ],
                target=r"\b(image|images|picture|pictures|photo|photos|portrait|artwork|variation|variations)\b|चित्र|तस्वीर",
            )
        )
        if image_command and not any(t.toolName == "image_generate" for t in plan.toolRequests):
            prompt_str = plain_text
            prompt_str = re.sub(
                r"(?i)^\s*(?:(?:hey\s+)?hinaa?[\s,]+)?(?:please\s+)?(?:can\s+you\s+)?(?:could\s+you\s+)?(?:generate|create|make|draw|paint|render)\s+(?:me\s+)?(?:an?\s+)?(?:image|picture|photo|portrait)?\s*(?:of\s+)?",
                "",
                prompt_str,
            ).strip()
            prompt_str = re.sub(
                r"(?i)\s+(?:image|picture|photo|portrait|artwork|wallpaper)$",
                "",
                prompt_str,
            ).strip()
            prompt_str = re.sub(r"(?i)\b(?:please|pls|hinaa?)\b", "", prompt_str).strip()
            clean_prompt = prompt_str or plain_text or text
            # Expand known character names to canonical full names for better image quality
            # e.g. "gojo" → "Gojo Satoru", "mikasa" → "Mikasa Ackerman"
            clean_prompt_lower = clean_prompt.lower()
            for alias, canonical in sorted(CHARACTER_ENTITY_MAP.items(), key=lambda x: -len(x[0])):
                pattern = r"\b" + re.escape(alias) + r"\b"
                if re.search(pattern, clean_prompt_lower, re.IGNORECASE):
                    clean_prompt = re.sub(pattern, canonical, clean_prompt, flags=re.IGNORECASE)
                    break

            image_parameters: dict[str, object] = {
                "prompt": clean_prompt,
                "count": 1,
                "mode": "quality",
                "strategy": "variations",
            }
            lower_prompt = f"{clean_prompt.lower()} {lower_text}"
            if re.search(r"\b(ultra|hd|high quality|quality|poster|wallpaper|print)\b", lower_prompt):
                image_parameters["mode"] = "ultra" if "ultra" in lower_prompt else "quality"
            if re.search(r"\b(anime|manga|mangaka|mangal|एनिमे)\b|cel ?shad", lower_prompt, re.IGNORECASE):
                image_parameters["style"] = "anime"
            elif re.search(r"\b(photorealistic|realistic|photo real|dslr|portrait photo)\b", lower_prompt):
                image_parameters["style"] = "realistic"
            elif re.search(r"\b(cinematic|movie|film|trailer|poster)\b", lower_prompt):
                image_parameters["style"] = "cinematic"
            elif re.search(r"\b(3d|render|octane|cgi)\b", lower_prompt):
                image_parameters["style"] = "3d-art"
            elif re.search(r"\b(watercolor|painting|canvas art)\b", lower_prompt):
                image_parameters["style"] = "watercolor"

            # “Use that reference / like the images you found”
            reference_led = re.search(
                r"(?i)\b(based on|using|like|from)\s+(?:the\s+|that\s+|this\s+)?(?:same\s+)?"
                r"(?:earlier\s+|previous\s+|last\s+)?(?:reference(?:\s+image)?|image|picture|photo|result)\b",
                lower_text,
            ) or re.search(r"(?i)\bउसी\s+(?:तस्वीर|चित्र|रेफरेन्स)\b", lower_text)
            if reference_led:
                named = re.search(
                    r"(?i)(?:of|for|about|बाबत|को|की)\s+([A-Z][\w .,'-]{1,48}?)(?:\s+(?:based|using|like|image|picture|photo)\b|[.!?]\s*$|$)",
                    text,
                )
                subject = (named.group(1) if named else "").strip(" .,'")
                if not subject:
                    proper = re.search(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,3})\b", text)
                    subject = proper.group(1) if proper else ""
                if subject:
                    image_parameters["reference_query"] = subject
            plan.toolRequests.append(ToolRequest(toolName="image_generate", parameters=image_parameters))

        is_web_explicit = bool(re.search(r"\b(web|online|with\s+sources?)\b", lower_text))
        deep_research_command = not is_web_explicit and is_command(
            [
                r"^\s*(please\s+)?(deep\s*[- ]?research|dig\s+into\b|find\s+everything\s+about\b|fetch\s+(?:details|info)\s+about\b|tell\s+me\s+everything\s+about\b)",
                r"\b(deep\s+research|full\s+report|detailed\s+research)\b",
                r"(?i)^(?:बुझ|अध्यन|विस्तार(?:मा)?\s+बुझ)",
            ],
            target=r"\b(deep\s+research|full\s+report|detailed\s+research|everything|विस्तार)\b|अध्यन|बुझ",
        )
        if deep_research_command and not any(t.toolName == "deep_research" for t in plan.toolRequests):
            topic = re.sub(
                r"(?i)^\s*(?:please\s+)?(?:deep\s*[- ]?research|research\s+(?:on\s+|into\s+|me\s+)?|investigate\b|dig\s+into\b|fetch\s+(?:details|info)\s+about\s+|tell\s+me\s+|find\s+)?(?:everything|all\s+the\s+details|details|info)?\s*(?:about|on|of|for)?\s*",
                "",
                text,
            ).strip(" :.!?，,")
            if topic:
                plan.toolRequests.append(ToolRequest(
                    toolName="deep_research",
                    parameters={"topic": topic, "depth": 20},
                ))


        pdf_command = bool(
            re.search(r"\b(?:make|create|generate|give\s+me|build|write|download)\s+(?:me\s+)?(?:a\s+)?pdf\b", unquoted, re.I)
            or re.search(r"\bpdf\s+(?:file|document|of|on|about|for)\b", unquoted, re.I)
            or re.search(r"\b(?:assignment|report|paper|summary)\s+pdf\b", unquoted, re.I)
            or re.search(r"\bpdf\s+(?:banao|banau|dinu)\b", unquoted, re.I)
        )
        if pdf_command and not any(t.toolName == "pdf_generate" for t in plan.toolRequests):
            topic_str = plain_text
            topic_str = re.sub(r"(?i)\b(?:like|please|pls|hina|bro|can\s+you|could\s+you)\b", "", topic_str).strip()
            topic_str = re.sub(r"(?i)\b(?:i\s+need\s+to\s+complete\s+my\s+assignment|my\s+topic\s+is)\b", "", topic_str).strip()
            topic_str = re.sub(r"(?i)\b(?:make|create|generate|give\s+me|build|write)\s+(?:me\s+)?(?:a\s+)?pdf\s*(?:and\s+give\s+me)?\b", "", topic_str).strip()
            topic_str = re.sub(r"(?i)\b(?:make|give\s+me)\s+a?\s*pdf\b", "", topic_str).strip()
            topic_str = re.sub(r"[\"']", "", topic_str).strip()
            topic_str = re.sub(r"\s+", " ", topic_str).strip()
            if not topic_str or len(topic_str) < 3:
                topic_str = "Cryptography and Cyber Leaks"

            topic_str = re.sub(r"(?i)\bcryptogrpic\b", "Cryptography", topic_str)
            topic_str = re.sub(r"(?i)\bcryptogrp[a-z]*\b", "Cryptography", topic_str)

            plan.toolRequests.append(ToolRequest(
                toolName="pdf_generate",
                parameters={
                    "topic": topic_str,
                    "title": f"{topic_str.title()} Assignment Document",
                    "category": "Academic Assignment",
                },
            ))

            plan.displayText = (
                f"### 📄 Assignment PDF: {topic_str.title()}\n\n"
                f"I have compiled your assignment on **{topic_str.title()}** into a complete academic PDF document "
                f"with foundational theory, comparison tables, empirical case studies, and security countermeasures.\n\n"
                f"• **Document Type**: Academic Assignment (PDF)\n"
                f"• **Standards**: IEEE / NIST Format\n\n"
                f"Your PDF is compiled and ready for download below! ✨"
            )
            plan.spokenText = f"I've generated your {topic_str} assignment PDF! You can download it right below. ✨"
            plan.language = "en-US"
            plan.emotion = Emotion(primary="happy", intensity=0.8, valence=0.8, arousal=0.5)

        browser_command = is_command(
            [r"^\s*(please\s+)?(open|navigate to|go to|browse to|launch|खोलो|खोल्नुहोस्)\b"],
            target=r"\b(https?://\S+|website|url|page|site|netflix|youtube|google)\b",
        )
        if browser_command and not any(t.toolName in {"browser_navigate", "browser_execute_task"} for t in plan.toolRequests):
            prompt_str = re.sub(r"(?i)^\s*(?:please\s+)?(?:open|navigate to|go to|browse to|launch)\s+", "", text).strip()
            target = prompt_str or text
            known_destinations = {
                "netflix": "https://www.netflix.com",
                "youtube": "https://www.youtube.com",
                "google": "https://www.google.com",
            }
            destination = next((url for name, url in known_destinations.items() if re.search(rf"\b{name}\b", target, re.IGNORECASE)), None)
            explicit_url = re.search(r"https?://[^\s]+", target)
            if explicit_url:
                destination = explicit_url.group(0)
            if destination:
                # A direct destination is a single owned navigation, not an
                # autonomous browser sub-agent task.  It creates one page only.
                plan.toolRequests.append(ToolRequest(
                    toolName="browser_navigate",
                    parameters={"url": destination},
                ))

        cited_answer_command = is_command(
            [r"^\s*(please\s+)?(answer with sources|give (?:me )?a cited answer|verify online)\b"],
            target=r"\b(sources?|citations?|online|web|internet)\b|वेब|स्रोत",
        )
        if cited_answer_command and not any(t.toolName == "web_answer" for t in plan.toolRequests):
            prompt_str = re.sub(
                r"(?i)^\s*(?:please\s+)?(?:answer with sources|give (?:me )?a cited answer|verify online)\s*(?:for|about|:)?\s*",
                "",
                text,
            ).strip()
            plan.toolRequests.append(ToolRequest(
                toolName="web_answer",
                parameters={"query": prompt_str or text},
            ))

        extract_command = is_command(
            [r"^\s*(please\s+)?(read|extract|summarize)\b"],
            target=r"https?://[^\s]+",
        )
        if extract_command and not any(t.toolName == "web_extract" for t in plan.toolRequests):
            urls = re.findall(r"https?://[^\s]+", text)
            plan.toolRequests.append(ToolRequest(
                toolName="web_extract",
                parameters={"urls": urls[:5]},
            ))

        finance_command = is_command(
            [r"^\s*(please\s+)?(?:financial|finance) research\b"],
            target=r"\b(finance|financial|earnings|filing|stock|market|company)\b",
        )
        if finance_command and not any(t.toolName == "finance_research" for t in plan.toolRequests):
            prompt_str = re.sub(r"(?i)^\s*(?:please\s+)?(?:financial|finance) research\s*(?:on|about|:)?\s*", "", text).strip()
            plan.toolRequests.append(ToolRequest(
                toolName="finance_research",
                parameters={"query": prompt_str or text, "effort": "deep"},
            ))

        deep_research_command = is_command(
            [r"^\s*(please\s+)?(search and research|research|investigate|compare with sources|deep research)\b"],
            target=r"\b(web|internet|online|sources?|citations?|documentation|current|breakthrough|quantum|computing|technology|science|news|ai|market|development|history|theory)\b|वेब|स्रोत",
        )
        if deep_research_command and not any(t.toolName == "web_research" for t in plan.toolRequests):
            prompt_str = re.sub(
                r"(?i)^\s*(?:please\s+)?(?:search and research|research|investigate|compare with sources|deep research)\s*(?:the web for|online|with sources|about|into|on|:)?\s*",
                "",
                text,
            ).strip()
            plan.toolRequests.append(ToolRequest(
                toolName="web_research",
                parameters={"query": prompt_str or text, "effort": "lite"},
            ))

        search_command = is_command(
            [
                r"^\s*(please\s+)?(search the web for|look up|find information about|google search for|खोज|खोज्नुहोस्)\b",
                r"\b(give me|find me|show me|get me|fetch me)\b.*\b(links?|sites?|websites?|urls?|results?)\b",
                r"\b(latest|current|recent|new|best|top|popular)\b.*\b(sites?|websites?|links?|platforms?|services?|apps?)\b",
                r"\b(where can I|how can I|where to)\b.*\b(watch|stream|see|find|get)\b",
                r"\b(recommend|suggest|list)\b.*\b(sites?|websites?|links?|platforms?|services?)\b",
                r"\b(streaming|anime|movie|music|video)\b.*\b(sites?|websites?|links?|platforms?)\b",
                r"\b(search|find|look)\b.*\b(for|about|on)\b",
            ],
            target=r"\b(web|internet|online|google|documentation|sources?|links?|sites?|websites?|find|search|latest|current|recent|best|top|watch|stream|recommend|anime|movie|music|video)\b|वेब|इन्टरनेट|खोज",
        )
        if search_command and not any(t.toolName == "web_search" for t in plan.toolRequests):
            prompt_str = re.sub(
                r"(?i)^\s*(?:please\s+)?(?:search the web for|look up|find information about|google search for)\s+",
                "",
                text,
            ).strip()
            plan.toolRequests.append(ToolRequest(
                toolName="web_search",
                parameters={"query": prompt_str or text},
            ))

    def _map_explicit_command(self, parsed_command: ParsedCommand, plan: AssistantTurnPlan) -> None:
        """Map an explicit /command to a tool request."""
        cmd = parsed_command.command.lower()
        args = parsed_command.args.strip()

        # Extract flags like --seed=123 --model=flux-anime --mode=quality --count=2
        raw_tokens = args.split()
        clean_tokens = []
        flags: dict[str, Any] = {}
        for token in raw_tokens:
            if token.startswith("--") and "=" in token:
                k, v = token[2:].split("=", 1)
                flags[k.lower()] = int(v) if v.isdigit() else v
            else:
                clean_tokens.append(token)
        clean_args = " ".join(clean_tokens).strip()

        # 0. Character lookup shortcut (e.g. "/image gojo" or "/image mikasa")
        if clean_args.lower() in CHARACTER_ENTITY_MAP and not flags and cmd in {"image", "images", "img", "pics", "pictures", "search", "find"}:
            final_query = CHARACTER_ENTITY_MAP[clean_args.lower()]
            plan.toolRequests = [t for t in plan.toolRequests if t.toolName not in {"web_search", "image_search", "image_generate"}]
            plan.toolRequests.append(ToolRequest(
                toolName="image_search",
                parameters={"query": final_query, "count": 6},
            ))
            display_name = final_query.title()
            plan.displayText = f"Here are some {display_name} pictures for you! ✨"
            plan.spokenText = f"Here are some {display_name} pictures for you!"
            plan.language = "en-US"
            plan.emotion = Emotion(primary="happy", intensity=0.7, valence=0.7, arousal=0.5)
            return

        # 1. Image Generation Commands (/image, /draw, /generate, /imagine, /flux, /dalle)
        is_generate_cmd = cmd in {
            "image", "generate", "draw", "imagine", "create image",
            "generate image", "image_generate", "img", "dalle", "flux", "paint"
        }
        if is_generate_cmd:
            prompt_text = clean_args or "beautiful digital artwork"
            # Expand known character names to canonical full names
            _pt_lower = prompt_text.lower()
            for alias, canonical in sorted(CHARACTER_ENTITY_MAP.items(), key=lambda x: -len(x[0])):
                _pattern = r"\b" + re.escape(alias) + r"\b"
                if re.search(_pattern, _pt_lower, re.IGNORECASE):
                    prompt_text = re.sub(_pattern, canonical, prompt_text, flags=re.IGNORECASE)
                    break
            count = int(flags.get("count", 1))
            mode = flags.get("mode", "quality")
            seed = flags.get("seed")
            engine = flags.get("model") or flags.get("engine")

            gen_params: dict[str, Any] = {
                "prompt": prompt_text,
                "count": min(max(1, count), 4),
                "mode": mode,
            }
            if seed is not None:
                gen_params["seed"] = seed
            if engine:
                gen_params["engine"] = engine

            plan.toolRequests = [t for t in plan.toolRequests if t.toolName not in {"web_search", "image_search", "image_generate"}]
            plan.toolRequests.append(ToolRequest(
                toolName="image_generate",
                parameters=gen_params,
            ))
            display_model = f" [{engine}]" if engine else ""
            plan.displayText = f"Generating '{prompt_text}'{display_model} for you now! 🎨✨"
            plan.spokenText = f"Generating that image for you now!"
            plan.language = "en-US"
            plan.emotion = Emotion(primary="excited", intensity=0.8, valence=0.8, arousal=0.6)
            return

        # 2. Web Image Search Commands (/image_search, /find images, /wallpaper)
        has_image_kw = bool(re.search(r"\b(images?|pictures?|photos?|pics?|imgs?|wallpaper|wallpapers?|pinterest|pintrest|pintrens)\b", clean_args, re.I))
        is_search_image_cmd = (
            cmd in {
                "imagesearch", "image_search", "image search", "find images",
                "wallpaper", "wallpapers", "pinterest", "pintrest"
            }
            or (cmd in {"search", "find", "lookup"} and has_image_kw)
        )

        if is_search_image_cmd:
            clean_q = re.sub(r"(?i)\b(images?|pictures?|photos?|pics?|imgs?|wallpaper|wallpapers?|pinterest|pintrest|pintrens|bro|and|of|from|please|pls)\b", "", clean_args).strip()
            clean_q = re.sub(r"\s+", " ", clean_q).strip()
            if clean_q.lower() in CHARACTER_ENTITY_MAP:
                clean_q = CHARACTER_ENTITY_MAP[clean_q.lower()]
            final_query = clean_q or clean_args or "anime aesthetic"
            plan.toolRequests = [t for t in plan.toolRequests if t.toolName not in {"web_search", "image_search"}]
            plan.toolRequests.append(ToolRequest(
                toolName="image_search",
                parameters={"query": final_query, "count": 6},
            ))
            display_name = final_query.title()
            plan.displayText = f"Here are some {display_name} pictures for you! ✨"
            plan.spokenText = f"Here are some {display_name} pictures for you!"
            plan.language = "en-US"
            plan.emotion = Emotion(primary="happy", intensity=0.7, valence=0.7, arousal=0.5)
            return
        
        # 3. Map general commands to tool names
        command_to_tool: dict[str, tuple[str, dict]] = {
            "search": ("web_search", {"query": clean_args}),
            "find": ("web_search", {"query": clean_args}),
            "lookup": ("web_search", {"query": clean_args}),
            "web": ("web_search", {"query": clean_args}),
            "google": ("web_search", {"query": clean_args}),
            "research": ("web_research", {"query": clean_args, "effort": flags.get("effort", "lite")}),
            "investigate": ("web_research", {"query": clean_args, "effort": "standard"}),
            "deep research": ("web_research", {"query": clean_args, "effort": "deep"}),
            "answer": ("web_answer", {"query": clean_args}),
            "verify": ("web_answer", {"query": clean_args}),
            "extract": ("web_extract", {"urls": clean_args.split()}),
            "read": ("web_extract", {"urls": clean_args.split()}),
            "document": ("document_generate", {"title": clean_args or "Generated Document", "content": "", "format": flags.get("format", "pdf")}),
            "create doc": ("document_generate", {"title": clean_args or "Generated Document", "content": "", "format": "docx"}),
            "pdf": ("pdf_generate", {"topic": clean_args or "Academic Assignment", "title": clean_args or "Academic Document", "content": ""}),
            "gamma": ("create_gamma_presentation", {"topic": clean_args or "Presentation", "format": "presentation"}),
            "deck": ("create_gamma_presentation", {"topic": clean_args or "Pitch Deck", "format": "presentation"}),
            "gamma doc": ("create_gamma_presentation", {"topic": clean_args or "Document", "format": "document"}),
            "gamma webpage": ("create_gamma_presentation", {"topic": clean_args or "Webpage", "format": "webpage"}),
            "presentation": ("create_gamma_presentation", {"topic": clean_args or "Presentation Slides", "format": "presentation"}),
            "slides": ("create_gamma_presentation", {"topic": clean_args or "Presentation Slides", "format": "presentation"}),
            "analyze": ("analyze_text", {"target": clean_args, "focus": "summary"}),
            "summarize": ("summarize_text", {"target": clean_args, "length": "standard"}),
            "plan": ("create_plan", {"goal": clean_args, "horizon": "week"}),
            "play": ("play_music", {"query": clean_args}),
            "memory": ("memory_manage", {"action": "save", "content": clean_args}),
            "files": ("search_files", {"query": clean_args}),
            "model": ("switch_model", {"model": clean_args}),
            "voice": ("voice_config", {"action": "test", "provider": clean_args}),
            "avatar": ("avatar_config", {"action": "switch", "model": clean_args}),
            "settings": ("open_settings", {"section": clean_args}),
            "automate": ("create_automation", {"schedule": "", "task": clean_args, "tools": []}),
            "upscale": ("image_upscale", {"prompt": clean_args, "scale": 2}),
            "upscale image": ("image_upscale", {"prompt": clean_args, "scale": 2}),
            "relight": ("image_relight", {"lighting_prompt": clean_args or "studio lighting"}),
            "relight image": ("image_relight", {"lighting_prompt": clean_args or "studio lighting"}),
        }
        
        if cmd in command_to_tool:
            tool_name, base_params = command_to_tool[cmd]
            existing_req = next((t for t in plan.toolRequests if t.toolName == tool_name), None)
            if existing_req:
                for k, v in base_params.items():
                    if not existing_req.parameters.get(k):
                        existing_req.parameters[k] = v
            else:
                plan.toolRequests.append(ToolRequest(
                    toolName=tool_name,
                    parameters=base_params,
                ))

    def _detect_artifact_lookup(self, text: str, plan: AssistantTurnPlan) -> None:
        """Detect artifact follow-up questions and add lookup tool requests.
        
        Handles questions like:
        - "where is the pdf file?"
        - "where's my document?"
        - "show me the pdf"
        - "find the pdf"
        """
        lower_text = text.casefold().strip()
        
        # Patterns for artifact lookup questions
        artifact_patterns = [
            (r"\bwhere (is|'s|was) (the|my|a) (pdf|docx|pptx|document|image|video|audio|file)\b", "pdf"),
            (r"\b(find|show|get|locate) (the|my|a) (pdf|docx|pptx|document|image|video|audio|file)\b", "pdf"),
            (r"\b(pdf|docx|pptx|document) (file|artifact)? (where|location)\b", "pdf"),
        ]
        
        import re
        for pattern, default_kind in artifact_patterns:
            match = re.search(pattern, lower_text)
            if match:
                # Extract the artifact kind from the match
                kind_match = re.search(r"(pdf|docx|pptx|document|image|video|audio|file)", lower_text)
                kind = kind_match.group(1) if kind_match else default_kind
                if kind == "document":
                    kind = "pdf"
                
                # Add artifact lookup tool request
                if not any(t.toolName == "artifact_lookup" for t in plan.toolRequests):
                    plan.toolRequests.append(ToolRequest(
                        toolName="artifact_lookup",
                        parameters={"kind": kind, "sessionId": ""},
                    ))
                break

    def _fallback_candidate_modes(self, primary_mode: str) -> list[tuple[str, str | None]]:
        """Return candidate fallback (mode, model) in order of reliability."""
        candidates: list[tuple[str, str | None]] = []
        if self.settings.gemini_configured and primary_mode not in {"real", "gemini"}:
            candidates.append(("real", self.settings.gemini_model))
        if self.settings.claude_configured and primary_mode != "claude":
            candidates.append(("claude", self.settings.active_claude_model))
        if self.settings.qwen_configured and primary_mode != "qwen":
            candidates.append(("qwen", self.settings.active_qwen_model))
        if self.settings.groq_configured and primary_mode != "groq":
            candidates.append(("groq", self.settings.groq_model))
        return candidates

    async def _resolve_turn_media(self, request: TurnRequest) -> list[Any]:
        from .media import MediaResolver
        resolver = MediaResolver()
        resolved: list[Any] = []
        # Check attachment_ids
        for aid in (request.attachment_ids or []):
            try:
                res = await resolver.resolve(aid)
                resolved.append(res)
            except Exception:
                logger.warning("Failed to resolve attachment ID %s", aid, exc_info=True)
        # Check attachments
        for att in (request.attachments or []):
            aid = att.get("asset_id") or att.get("assetId")
            url = att.get("url")
            ref = aid if (aid and not str(aid).startswith("client-")) else (url or aid)
            if ref and ref not in (request.attachment_ids or []):
                try:
                    res = await resolver.resolve(ref, role=att.get("role"))
                    resolved.append(res)
                except Exception:
                    if url and url != ref:
                        try:
                            res = await resolver.resolve(url, role=att.get("role"))
                            resolved.append(res)
                        except Exception:
                            logger.warning("Failed to resolve attachment fallback %s", str(url)[:50], exc_info=True)
                    else:
                        logger.warning("Failed to resolve attachment %s", str(ref)[:50], exc_info=True)
        # Check imageUrl
        if request.imageUrl and not resolved:
            try:
                res = await resolver.resolve(request.imageUrl)
                resolved.append(res)
            except Exception:
                logger.warning("Failed to resolve imageUrl", exc_info=True)
        return resolved

    async def create_plan(
        self, request: TurnRequest, *, user_id: str | None = None
    ) -> ProviderResult[AssistantTurnPlan]:
        history = self.memory.context(request.sessionId)
        approved = self._approved_blocks(user_id)
        session_memories = _dedupe_session_facts(
            self.memory.learned_memories(request.sessionId), approved
        )
        resolved_media = await self._resolve_turn_media(request)
        prompt = build_turn_prompt(
            request=request,
            history=history,
            settings=self.settings,
            interaction_mode="rest",
            session_memories=session_memories,
            approved_memory_blocks=approved,
            attachments=tuple(resolved_media),
        )
        self._log_prompt_meta(request.sessionId, prompt.fingerprint, "rest")
        requested_provider = request.providerMode
        requested_model = request.brainModel
        resolved_provider = requested_provider
        resolved_model = requested_model
        is_fallback = False
        fallback_reason: str | None = None

        is_remote_primary = request.providerMode in ("claude", "agent-router", "cx-gateway", "custom")
        # Use the configured LLM timeout for all providers. The old 2.5s was far
        # too short for mwapi.dev (which needs 3-8s cold) and caused constant
        # timeouts. HINAA_LLM_TIMEOUT_SECONDS=90 from .env.local applies here.
        primary_plan_timeout = self.settings.llm_timeout_seconds

        try:
            async with asyncio.timeout(primary_plan_timeout):
                provider = self._fast_casual_provider(
                    request.providerMode, request.text, history
                )
                fast_provider_id = getattr(provider, "id", None)
                if provider is None:
                    provider = self.router.llm(
                        request.providerMode, request.brainModel
                    )
                result = await provider.create_plan(
                    request.text,
                    request.companionId,
                    request.language,
                    history,
                    prompt,
                )
        except (HinaaError, TimeoutError, Exception) as raw_error:
            if isinstance(raw_error, TimeoutError):
                error = HinaaError(
                    "PROVIDER_TIMEOUT",
                    f"Primary brain {request.providerMode} timed out after {primary_plan_timeout}s.",
                    504,
                    True,
                )
            elif isinstance(raw_error, HinaaError):
                error = raw_error
            else:
                error = HinaaError(
                    "PROVIDER_UNAVAILABLE",
                    str(raw_error) or "The selected brain could not complete this turn.",
                    503,
                    True,
                )

            retry_succeeded = False
            if fast_provider_id and error.code in {
                "PROVIDER_KEY_INVALID",
                "PROVIDER_UNAVAILABLE",
                "PROVIDER_RATE_LIMIT",
            }:
                # The fast brain (e.g. a deactivated key or schema failure) must
                # never fail the turn: negative-cache its key and retry
                # once with the configured reasoning brain.
                self._mark_fast_key_bad(fast_provider_id)
                logger.warning(
                    "casual fast provider %s failed (%s); retrying with %s",
                    fast_provider_id,
                    error.code,
                    request.providerMode,
                )
                provider = self.router.llm(
                    request.providerMode, request.brainModel
                )
                try:
                    async with asyncio.timeout(primary_plan_timeout):
                        result = await provider.create_plan(
                            request.text,
                            request.companionId,
                            request.language,
                            history,
                            prompt,
                        )
                    retry_succeeded = True
                except Exception as retry_err:
                    if isinstance(retry_err, HinaaError):
                        error = retry_err
                    else:
                        error = HinaaError("PROVIDER_UNAVAILABLE", str(retry_err), 503, True)

            if not retry_succeeded:
                if self.settings.auto_fallback_enabled and error.code in {
                    "PROVIDER_RATE_LIMIT",
                    "PROVIDER_UNAVAILABLE",
                    "PROVIDER_KEY_INVALID",
                    "PROVIDER_ACCOUNT_CAPACITY_UNAVAILABLE",
                    "PROVIDER_TIMEOUT",
                }:
                    fallback_result = None
                    for fb_mode, fb_model in self._fallback_candidate_modes(request.providerMode):
                        try:
                            logger.info(
                                "Primary brain %s failed with %s; falling back to %s (%s)",
                                request.providerMode,
                                error.code,
                                fb_mode,
                                fb_model,
                            )
                            fb_provider = self.router.llm(fb_mode, fb_model)
                            async with asyncio.timeout(max(45.0, primary_plan_timeout)):  # Enough for Gemini/other fallbacks
                                fallback_result = await fb_provider.create_plan(
                                    request.text,
                                    request.companionId,
                                    request.language,
                                    history,
                                    prompt,
                                )
                            logger.info("Fallback to %s succeeded", fb_mode)
                            is_fallback = True
                            fallback_reason = f"Primary {request.providerMode} failed: {error.code}"
                            resolved_provider = fb_mode
                            resolved_model = fb_model
                            break
                        except Exception as fb_exc:
                            logger.warning("Fallback provider %s failed: %r", fb_mode, fb_exc)
                    if fallback_result is not None:
                        result = fallback_result
                    else:
                        plan = neutral_fallback_plan(
                            user_text=request.text,
                            companion_id=request.companionId,
                            language=request.language,
                            depth=prompt.response_depth,
                        )
                        result = ProviderResult(plan, f"fallback:{PROMPT_VERSION}", 0)
                        is_fallback = True
                        fallback_reason = f"Candidate fallbacks exhausted ({error.code}): neutral fallback engaged"
                        resolved_provider = "neutral_fallback"
                        resolved_model = None
                elif error.code == "MODEL_RESPONSE_INVALID":
                    plan = neutral_fallback_plan(
                        user_text=request.text,
                        companion_id=request.companionId,
                        language=request.language,
                        depth=prompt.response_depth,
                    )
                    result = ProviderResult(plan, f"fallback:{PROMPT_VERSION}", 0)
                    is_fallback = True
                    fallback_reason = "MODEL_RESPONSE_INVALID: neutral fallback plan engaged"
                    resolved_provider = "neutral_fallback"
                    resolved_model = None
                else:
                    raise error
        _apply_response_quality_guard(result.value)
        result.value.requestedProvider = requested_provider
        result.value.requestedModel = requested_model
        result.value.resolvedProvider = resolved_provider
        result.value.resolvedModel = resolved_model
        result.value.fallback = is_fallback
        result.value.fallbackReason = fallback_reason
        result.value.latencyMs = result.latency_ms

        # Auto-persist learned memory candidates
        if getattr(result.value, "memoryCandidates", None):
            for candidate in result.value.memoryCandidates:
                try:
                    if self.memory_service and user_id:
                        self.memory_service.remember(
                            user_id=user_id,
                            content=candidate.content,
                            category=getattr(candidate, 'category', None) or "conversation",
                            source_turn_ref=f"auto:{request.conversationId or request.sessionId}",
                        )
                except Exception:
                    logger.debug("Failed to persist memory candidate: %s", candidate.content[:50], exc_info=True)

        self._inject_deterministic_tool_intents(
            request.text,
            result.value,
            session_id=request.sessionId,
            turn_request=request,
        )

        self.memory.append_turn(request.sessionId, request.text, result.value.model_dump_json())

        # Persist to durable storage
        try:
            if self.memory_service and user_id:
                self.memory_service.append_turn(
                    user_id=user_id,
                    companion_id=request.companionId or "hinaa",
                    conversation_id=request.conversationId or request.sessionId,
                    user_text=request.text,
                    assistant_text=result.value.model_dump_json(),
                    language=result.value.language or "mixed",
                    attachments=request.attachments or (
                        [{"asset_id": aid} for aid in request.attachment_ids] if request.attachment_ids else None
                    ),
                )
        except Exception:
            logger.warning("Failed to persist turn to database", exc_info=True)

        self._persist_learned_memories(user_id, request.sessionId)
        
        return result

    async def create_live_plan(
        self,
        request: TurnRequest,
        emit_delta: Callable[[str], Awaitable[None]],
        *,
        user_id: str | None = None,
    ) -> ProviderResult[AssistantTurnPlan]:
        from .providers.timing import ProviderTiming

        timing = ProviderTiming()
        history = self.memory.context(request.sessionId)
        approved = self._approved_blocks(user_id)
        session_memories = _dedupe_session_facts(
            self.memory.learned_memories(request.sessionId), approved
        )
        resolved_media = await self._resolve_turn_media(request)
        prompt = build_turn_prompt(
            request=request,
            history=history,
            settings=self.settings,
            interaction_mode="realtime",
            session_memories=session_memories,
            approved_memory_blocks=approved,
            attachments=tuple(resolved_media),
        )
        timing.mark("prompt_built")
        self._log_prompt_meta(request.sessionId, prompt.fingerprint, "realtime")
        fast_provider_id: str | None = None
        requested_provider = request.providerMode
        requested_model = request.brainModel
        resolved_provider = requested_provider
        resolved_model = requested_model
        is_fallback = False
        fallback_reason: str | None = None

        is_remote_primary = request.providerMode in ("claude", "agent-router", "cx-gateway", "custom")
        primary_live_timeout = self.settings.llm_timeout_seconds

        try:
            async with asyncio.timeout(primary_live_timeout):
                provider = self._fast_casual_provider(
                    request.providerMode, request.text, history
                )
                fast_provider_id = getattr(provider, "id", None)
                if provider is None:
                    provider = self.router.llm(
                        request.providerMode, request.brainModel
                    )
                if isinstance(provider, GeminiLLMProvider | GroqLLMProvider | OpenAILLMProvider | AgentRouterOpenAIProvider | AgentRouterAnthropicProvider):
                    result = await provider.create_live_plan(
                        request.text,
                        request.companionId,
                        request.language,
                        history,
                        emit_delta,
                        prompt,
                    )
                    stages = {"prompt_built": timing.ms_since_start("prompt_built") or 0}
                    if result.stages:
                        stages.update(result.stages)
                    result = ProviderResult(
                        result.value,
                        result.provider,
                        result.latency_ms,
                        stages=stages,
                    )
                else:
                    # Mock / non-streaming path: deltas are synthetic after full plan.
                    timing.mark("provider_client_ready")
                    timing.mark("request_sent")
                    result = await provider.create_plan(
                        request.text,
                        request.companionId,
                        request.language,
                        history,
                        prompt,
                    )
                    timing.mark("first_provider_event")
                    timing.mark("plan_parsed")
                    timing.mark("plan_validated")
                    display = result.value.displayText
                    for start in range(0, len(display), 7):
                        chunk = display[start : start + 7]
                        timing.mark("first_text_delta")
                        await emit_delta(chunk)
                        await asyncio.sleep(0.006)
                    timing.mark("text_complete")
                    result = ProviderResult(
                        result.value,
                        result.provider,
                        result.latency_ms,
                        stages=timing.snapshot(),
                    )
        except (HinaaError, TimeoutError, Exception) as raw_error:
            if isinstance(raw_error, TimeoutError):
                error = HinaaError(
                    "PROVIDER_TIMEOUT",
                    f"Live primary brain {request.providerMode} timed out after {primary_live_timeout}s.",
                    504,
                    True,
                )
            elif isinstance(raw_error, HinaaError):
                error = raw_error
            else:
                error = HinaaError(
                    "PROVIDER_UNAVAILABLE",
                    str(raw_error) or "The selected brain could not complete this live turn.",
                    503,
                    True,
                )
            live_retry_succeeded = False
            if fast_provider_id and error.code in {
                "PROVIDER_KEY_INVALID",
                "PROVIDER_UNAVAILABLE",
                "PROVIDER_RATE_LIMIT",
            }:
                self._mark_fast_key_bad(fast_provider_id)
                selected_provider = self.router.llm(request.providerMode, request.brainModel)
                if getattr(selected_provider, "id", None) != fast_provider_id:
                    try:
                        async with asyncio.timeout(primary_live_timeout):
                            if isinstance(selected_provider, GeminiLLMProvider | GroqLLMProvider | OpenAILLMProvider | AgentRouterOpenAIProvider | AgentRouterAnthropicProvider):
                                result = await selected_provider.create_live_plan(
                                    request.text,
                                    request.companionId,
                                    request.language,
                                    history,
                                    emit_delta,
                                    prompt,
                                )
                            else:
                                result = await selected_provider.create_plan(
                                    request.text,
                                    request.companionId,
                                    request.language,
                                    history,
                                    prompt,
                                )
                            live_retry_succeeded = True
                    except HinaaError as retry_err:
                        error = retry_err
                    except Exception as retry_error:
                        error = HinaaError(
                            "PROVIDER_UNAVAILABLE",
                            "The selected brain could not complete this live turn.",
                            503,
                            True,
                        )

            if not live_retry_succeeded:
                if self.settings.auto_fallback_enabled and error.code in {
                    "PROVIDER_KEY_INVALID",
                    "PROVIDER_UNAVAILABLE",
                    "PROVIDER_RATE_LIMIT",
                    "PROVIDER_ACCOUNT_CAPACITY_UNAVAILABLE",
                    "PROVIDER_TIMEOUT",
                }:
                    fallback_live_result = None
                    for fb_mode, fb_model in self._fallback_candidate_modes(request.providerMode):
                        try:
                            logger.info(
                                "Live primary %s failed with %s; attempting fallback to %s (%s)",
                                request.providerMode,
                                error.code,
                                fb_mode,
                                fb_model,
                            )
                            fb_provider = self.router.llm(fb_mode, fb_model)
                            async with asyncio.timeout(30.0):
                                if isinstance(fb_provider, GeminiLLMProvider | GroqLLMProvider | OpenAILLMProvider | AgentRouterOpenAIProvider | AgentRouterAnthropicProvider):
                                    fallback_live_result = await fb_provider.create_live_plan(
                                        request.text,
                                        request.companionId,
                                        request.language,
                                        history,
                                        emit_delta,
                                        prompt,
                                    )
                                else:
                                    fallback_live_result = await fb_provider.create_plan(
                                        request.text,
                                        request.companionId,
                                        request.language,
                                        history,
                                        prompt,
                                    )
                            logger.info("Live fallback to %s succeeded", fb_mode)
                            is_fallback = True
                            fallback_reason = f"Primary {request.providerMode} failed: {error.code}"
                            resolved_provider = fb_mode
                            resolved_model = fb_model
                            break
                        except Exception as fb_exc:
                            logger.warning("Live fallback provider %s failed: %r", fb_mode, fb_exc)
                    if fallback_live_result is not None:
                        result = fallback_live_result
                    else:
                        raise error
                else:
                    raise error

        _apply_response_quality_guard(result.value, is_live=True)
        result.value.requestedProvider = requested_provider
        result.value.requestedModel = requested_model
        result.value.resolvedProvider = resolved_provider
        result.value.resolvedModel = resolved_model
        result.value.fallback = is_fallback
        result.value.fallbackReason = fallback_reason
        result.value.latencyMs = result.latency_ms

        # Auto-persist learned memory candidates
        if getattr(result.value, "memoryCandidates", None):
            for candidate in result.value.memoryCandidates:
                try:
                    if self.memory_service and user_id:
                        self.memory_service.remember(
                            user_id=user_id,
                            content=candidate.content,
                            category=getattr(candidate, 'category', None) or "conversation",
                            source_turn_ref=f"auto:{request.conversationId or request.sessionId}",
                        )
                except Exception:
                    logger.debug("Failed to persist memory candidate: %s", candidate.content[:50], exc_info=True)

        self._inject_deterministic_tool_intents(
            request.text,
            result.value,
            session_id=request.sessionId,
            turn_request=request,
        )

        self.memory.append_turn(request.sessionId, request.text, result.value.model_dump_json())

        # Persist to durable storage
        try:
            if self.memory_service and user_id:
                self.memory_service.append_turn(
                    user_id=user_id,
                    companion_id=request.companionId or "hinaa",
                    conversation_id=request.conversationId or request.sessionId,
                    user_text=request.text,
                    assistant_text=result.value.model_dump_json(),
                    language=result.value.language or "mixed",
                    attachments=request.attachments or (
                        [{"asset_id": aid} for aid in request.attachment_ids] if request.attachment_ids else None
                    ),
                )
        except Exception:
            logger.warning("Failed to persist turn to database", exc_info=True)

        self._persist_learned_memories(user_id, request.sessionId)
        
        return result

    async def stream_turn(
        self, request: TurnRequest, correlation_id: str, *, user_id: str | None = None
    ) -> AsyncIterator[bytes]:
        import uuid
        start_time = time.time()
        yield self._event("thinking", {"correlationId": correlation_id})
        yield self._event("run.started", {
            "runId": correlation_id,
            "providerMode": request.providerMode,
            "brainModel": request.brainModel,
            "imageEngine": request.imageEngine,
            "voiceEngine": request.voiceEngine,
        })
        yield self._event("planning.started", {
            "step": 1,
            "description": "Analyzing context & synthesizing plan",
            "correlationId": correlation_id,
        })

        # True token-by-token streaming. Provider deltas are relayed onto the
        # wire the instant they are produced instead of waiting for the whole
        # plan, so the interface reveals text continuously like a live brain.
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def emit_delta(delta: str) -> None:
            await queue.put(delta)

        turn_task = asyncio.create_task(
            self.create_live_plan(request, emit_delta, user_id=user_id)
        )
        emitted: list[str] = []
        try:
            while True:
                getter = asyncio.create_task(queue.get())
                done, _ = await asyncio.wait(
                    {getter, turn_task}, return_when=asyncio.FIRST_COMPLETED
                )
                if getter in done:
                    item = getter.result()
                    if item is not None:
                        emitted.append(item)
                        yield self._event("text.delta", {"delta": item})
                    continue
                getter.cancel()
                # The turn finished; drain any deltas queued a beat earlier.
                while not queue.empty():
                    item = queue.get_nowait()
                    if isinstance(item, str):
                        emitted.append(item)
                        yield self._event("text.delta", {"delta": item})
                break
            result = await turn_task
            # Guarantee full display text even if a provider finished without
            # streaming (or emitted a different final polish than its deltas).
            full_text = result.value.displayText or ""
            streamed_so_far = "".join(emitted)
            if full_text.startswith(streamed_so_far) and len(full_text) > len(streamed_so_far):
                remainder = full_text[len(streamed_so_far):]
                yield self._event("text.delta", {"delta": remainder})
        finally:
            if not turn_task.done():
                turn_task.cancel()

        plan_elapsed_ms = int((time.time() - start_time) * 1000)
        yield self._event("planning.completed", {
            "step": 1,
            "durationMs": plan_elapsed_ms,
            "correlationId": correlation_id,
        })

        # Emit tool events for each tool request
        total_tools = len(result.value.toolRequests)
        for idx, tool_req in enumerate(result.value.toolRequests, 1):
            tool_run_id = str(uuid.uuid4())
            yield self._event("tool.started", {
                "toolRunId": tool_run_id,
                "toolName": tool_req.toolName,
                "step": idx,
                "totalSteps": total_tools,
                "parameters": tool_req.parameters,
                "correlationId": correlation_id,
            })
            yield self._event("tool.progress", {
                "toolRunId": tool_run_id,
                "toolName": tool_req.toolName,
                "message": f"Processing {tool_req.toolName}...",
            })
            yield self._event("tool.proposed", {
                "toolRunId": tool_run_id,
                "toolName": tool_req.toolName,
                "parameters": tool_req.parameters,
                "correlationId": correlation_id,
            })
            yield self._event("tool.completed", {
                "toolRunId": tool_run_id,
                "toolName": tool_req.toolName,
                "status": "ready",
            })

        plan_payload: dict[str, object] = {
            "plan": result.value.model_dump(),
            "provider": result.provider,
        }
        if self.settings.prompt_debug_metadata:
            plan_payload["promptVersion"] = PROMPT_VERSION
        yield self._event("plan", plan_payload)
        yield self._event("usage", {"latencyMs": result.latency_ms})
        yield self._event("run.completed", {
            "runId": correlation_id,
            "status": "completed",
            "latencyMs": result.latency_ms,
            "totalDurationMs": int((time.time() - start_time) * 1000),
        })

    async def synthesize(self, request: SpeechRequest) -> ProviderResult[bytes]:
        try:
            async with asyncio.timeout(self.settings.provider_timeout_seconds):
                provider = self.router.tts(request.providerMode, request.companionId)
                if isinstance(provider, DeepgramTTSProvider):
                    return await provider.synthesize(request.text, voice=self.settings.deepgram_tts_model_hiro)
                if isinstance(provider, ElevenLabsHTTPStreamingProvider):
                    voice_id = (
                        self.settings.elevenlabs_hiro_voice_id
                        if request.companionId == "hiro"
                        else self.settings.elevenlabs_hinaa_voice_id
                    )
                    return await provider.synthesize_full(request.text, voice=voice_id)
                voice = resolve_voice(
                    request.companionId,
                    self.settings.azure_speech_female_voice,
                    self.settings.azure_speech_male_voice,
                    request.language,
                )
                if isinstance(provider, FishAudioTTSProvider):
                    voice_id = self.settings.fish_audio_voice_ids[0 if request.companionId == "hinaa" else 1]
                    return await provider.synthesize(request.text, voice=voice_id, language_hint=request.language.split("-")[0] if request.language != "mixed" else "auto")
                return await provider.synthesize(request.text, voice)
        except TimeoutError as error:
            raise HinaaError(
                "PROVIDER_TIMEOUT", "Voice synthesis took too long.", 504, True
            ) from error

    async def synthesize_text(
        self,
        text: str,
        companion_id: CompanionId,
        mode: ProviderMode,
        calibration: str = "natural",
        rate: float | None = None,
        pitch_semitones: float | None = None,
        volume: float | None = None,
        delivery_mode: str = "warm",
        language: str = "mixed",
    ) -> ProviderResult[bytes]:
        provider = self.router.tts(mode, companion_id)
        if isinstance(provider, DeepgramTTSProvider):
            try:
                async with asyncio.timeout(self.settings.provider_timeout_seconds):
                    return await provider.synthesize(text, voice=self.settings.deepgram_tts_model_hiro)
            except Exception as deepgram_err:
                if self.settings.elevenlabs_configured:
                    logger.warning("Deepgram failed for Hiro, falling back to ElevenLabs: %s", deepgram_err)
                    provider = self.router.tts("cloud", companion_id) # ElevenLabs will be picked up if configured
                    if isinstance(provider, DeepgramTTSProvider): # If router still returned Deepgram, fallback manually
                        config = ElevenLabsConfig(
                            api_key=self.settings.elevenlabs_api_key.get_secret_value(),
                            base_url=self.settings.elevenlabs_base_url,
                            voice_id=self.settings.elevenlabs_hiro_voice_id,
                            model_id=self.settings.elevenlabs_model_id,
                            output_format=self.settings.elevenlabs_output_format,
                        )
                        provider = ElevenLabsHTTPStreamingProvider(config)
                else:
                    raise HinaaError("TTS_FAILED", f"Deepgram TTS failed and no fallback configured: {deepgram_err}", 503, True) from deepgram_err
        
        if isinstance(provider, FishAudioTTSProvider):
            # Language hint auto-detects Nepali (Devanagari) vs English per turn.
            voice_id = (
                self.settings.fish_audio_voice_ids[0]
                if companion_id == "hinaa"
                else self.settings.fish_audio_voice_ids[1]
            )
            if not voice_id:
                raise HinaaError("TTS_FAILED", "Fish Audio voice id is not configured.", 503, True)
            try:
                async with asyncio.timeout(self.settings.provider_timeout_seconds):
                    return await provider.synthesize(text, voice=voice_id, language_hint=language.split("-")[0] if language != "mixed" else "auto")
            except Exception as error:
                raise HinaaError("TTS_FAILED", f"Fish Audio TTS failed: {error}", 503, True) from error
        if isinstance(provider, ElevenLabsHTTPStreamingProvider):
            # Select per-companion voice ID
            if companion_id == "hiro":
                voice_id = self.settings.elevenlabs_hiro_voice_id
            else:
                voice_id = self.settings.elevenlabs_hinaa_voice_id
            try:
                async with asyncio.timeout(self.settings.provider_timeout_seconds):
                    return await provider.synthesize_full(
                        text,
                        voice=voice_id,
                        delivery_mode=delivery_mode,
                        companion_id=companion_id,
                    )
            except Exception as error:
                raise HinaaError("TTS_FAILED", f"ElevenLabs TTS failed: {error}", 503, True) from error
        if mode in {"mock", "local"}:
            return await self.synthesize(
                SpeechRequest(text=text, companionId=companion_id, providerMode=mode)
            )
        if not isinstance(provider, AzureSpeechProvider):
            raise HinaaError("TTS_FAILED", "Speech synthesis provider is unavailable.", 503, True)
        voice = resolve_voice(
            companion_id,
            self.settings.azure_speech_female_voice,
            self.settings.azure_speech_male_voice,
            language,
        )
        tuning = resolve_calibration(calibration)
        try:
            async with asyncio.timeout(self.settings.provider_timeout_seconds):
                return await provider.synthesize_calibrated(
                    text,
                    voice,
                    rate if rate is not None else tuning.rate,
                    pitch_semitones if pitch_semitones is not None else tuning.pitch_semitones,
                    volume if volume is not None else tuning.volume,
                )
        except TimeoutError as error:
            raise HinaaError(
                "PROVIDER_TIMEOUT", "Voice synthesis took too long.", 504, True
            ) from error


    def _log_prompt_meta(self, session_id: str, fingerprint: str, mode: str) -> None:
        logger.info(
            "prompt_assembled",
            extra={
                "session_id": session_id,
                "prompt_version": PROMPT_VERSION,
                "fingerprint": fingerprint,
                "interaction_mode": mode,
            },
        )

    @staticmethod
    def _event(event_type: str, payload: dict[str, object]) -> bytes:
        return (json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n").encode()
