from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING

from .config import Settings
from .errors import HinaaError
from .memory import SessionMemory
from .models import AssistantTurnPlan, CompanionId, ProviderMode, SpeechRequest, TurnRequest, ToolRequest

if TYPE_CHECKING:  # pragma: no cover
    from .persistence.memory_service import MemoryService

from .prompts import PROMPT_VERSION, neutral_fallback_plan
from .prompts.turn_prompt import build_turn_prompt
from .providers.agent_router import AgentRouterOpenAIProvider, AgentRouterAnthropicProvider
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
from .providers.openai_llm import OpenAILLMProvider
from .providers.deepgram_voice import DeepgramTTSProvider, DeepgramSTTProvider
from .voice_profiles import resolve_calibration, resolve_voice

logger = logging.getLogger("hinaa.conversation")


def _durable_content(block: str) -> str:
    """Strip the ``memory:{id}: `` prefix from an approved durable block."""
    if ": " in block:
        return block.split(": ", 1)[1].strip()
    return block.strip()


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


def _apply_response_quality_guard(plan: AssistantTurnPlan) -> None:
    """Normalize a completed plan without changing meaning or tool requests."""
    plan.displayText = _remove_repeated_passages(plan.displayText)
    plan.spokenText = _remove_repeated_passages(plan.spokenText)
    # Voice should complement a long display answer, not replay it verbatim.
    if (
        len(plan.displayText) > 160
        and _comparison_key(plan.displayText) == _comparison_key(plan.spokenText)
    ):
        plan.spokenText = "I’ve put the key details in chat, babe."


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
                try:
                    model = self.settings.resolve_gemini_model(
                        "gemini-3.1-flash-lite"
                    )
                except ValueError:
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

    def _inject_deterministic_tool_intents(self, text: str, plan: AssistantTurnPlan) -> None:
        """Add only unambiguous, imperative local tool requests.

        This deliberately does not behave like a keyword detector.  Explanations,
        negations, quoted examples, capability questions, and historical wording
        remain conversational text.  Ambiguous requests are left to the selected
        model rather than causing an unexpected side effect.
        """
        lower_text = text.casefold().strip()
        unquoted = re.sub(r"[\"'“”‘’][^\"'“”‘’]*[\"'“”‘’]", "", lower_text).strip()
        blocked_framing = (
            r"\b(do not|don't|dont|never|not|may|might|later|example|phrase|"
            r"explain|why did|how does|how to|can you|can hinaa|is it possible)\b"
        )
        if re.search(blocked_framing, lower_text):
            return

        def is_command(patterns: list[str], *, target: str) -> bool:
            if not re.search(target, unquoted, re.IGNORECASE):
                return False
            return any(re.search(pattern, unquoted, re.IGNORECASE) for pattern in patterns)

        image_search_command = is_command(
            [
                r"^\s*(please\s+)?(?:search|find|look\s+for)\s+(?:public\s+)?(?:images?|pictures?|photos?)\b",
                r"^\s*(?:images?|pictures?|photos?)\s+(?:search|find|lookup)\b",
                r"^\s*(?:तस्वीरें|चित्र)\s+(?:खोजो|ढूंढो)\b",
            ],
            target=r"\b(images?|pictures?|photos?)\b|तस्वीरें|चित्र",
        )
        if image_search_command and not any(t.toolName == "image_search" for t in plan.toolRequests):
            prompt_str = re.sub(
                r"(?i)^\s*(?:please\s+)?(?:search|find|look\s+for)\s+(?:public\s+)?(?:images?|pictures?|photos?)\s+(?:of|for|about)?\s*",
                "",
                text,
            ).strip()
            plan.toolRequests.append(ToolRequest(
                toolName="image_search",
                parameters={"query": prompt_str or text, "count": 6},
            ))

        image_command = is_command(
            [
                r"^\s*(please\s+)?(generate|create|make|draw|paint|render|बनाओ|बनाऊ|बनाइदेऊ)\b",
                r"^\s*(?:\d+|one|two|three|four|चार|एक|दुई|एउटा)?\s*(?:fast\s+|quality\s+)?(?:images?|pictures?|photos?|चित्र|तस्वीर)\s+(?:generate|create|make|करो|गर)\b",
                r"^\s*(?:generate|create|make|बनाओ|बनाऊ|बनाइदेऊ)\b.*(?:image|picture|photo|चित्र|तस्वीर)",
            ],
            target=r"\b(image|images|picture|pictures|photo|photos|portrait|artwork|variation|variations)\b|चित्र|तस्वीर",
        )
        if image_command and not any(t.toolName == "image_generate" for t in plan.toolRequests):
            prompt_str = re.sub(
                r"(?i)^\s*(?:please\s+)?(?:generate|create|make|draw|paint|render)\s+(?:an?\s+)?(?:image|picture|photo|portrait)\s+(?:of\s+)?",
                "",
                text,
            ).strip()
            plan.toolRequests.append(ToolRequest(
                toolName="image_generate",
                parameters={
                    "prompt": prompt_str if prompt_str else text,
                    "count": 1,
                    "mode": "fast",
                    "strategy": "variations",
                },
            ))

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
            [r"^\s*(please\s+)?(research|investigate|compare with sources|deep research)\b"],
            target=r"\b(web|internet|online|sources?|citations?|documentation|current)\b|वेब|स्रोत",
        )
        if deep_research_command and not any(t.toolName == "web_research" for t in plan.toolRequests):
            prompt_str = re.sub(
                r"(?i)^\s*(?:please\s+)?(?:research|investigate|compare with sources|deep research)\s*(?:the web for|online|with sources|:)?\s*",
                "",
                text,
            ).strip()
            plan.toolRequests.append(ToolRequest(
                toolName="web_research",
                parameters={"query": prompt_str or text, "effort": "lite"},
            ))

        search_command = is_command(
            [r"^\s*(please\s+)?(search the web for|look up|find information about|google search for|खोज|खोज्नुहोस्)\b"],
            target=r"\b(web|internet|online|google|documentation|sources?)\b|वेब|इन्टरनेट",
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

    async def create_plan(
        self, request: TurnRequest, *, user_id: str | None = None
    ) -> ProviderResult[AssistantTurnPlan]:
        history = self.memory.context(request.sessionId)
        approved = self._approved_blocks(user_id)
        session_memories = _dedupe_session_facts(
            self.memory.learned_memories(request.sessionId), approved
        )
        prompt = build_turn_prompt(
            request=request,
            history=history,
            settings=self.settings,
            interaction_mode="rest",
            session_memories=session_memories,
            approved_memory_blocks=approved,
        )
        self._log_prompt_meta(request.sessionId, prompt.fingerprint, "rest")
        try:
            async with asyncio.timeout(self.settings.llm_timeout_seconds):
                provider = self._fast_casual_provider(
                    request.providerMode, request.text, history
                )
                fast_provider_id = getattr(provider, "id", None)
                if provider is None:
                    provider = self.router.llm(
                        request.providerMode, request.brainModel
                    )
                try:
                    result = await provider.create_plan(
                        request.text,
                        request.companionId,
                        request.language,
                        history,
                        prompt,
                    )
                except HinaaError as error:
                    if fast_provider_id and error.code in {
                        "PROVIDER_KEY_INVALID",
                        "PROVIDER_UNAVAILABLE",
                        "PROVIDER_RATE_LIMIT",
                    }:
                        # The fast brain (e.g. a deactivated OpenAI key) must
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
                        result = await provider.create_plan(
                            request.text,
                            request.companionId,
                            request.language,
                            history,
                            prompt,
                        )
                    else:
                        raise
        except TimeoutError as error:
            raise HinaaError(
                "PROVIDER_TIMEOUT", "The response took too long.", 504, True
            ) from error
        except HinaaError as error:
            if error.code == "MODEL_RESPONSE_INVALID":
                plan = neutral_fallback_plan(
                    user_text=request.text,
                    companion_id=request.companionId,
                    language=request.language,
                    depth=prompt.response_depth,
                )
                result = ProviderResult(plan, f"fallback:{PROMPT_VERSION}", 0)
            else:
                raise
        _apply_response_quality_guard(result.value)
        self.memory.append_turn(request.sessionId, request.text, result.value.model_dump_json())
        self._persist_learned_memories(user_id, request.sessionId)
        
        self._inject_deterministic_tool_intents(request.text, result.value)
        
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
        prompt = build_turn_prompt(
            request=request,
            history=history,
            settings=self.settings,
            interaction_mode="realtime",
            session_memories=session_memories,
            approved_memory_blocks=approved,
        )
        timing.mark("prompt_built")
        self._log_prompt_meta(request.sessionId, prompt.fingerprint, "realtime")
        fast_provider_id: str | None = None
        try:
            async with asyncio.timeout(self.settings.llm_timeout_seconds):
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
        except Exception as error:
            # A failed fast brain must not be retried forever: negative-cache
            # its key so the next casual turn uses a working fast brain (or the
            # reasoning brain) instead of burning another failed attempt.
            if fast_provider_id and isinstance(error, HinaaError) and error.code in {
                "PROVIDER_KEY_INVALID",
                "PROVIDER_UNAVAILABLE",
                "PROVIDER_RATE_LIMIT",
            }:
                self._mark_fast_key_bad(fast_provider_id)
            logger.warning("Primary provider %r failed or timed out (%s); engaging fast fallback", request.providerMode, error)
            try:
                # Attempt fast fallback to Gemini or OpenAI if configured, but
                # never straight back to the fast provider that just failed.
                fallback_provider_id = (
                    "gemini"
                    if self.settings.gemini_configured and fast_provider_id != "gemini"
                    else "openai"
                    if self.settings.openai_configured and fast_provider_id != "openai"
                    else "mock"
                )
                fallback_provider = self.router.llm(fallback_provider_id, None)
                if isinstance(fallback_provider, GeminiLLMProvider | OpenAILLMProvider):
                    async with asyncio.timeout(self.settings.llm_timeout_seconds):
                        result = await fallback_provider.create_live_plan(
                            request.text,
                            request.companionId,
                            request.language,
                            history,
                            emit_delta,
                            prompt,
                        )
                else:
                    raise error
            except Exception:
                plan = neutral_fallback_plan(
                    user_text=request.text,
                    companion_id=request.companionId,
                    language=request.language,
                    depth=prompt.response_depth,
                )
                await emit_delta(plan.displayText)
                result = ProviderResult(plan, f"fallback:{PROMPT_VERSION}", 0)

        _apply_response_quality_guard(result.value)
        self.memory.append_turn(request.sessionId, request.text, result.value.model_dump_json())
        self._persist_learned_memories(user_id, request.sessionId)
        
        self._inject_deterministic_tool_intents(request.text, result.value)
        
        return result

    async def stream_turn(
        self, request: TurnRequest, correlation_id: str, *, user_id: str | None = None
    ) -> AsyncIterator[bytes]:
        yield self._event("thinking", {"correlationId": correlation_id})
        result = await self.create_plan(request, user_id=user_id)
        words = result.value.displayText.split(" ")
        for index, word in enumerate(words):
            delta = word if index == len(words) - 1 else f"{word} "
            yield self._event("text.delta", {"delta": delta})
            if request.providerMode == "mock":
                await asyncio.sleep(0.012)
        plan_payload: dict[str, object] = {
            "plan": result.value.model_dump(),
            "provider": result.provider,
        }
        if self.settings.prompt_debug_metadata:
            plan_payload["promptVersion"] = PROMPT_VERSION
        yield self._event("plan", plan_payload)
        yield self._event("usage", {"latencyMs": result.latency_ms})

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
                voice = (
                    self.settings.azure_speech_female_voice
                    if request.companionId == "hinaa"
                    else self.settings.azure_speech_male_voice
                )
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
    ) -> ProviderResult[bytes]:
        provider = self.router.tts(mode, companion_id)
        if isinstance(provider, DeepgramTTSProvider):
            try:
                async with asyncio.timeout(self.settings.provider_timeout_seconds):
                    return await provider.synthesize(text, voice=self.settings.deepgram_tts_model_hiro)
            except Exception as deepgram_err:
                if self.settings.elevenlabs_configured:
                    print(f"Deepgram failed for Hiro, falling back to ElevenLabs: {deepgram_err}")
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
