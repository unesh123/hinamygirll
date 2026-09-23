from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from .config import Settings
from .circuit_breaker import peek_circuit_breaker
from .brain_ledger import fingerprint_for, record_call, row_for_brain
from .errors import HinaaError
from .reachability import probe_gateway_models
from .memory import SessionMemory
from .models import AssistantTurnPlan, CompanionId, ProviderMode, SpeechRequest, TurnRequest, ToolRequest, Emotion

if TYPE_CHECKING:  # pragma: no cover
    from .persistence.memory_service import MemoryService

from .prompts import PROMPT_VERSION, build_plan_from_text, neutral_fallback_plan
from .prompts.performance import extract_executive_voice_summary
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

# Below this many characters the primary had not really started answering, so a
# fallback brain may still take the turn; above it the text is already on the
# user's screen and replacing it would attribute words to her she never wrote.
_MIN_STREAMED_CHARS_TO_KEEP = 400

# A dead primary brain should hand the turn to a working one, not surface an
# error. This list must track the codes providers actually raise: the per-path
# copies of it used to name PROVIDER_RATE_LIMIT / PROVIDER_KEY_INVALID (which
# nothing emits) while missing PROVIDER_UNREACHABLE and PROVIDER_RATE_LIMITED
# (which the agent-router gateway emits on every connection reset and 429), so
# the documented recovery never ran.
# SAFETY_REFUSAL and *_RESPONSE_INVALID stay out on purpose: refusal is final,
# and a malformed answer has its own neutral-plan path.
FALLBACK_ELIGIBLE_ERROR_CODES = frozenset(
    {
        "PROVIDER_UNREACHABLE",
        "PROVIDER_UNAVAILABLE",
        "PROVIDER_TIMEOUT",
        "PROVIDER_RATE_LIMIT",
        "PROVIDER_RATE_LIMITED",
        "PROVIDER_KEY_INVALID",
        "PROVIDER_AUTH_FAILED",
        "PROVIDER_ACCESS_DENIED",
        "PROVIDER_ENDPOINT_INVALID",
        "PROVIDER_MODEL_NOT_FOUND",
        "PROVIDER_ACCOUNT_CAPACITY_UNAVAILABLE",
    }
)


@asynccontextmanager
async def live_generation_window(
    *,
    ceiling_s: float,
    idle_s: float,
    forward: Callable[[str], Awaitable[None]],
    sink: list[str] | None = None,
) -> AsyncIterator[tuple[Callable[[str], Awaitable[None]], Callable[[], bool]]]:
    """Emit hook + liveness predicate for one live brain attempt.

    The idle deadline moves forward on every token, so a long answer is never
    killed merely for being long; only a silent stream is. ``ceiling_s`` remains
    as the absolute backstop against a hung connection.
    """
    loop = asyncio.get_running_loop()
    async with asyncio.timeout(ceiling_s), asyncio.timeout(idle_s) as idle_window:

        async def emit(delta: str) -> None:
            if sink is not None:
                sink.append(delta)
            idle_window.reschedule(loop.time() + idle_s)
            await forward(delta)

        yield emit, idle_window.expired


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


def _dedupe_halves(text: str) -> str:
    """If the model repeated its entire answer block verbatim or near-verbatim, collapse it."""
    s = text.strip()
    n = len(s)
    if n < 40:
        return text
    mid = n // 2
    for offset in range(-15, 16):
        m = mid + offset
        if m < 20 or m > n - 20:
            continue
        first = s[:m].strip()
        second = s[m:].strip()
        if first and second:
            if first == second:
                return first
            k1 = _comparison_key(first)
            k2 = _comparison_key(second)
            if k1 and k2 and len(k1) >= 25 and k1 == k2:
                return first
    return text


def _remove_repeated_passages(text: str) -> str:
    """Keep the first copy of an identical paragraph, sentence, or text block.

    Provider output can occasionally repeat its answer during schema recovery or
    streaming completion. This guard is intentionally conservative: it removes
    only identical normalized passages and leaves differently worded details,
    Markdown lists, and code intact.
    """
    text = _dedupe_halves(text)
    chunks = re.split(r"(\n{2,}|(?<=[.!?।])\s+)", text.strip())
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


def _plain_first_sentences(text: str, limit: int = 280) -> str:
    """First one or two substantive prose sentences of a document, skipping
    conversational greetings and stripping markdown so voice summaries are natural."""
    return extract_executive_voice_summary(text, limit=limit)


def _speech_safe(text: str) -> str:
    """Strip inline markdown from the spoken channel. The document keeps its
    formatting; a voice engine reads a backtick as a hiccup and says 'asterisk'
    out loud. Measured live: she spoke `tier-a-conversation-brain-1.0.0` with
    the backticks in it because the guard only looks for triple backticks.

    Deliberately narrow: emphasis markers only count when they hug a word on
    both sides, so "2 * 3 * 4" and snake_case identifiers survive untouched.
    """
    if not text:
        return text
    safe = re.sub(r"\[([^\]\n]+)\]\([^)\n]*\)", r"\1", text)
    safe = re.sub(r"`{1,3}([^`\n]*)`{1,3}", r"\1", safe)
    safe = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", safe)
    safe = re.sub(r"(?<!\*)\*(?=[^\s*])([^*\n]*?[^\s*])\*(?!\*)", r"\1", safe)
    safe = re.sub(r"(?<![\w_])_(?=[^\s_])([^_\n]*?[^\s_])_(?![\w_])", r"\1", safe)
    safe = re.sub(r"^\s{0,3}#{1,6}\s+", "", safe, flags=re.MULTILINE)
    return re.sub(r"\s{2,}", " ", safe).strip()


def _closing_ask(display: str) -> str:
    """The last real question in a document — normally her offer to build the
    full report or deep-dive next.

    A long answer is spoken from its *first* sentences, so whatever sits at the
    end is structurally never said. Measured on production: an 8,248-character
    status answer asked "Would you like the full documented report?" on screen
    while her voice ended on a mid-document bullet about colour palettes.
    """
    if not display:
        return ""
    # Split on line breaks as well as terminators: a heading such as
    # "### Exploration Paths" carries no full stop, so terminator-only splitting
    # glued it onto the bullet underneath and dragged the literal "\n* " into
    # what she then read aloud.
    sentences = [
        re.sub(r"\s+", " ", piece.lstrip("-*•\u2192>\u00a0 ").strip())
        for piece in re.split(r"\n+|(?<=[.!?।])\s+", _speech_safe(display))
    ]
    questions = [s for s in sentences if s.endswith("?") and len(s) >= 25]
    if not questions:
        return ""
    # He asked to be offered the documented report out loud. When she writes
    # several questions, the last one can be a tangent ("...or shall we tune
    # your PyTorch loop?") while the report offer sits above it — so prefer the
    # last offer that actually names the report, and fall back to the last ask.
    for sentence in reversed(questions):
        if re.search(r"\b(report|document|write-up|writeup|brief)\b", sentence, re.I):
            return sentence
    return questions[-1]


def _with_closing_ask(text: str, display: str, limit: int) -> str:
    """Append her closing ask to a spoken summary without busting the budget."""
    ask = _closing_ask(display)
    if not ask or ask.rstrip("?").strip() in text:
        return text
    room = limit - len(ask) - 1
    if room < 200:
        return text
    body = text.strip() if len(text) <= room else (_plain_first_sentences(text, limit=room) or text[:room])
    body = body.strip()
    if body and not re.search(r"[.!?:\u0964\u0965💜✨🌟🌸💖]\s*$", body):
        body += "."
    return f"{body} {ask}" if body else ask


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
    # Strip only actual stage directions in single asterisks, e.g. *laughs*, *smiles gently*, *sighs*, *मुस्कुराते हुए*
    # NEVER strip double asterisks (**bold**), which are standard markdown formatting!
    stage_dir_pattern = (
        r"(?<!\*)\*\s*(?:laughs?|chuckles?|giggles?|smiles?|smiling|sighs?|winks?|blushes?|nodding|nods|"
        r"softly|gently|warmly|cheerful|playful|curious|pouts?|gazing|looking|thinking|"
        r"मुस्कुराते\s+हुए|हंसते\s+हुए|धीमे\s+से\s+मुस्कुराते\s+हुए|गले\s+लगाते\s+हुए)[^*]*\*(?!\*)"
    )
    cleaned = re.sub(stage_dir_pattern, "", cleaned, flags=re.IGNORECASE)
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
    # Strip <svg>...</svg> blocks and standalone svg lines
    cleaned = re.sub(r"<svg[\s\S]*?</svg>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?im)^\s*svg\s*$\n?", "", cleaned)
    # Strip internal workflow tokens
    cleaned = re.sub(r"\b(?:workflow_mode|generation_set_id)\b\s*", "", cleaned)
    # Normalize leftover whitespace
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned)
    return cleaned.strip(), had_laughter


def _truncate_at_clause_boundary(text: str, limit: int) -> str:
    """Shorten text to ≤ ``limit`` chars WITHOUT cutting mid-thought (§32).

    Preference order: keep as-is → last sentence end → last clause break
    (comma/semicolon/dash/colon) → last word boundary. Never slices into
    the middle of a word.
    """
    if len(text) <= limit:
        return text
    window = text[: limit + 1]
    # Sentence boundary: cut AFTER the terminator so the thought keeps its
    # punctuation (never ends on a bare word).
    matches = list(re.finditer(r"[.!?\u0964\u0965]", window))
    if matches:
        cut = window[: matches[-1].end()].strip()
        if len(cut) >= limit * 0.4:
            return cut
    for sep in (",", ";", "—", " -", ":"):
        idx = window.rfind(sep)
        if idx >= limit * 0.4:
            return window[:idx].rstrip(" ,;—")
    cut = window.rsplit(" ", 1)[0].rstrip(" ,;—")
    return cut


class VoiceResponseType(str, Enum):
    """Semantic voice response types (directive §32).

    SHORT_FULL — the whole answer is short; voice may speak it verbatim.
    EXECUTIVE_SUMMARY — display is a long document; voice summarizes.
    PROGRESS_UPDATE — work still running; voice reports status only.
    QUESTION — Hina is asking the user something.
    ERROR — failure path; voice explains safely.
    COMPLETION — a tool finished (artifact produced); voice announces it.
    """

    SHORT_FULL = "SHORT_FULL"
    EXECUTIVE_SUMMARY = "EXECUTIVE_SUMMARY"
    PROGRESS_UPDATE = "PROGRESS_UPDATE"
    QUESTION = "QUESTION"
    ERROR = "ERROR"
    COMPLETION = "COMPLETION"
    ARTIFACT_READY = "ARTIFACT_READY"


def plan_voice_response(
    display_text: str,
    spoken_text: str,
    *,
    has_artifact: bool = False,
    has_pdf: bool = False,
    has_image: bool = False,
    has_error: bool = False,
    is_progress: bool = False,
    artifact_title: str | None = None,
    live: bool = False,
) -> tuple[VoiceResponseType, str]:
    """Classify the turn and produce the voice text for that type.

    Long documents never get a recitation; short conversational answers
    keep their full voice text; the summary is built from whole sentences
    and never cut mid-thought.

    `live` widens every budget. In the chat window a short spoken line
    complements a long display answer the user can scroll through; in a
    hands-free call it is the only surface, so the chat clamps truncated her
    to two sentences mid-thought.
    """
    display = (display_text or "").strip()
    spoken = (spoken_text or "").strip()

    if has_error:
        # Error voice: keep the spoken line if it's already short and
        # complete; otherwise a safe generic fallback. Never recite stacks.
        if spoken and len(spoken) <= 220 and re.search(r"[.!?\u0964]", spoken):
            return VoiceResponseType.ERROR, spoken
        return VoiceResponseType.ERROR, "Something went wrong on my side — give me another try? 💜"
    if has_artifact:
        title = artifact_title or "your document"
        return VoiceResponseType.ARTIFACT_READY, f"I've created {title} for you! You can view and edit it right here. ✨"
    if has_pdf:
        return VoiceResponseType.COMPLETION, "I've generated your assignment PDF! You can download it right below. ✨"
    if has_image:
        return VoiceResponseType.COMPLETION, "Here are some pictures for you! ✨"
    if is_progress:
        if spoken and len(spoken) <= 200:
            return VoiceResponseType.PROGRESS_UPDATE, spoken
        return VoiceResponseType.PROGRESS_UPDATE, "Working on it — I'll have it ready shortly! ✨"

    # Two tiers, one reason: a call has no second surface, so her voice has to
    # carry the whole answer. ~900 characters is about a minute of fluent
    # speech, and ~1.4k is about 90s. Note which tier production actually uses:
    # main.py has one entry into the brain (stream_turn) and stream_turn always
    # calls create_live_plan, so typed web turns arrive live too — the non-live
    # tier shapes only the non-streaming path that no route reaches today. Tighten
    # it and nothing changes on his phone.
    whole_answer_ceiling = 1_400 if live else 900
    verbatim_cap = 1_400 if live else 900
    distill_limit = 1_400 if live else 900
    summary_limit = 1_200 if live else 900

    # Question: Hina asked the user something — never overwrite a question
    # with a summary, that would erase the ask. Only while the question really
    # is the whole answer. A 5,056-word report that happens to close with
    # "Shall we examine the concurrency primitives?" is an executive summary
    # with an offer on the end, and this branch used to flatten it to 380
    # characters: measured on production as 398 spoken characters for what he
    # asked to hear in full.
    if len(display) <= whole_answer_ceiling and (
        spoken.endswith("?") or (not spoken and display.rstrip().endswith("?"))
    ):
        question = spoken or display
        if any(marker in question for marker in ("```", "\n", "•", "|", "###", "##", "- ")):
            # Falling back to the display text can pull in headings and bullets
            # that must never be read aloud.
            question = _plain_first_sentences(question, limit=400) or question.replace("\n", " ")
        if len(question) <= 400:
            return VoiceResponseType.QUESTION, question
        return VoiceResponseType.QUESTION, _truncate_at_clause_boundary(question, 380)

    if len(display) <= whole_answer_ceiling:
        # Short conversational turn: keep the model's own voice text when it
        # is a complete thought; otherwise speak the display text itself.
        candidate = spoken or display
        if len(candidate) <= verbatim_cap and bool(re.search(r"[.!?:\u0964\u0965💜✨🌟🌸💖]\s*$", candidate.rstrip())):
            return VoiceResponseType.SHORT_FULL, candidate
        if len(display) <= verbatim_cap:
            return VoiceResponseType.SHORT_FULL, display
        distilled = _plain_first_sentences(display, limit=distill_limit)
        return VoiceResponseType.SHORT_FULL, distilled or "I've put the full breakdown in chat! ✨"

    # Long document: executive summary from whole substantive sentences.
    clean_spoken = spoken.strip()
    sentence_ends = len(re.findall(r"[.!?\u0964\u0965]", clean_spoken))
    # Distinct sentences, not terminators: padding one sentence out twenty
    # times satisfies a terminator count while saying nothing new.
    distinct_sentences = len(
        {
            piece.strip().casefold()
            for piece in re.split(r"(?<=[.!?।])\s+", clean_spoken)
            if piece.strip()
        }
    )
    # Below these floors the model handed over a lead-in ("Great question,
    # babe, let me be honest with you…") rather than a summary, and distilling
    # from displayText says more. Live needs half its budget because her voice
    # is the only surface. Chat keeps a near-zero floor: a real three-sentence
    # summary measured 187 characters, so any character gate high enough to
    # catch a warm-up also destroys genuine summaries — the sentence rules
    # below are what separate the two.
    #
    # That only holds for ordinary turns. For a report-length document the
    # prompt asks for 600-1,400 characters of summary, and measured on
    # production she returned 398 for a 5,056-word report: chat's 40-character
    # floor waved it through and her voice covered 20s of a 40-minute read.
    report_length_doc = len(display) > 12_000
    chat_min_substantive_chars = 600 if report_length_doc else 40
    min_substantive_chars = (
        int(summary_limit * 0.5) if live else chat_min_substantive_chars
    )
    min_substantive_sentences = 3 if live else 2
    # Announcing that she is about to read the document is not a summary of it.
    recitation_openers = (
        "here is your",
        "i have generated",
        "i will now read",
        "i'll now read",
        "let me read",
    )
    substantive_ceiling = 2_400 if live else 1_500
    is_substantive_spoken = (
        len(clean_spoken) >= min_substantive_chars
        and distinct_sentences >= min_substantive_sentences
        and sentence_ends >= min_substantive_sentences
        and len(clean_spoken) <= substantive_ceiling
        and bool(re.search(r"[.!?:\u0964\u0965💜✨🌟🌸💖]\s*$", clean_spoken))
        and not any(marker in clean_spoken for marker in ("```", "\n", "•", "|", "###", "##"))
        and not clean_spoken.lower().startswith(recitation_openers)
    )
    if is_substantive_spoken:
        return VoiceResponseType.EXECUTIVE_SUMMARY, _with_closing_ask(
            clean_spoken, display, substantive_ceiling
        )

    summary = _plain_first_sentences(display, limit=summary_limit)
    if not summary:
        summary = _truncate_at_clause_boundary(spoken or display, summary_limit)
    if summary and not re.search(r"[.!?:\u0964\u0965]\s*$", summary.rstrip()):
        # Truncating here only made her shorter and still left the sentence
        # open, so the sign-off ran straight into it when spoken aloud.
        summary = summary.rstrip() + "."
    # Ask what she actually wrote at the end of the document; the canned line is
    # only for when there was no question to keep.
    sign_off = _closing_ask(display) or (
        "Want me to walk you through the whole thing?"
        if live
        else "The full document is in chat for you! ✨"
    )
    return VoiceResponseType.EXECUTIVE_SUMMARY, _with_closing_ask(
        f"{summary} {sign_off}".strip(), display, summary_limit
    )


_DOCUMENT_TOOL_NAMES = {"pdf_generate", "document_generate"}

# The builder typesets supplied text or cited findings and adds no analysis
# tables, figures, or bibliography of its own. A toolRequest is only a request
# at this point — nothing exists yet — so a reply listing what the document
# "contains" is describing a file nobody has written.
_UNVERIFIED_DOCUMENT_CLAIM = re.compile(
    r"(?i)[,;]?\s+\b(?:with|including|featuring|complete with|packed with)\b"
    r"(?P<list>[^.;:\n]{0,120}?\b(?:analyses?|analysis|citations?|references?|tables?|"
    r"graphs?|figures?|illustrations?|bibliography|footnotes?|scholarly sources)\b"
    r"[^.;:\n]{0,60})"
)


def _strip_unverified_document_claims(text: str) -> tuple[str, bool]:
    """Drop clauses asserting contents a document builder cannot have produced."""
    stripped_count = 0

    def _drop(match: re.Match[str]) -> str:
        nonlocal stripped_count
        stripped_count += 1
        return ""

    cleaned = _UNVERIFIED_DOCUMENT_CLAIM.sub(_drop, text)
    if not stripped_count:
        return text, False
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"(\w)\s+\1", r"\1", cleaned)
    return cleaned.strip(), True


def _apply_response_quality_guard(
    plan: AssistantTurnPlan,
    is_live: bool = False,
    evidence_sources: Any = None,
) -> None:
    """Normalize a completed plan without changing meaning or tool requests."""
    clean_display, display_laughed = _clean_natural_speech_and_display(plan.displayText)
    clean_spoken, spoken_laughed = _clean_natural_speech_and_display(plan.spokenText)
    # Speech only — the document keeps its markdown, her voice must not read it.
    clean_spoken = _speech_safe(clean_spoken)

    plan.displayText = _remove_repeated_passages(clean_display)
    plan.spokenText = _remove_repeated_passages(clean_spoken)

    if evidence_sources:
        try:
            from hinaa_api.grounding.citations import CitationRenderer
            renderer = CitationRenderer(evidence_sources)
            rendered_display, _, _ = renderer.render(plan.displayText, append_sources=True)
            plan.displayText = rendered_display
        except Exception:
            logger.debug("Citation rendering in quality guard skipped", exc_info=True)

    if any(t.toolName in _DOCUMENT_TOOL_NAMES for t in plan.toolRequests):
        plan.displayText, _ = _strip_unverified_document_claims(plan.displayText)
        plan.spokenText, _ = _strip_unverified_document_claims(plan.spokenText)

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
    has_pdf = any(t.toolName == "pdf_generate" for t in plan.toolRequests)
    has_image = any(t.toolName in {"image_search", "image_generate"} for t in plan.toolRequests)

    if has_pdf:
        # COMPLETION voice type: artifact announcement, not a recitation (§32).
        voice_type, voice_text = plan_voice_response(
            plan.displayText, raw_spoken := plan.spokenText, has_pdf=True
        )
        plan.spokenText = voice_text
        return
    elif has_image:
        voice_type, voice_text = plan_voice_response(
            plan.displayText, plan.spokenText, has_image=True
        )
        plan.spokenText = voice_text
        return

    raw_spoken = plan.spokenText or ""
    if is_live:
        # A paragraph break is prose, not structure. Discarding spoken text
        # just because it contained "\n" threw away everything the model
        # wrote to be said aloud; flatten it and keep the real hazards fatal.
        raw_spoken = " ".join(part.strip() for part in raw_spoken.split("\n") if part.strip())
        plan.spokenText = raw_spoken
    # Check if spoken text contains structured markdown, code, or outlines that should never be spoken aloud
    has_forbidden_speech_structure = any(
        marker in raw_spoken for marker in ("```", "\n", "•", "|", "- ", "1. ", "###", "##")
    )
    is_verbatim_echo = len(plan.displayText) > 280 and (
        _comparison_key(plan.displayText) == _comparison_key(raw_spoken)
    )

    if has_forbidden_speech_structure or is_verbatim_echo:
        voice_type, voice_text = plan_voice_response(
            plan.displayText, "", is_progress=False, live=is_live
        )
        plan.spokenText = voice_text
    elif len(plan.spokenText) > (3_000 if is_live else 1_500):
        voice_type, voice_text = plan_voice_response(
            plan.displayText, plan.spokenText, is_progress=False, live=is_live
        )
        plan.spokenText = voice_text
    elif len(plan.displayText) > (1_400 if is_live else 900):
        # Document guard (EXECUTIVE_SUMMARY): when displayText is a long
        # document/report, voice provides a smart, substantive executive summary.
        voice_type, voice_text = plan_voice_response(
            plan.displayText, plan.spokenText, is_progress=False, live=is_live
        )
        plan.spokenText = voice_text


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

    def _require_codecraft_brain(self) -> None:
        if self.settings.active_codecraft_key is None or self.settings.active_codecraft_base_url is None:
            raise HinaaError(
                "PROVIDER_CONFIGURATION_MISSING",
                "CodeCraft is not configured. Add CODECRAFT_API_KEY to apps/api/.env.local.",
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
        if mode == "codecraft":
            self._require_codecraft_brain()
            active_codecraft_key = self.settings.active_codecraft_key
            active_codecraft_base_url = self.settings.active_codecraft_base_url
            assert active_codecraft_key and active_codecraft_base_url
            try:
                model = self.settings.resolve_codecraft_model(brain_model)
            except ValueError:
                model = self.settings.active_codecraft_model
            return OpenAILLMProvider(
                active_codecraft_key.get_secret_value(),
                model,
                base_url=active_codecraft_base_url,
                provider_id="codecraft",
            )
        if mode == "ollama":
            base_url = self.settings.active_ollama_base_url or "http://localhost:11434/v1"
            model = self.settings.resolve_ollama_model(brain_model)
            return OpenAILLMProvider(
                key="ollama",
                model=model,
                base_url=base_url,
                provider_id="ollama",
            )
        if mode == "omniroute":
            if not self.settings.omniroute_configured:
                raise HinaaError(
                    "PROVIDER_CONFIGURATION_MISSING",
                    "OmniRoute is not enabled. Set HINAA_OMNIROUTE_ENABLED=true and start the "
                    f"local gateway on {self.settings.omniroute_base_url}.",
                    503,
                    user_action_required=True,
                )
            # The gateway stores its own upstream keys and needs no bearer token
            # for loopback access, so an empty key is the expected local case.
            return OpenAILLMProvider(
                key=self.settings.active_omniroute_key,
                model=self.settings.omniroute_model,
                base_url=self.settings.active_omniroute_base_url,
                provider_id="omniroute",
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
        task_service: Any = None,
        session_factory: Any = None,
        **kwargs: Any,
    ) -> None:
        self.settings = settings
        self.router = ProviderRouter(settings)
        self.memory = SessionMemory(settings.session_limit, settings.session_turn_limit)
        self.memory_service = memory_service
        self.task_service = task_service
        self.dialogue_state_service = kwargs.get("dialogue_state_service") or (getattr(memory_service, "dialogue_state_service", None) if memory_service else None)
        if self.dialogue_state_service is None and session_factory is not None:
            from hinaa_api.dialogue_state import DialogueStateService
            self.dialogue_state_service = DialogueStateService(session_factory)

        if session_factory is not None:
            from hinaa_api.continuity import (
                ConversationBootstrapper,
                ConversationFinalizer,
                CrossSessionMemoryRetriever,
                MemoryPromotionService,
            )
            self.cross_session_retriever = CrossSessionMemoryRetriever(session_factory)
            self.promotion_service = MemoryPromotionService(session_factory)
            self.bootstrapper = ConversationBootstrapper(session_factory)
            self.finalizer = ConversationFinalizer(session_factory)
        else:
            self.cross_session_retriever = None
            self.promotion_service = None
            self.bootstrapper = None
            self.finalizer = None
        # (user_id, session_id) -> set[str] of facts already pushed to the
        # durable store, so per-turn appends never rewrite the same facts.
        # OrderedDict + cap so long-running servers cannot leak memory here
        # even though SessionMemory evicts its own sessions.
        self._persisted_facts: OrderedDict[tuple[str, str], set[str]] = OrderedDict()
        # Fast-brain key health cache: provider_id -> monotonic time until which
        # the key is treated as bad. Prevents hammering a deactivated/expired
        # key (401) on every casual turn when a working brain is available.
        self._fast_key_bad_until: dict[str, float] = {}
        # Phase B2 — hierarchical context compiler: routing + manifest ledger.
        # One canonical compiler instance; manifests are per-request artifacts.
        from .agent.compiler import ContextCompiler
        self.context_compiler = ContextCompiler(
            max_tokens=getattr(settings, "session_history_char_limit", 32_000) // 4,
            model_context_limit=getattr(settings, "llm_context_limit", 131_072),
        )
        # Ring buffer of recent manifests for the developer inspector (§37).
        from collections import deque
        self._context_manifests: deque[dict[str, Any]] = deque(maxlen=50)
        # B2 summary tree (§17) — persistent episode summaries. Optional:
        # in-memory sessions (tests) run without a DB-backed episode tree.
        self.episode_summarizer = None
        if session_factory is not None:
            try:
                from .persistence.episode_service import EpisodeSummarizer
                self.episode_summarizer = EpisodeSummarizer(session_factory)
            except Exception:
                logger.debug("EpisodeSummarizer unavailable (no DB)", exc_info=True)
        self._episode_turn_counters: dict[str, int] = {}

    def _fast_key_bad(self, provider_id: str) -> bool:
        return self._fast_key_bad_until.get(provider_id, 0.0) > time.monotonic()

    def _mark_fast_key_bad(self, provider_id: str) -> None:
        # 10-minute negative cache: a dead key is retried only after the window
        # lapses (in case the user fixes their account mid-session).
        self._fast_key_bad_until[provider_id] = time.monotonic() + 600

    def _record_brain_call(
        self,
        brain_id: str | None,
        *,
        ok: bool,
        error: Exception | None = None,
        model: str = "",
    ) -> None:
        """Note what a real attempt proved, for the health badges.

        Every provider class answers for itself: some hold a circuit breaker,
        others raise straight through. Recording at the turn layer is the one
        place that sees the outcome of every brain, so the badge can never be
        greener than the call that actually happened.
        """
        if not brain_id:
            return
        try:
            code = str(getattr(error, "code", "") or "")
            detail = str(getattr(error, "message", "") or error or "")[:300]
            row_id = row_for_brain(brain_id)
            record_call(
                brain_id,
                ok=ok,
                code=code,
                detail=detail,
                model=model,
                fingerprint=fingerprint_for(self.settings, row_id),
            )
        except Exception:  # a badge is never worth failing a turn over
            logger.debug("Brain ledger write refused", exc_info=True)

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

    def _handle_continuity_promotions(self, user_id: str, convo_id: str | None, text: str) -> None:
        """Promote approved assets and project architecture facts to cross-session continuity."""
        # 1. Approved face/character reference (e.g. "My approved Hina face is IMG_24")
        face_match = re.search(
            r"approved\s+(?:([A-Za-z0-9_]+)\s+)?face\s+(?:is\s+|:\s*)?([A-Za-z0-9_]+)",
            text,
            re.IGNORECASE,
        ) or re.search(
            r"\b([A-Za-z0-9_]+)\s+is\s+(?:my\s+)?approved\s+(?:([A-Za-z0-9_]+)\s+)?face",
            text,
            re.IGNORECASE,
        )
        if face_match and self.promotion_service:
            entity = face_match.group(1) or "Hina"
            asset_id = face_match.group(2)
            try:
                self.promotion_service.promote_approved_asset(
                    user_id,
                    entity_name=entity.title(),
                    asset_id=asset_id,
                    conversation_id=convo_id,
                )
            except Exception:
                logger.debug("Failed to promote approved face %s", asset_id, exc_info=True)

        # 2. Project architecture / database facts (e.g. "Nova project uses PostgreSQL.")
        proj_match = re.search(
            r"\b([A-Za-z0-9_]+)\s+project\s+uses\s+([A-Za-z0-9_]+)",
            text,
            re.IGNORECASE,
        ) or re.search(
            r"\b([A-Za-z0-9_]+)\s+(?:stack|architecture|database|db)\s+(?:is|uses)\s+([A-Za-z0-9_]+)",
            text,
            re.IGNORECASE,
        )
        if proj_match:
            p_name = proj_match.group(1)
            try:
                if self.memory_service:
                    self.memory_service.remember(
                        user_id=user_id,
                        content=text.strip(),
                        category="project",
                        source_turn_ref=f"convo:{convo_id}" if convo_id else None,
                        explicit=True,
                    )
                if self.cross_session_retriever:
                    with self.cross_session_retriever._factory() as session:
                        from hinaa_api.persistence.orm import UserContinuityState
                        from sqlalchemy import select
                        import json
                        st = session.scalar(select(UserContinuityState).where(UserContinuityState.owner_id == user_id))
                        if not st:
                            st = UserContinuityState(owner_id=user_id)
                            session.add(st)
                            session.flush()
                        projs = []
                        try:
                            projs = json.loads(st.important_projects_json) if st.important_projects_json else []
                        except Exception:
                            pass
                        if p_name not in projs:
                            projs.append(p_name)
                            st.important_projects_json = json.dumps(projs)
                            session.commit()
            except Exception:
                logger.debug("Failed to record project fact", exc_info=True)

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
        user_id: str | None = None,
    ) -> None:
        """Add only unambiguous, imperative local tool requests.

        This deliberately does not behave like a keyword detector.  Explanations,
        negations, quoted examples, capability questions, and historical wording
        remain conversational text.  Ambiguous requests are left to the selected
        model rather than causing an unexpected side effect.
        """
        # First, parse explicit commands from composer
        plain_text, parsed_contexts, parsed_command = parse_composer_input(text)
        
        uid = user_id or getattr(turn_request, "userId", None)
        convo_id = getattr(turn_request, "conversationId", None) or session_id
        d_state = None
        if self.dialogue_state_service and convo_id:
            try:
                d_state = self.dialogue_state_service.load(convo_id, user_id=uid)
            except Exception:
                pass
        
        # If there's an explicit command, map it to a tool request
        if parsed_command:
            self._map_explicit_command(parsed_command, plan, user_id=uid)
        
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

        # Explicit slash commands bypass keyword heuristics entirely: the user
        # already typed the verb the system would otherwise have to infer.
        slash = re.match(r"^\s*/(research|deep|image|draw|generate|img)\b\s*(.*)$", text, re.IGNORECASE | re.DOTALL)
        if slash:
            command, rest = slash.group(1).casefold(), slash.group(2).strip(" :.!?")
            if command in {"research", "deep"}:
                if rest and not any(t.toolName == "deep_research" for t in plan.toolRequests):
                    plan.toolRequests.append(ToolRequest(
                        toolName="deep_research",
                        parameters={"topic": rest, "depth": 20},
                    ))
                return
            if command in {"image", "draw", "generate", "img"} and rest and not any(
                t.toolName == "image_generate" for t in plan.toolRequests
            ):
                image_parameters: dict[str, object] = {
                    "prompt": rest,
                    "count": 1,
                    "mode": "quality",
                    "strategy": "variations",
                }
                lower_rest = rest.casefold()
                if re.search(r"\b(ultra|wallpaper|poster|print|8k)\b", lower_rest):
                    image_parameters["mode"] = "ultra"
                elif re.search(r"\b(fast|quick|draft|sketch)\b", lower_rest):
                    image_parameters["mode"] = "fast"
                for style_name in ("anime", "realistic", "cinematic", "watercolor"):
                    if style_name in lower_rest:
                        image_parameters["style"] = style_name
                        break
                if re.search(r"\b\d+\s+(?:images?|variants?|versions?)\b", lower_rest):
                    image_parameters["count"] = min(int(re.search(r"\b(\d+)\s+(?:images?|variants?|versions?)", lower_rest).group(1)), 4)
                plan.toolRequests.append(ToolRequest(toolName="image_generate", parameters=image_parameters))
                return

        def is_command(patterns: list[str], *, target: str) -> bool:
            if not re.search(target, unquoted, re.IGNORECASE):
                return False
            return any(re.search(pattern, unquoted, re.IGNORECASE) for pattern in patterns)

        # Flexible, natural image search trigger supporting prefixes, typos (sho/show), and mid-sentence entities
        has_image_kw = bool(re.search(r"\b(images?|imges?|pictures?|photos?|pics?|imgs?|wallpaper|wallpapers?|तस्वीरें|चित्र|फोटो)\b", unquoted, re.I))
        has_fetch_verb = bool(re.search(r"\b(show|sho|display|find|search|get|fetch|bring|see|load|look\s+for|ढूँढ|खोज|दिखा|लाओ)\b", unquoted, re.I))
        # Saying she should get them is a fetch even without a fetch verb: "i want
        # pics of tokyo ghoul" used to fall through to a prose apology that began
        # by claiming images were being fetched.
        has_visual_request = bool(
            has_image_kw
            and re.search(r"\b(want|wanna|need|gimme|give\s+me|send\s+me|looking\s+for|chahe|chahiye)\b", unquoted, re.I)
            and not re.search(r"\b(?:don'?t|didn'?t|do\s+not|no)\s+(?:want|need|asked|ask)\b", unquoted, re.I)
        )
        is_followup_fetch = bool(re.search(r"\b(?:fetch|show|sho|get|see|display|load|bring)\s+(?:them|it|these|those)\b", unquoted, re.I))
        is_generate_action = bool(re.search(r"\b(generate|genrate|fenerate|generat|create|creat|make|draw|paint|render|बनाओ|बनाऊ|बनाइदेऊ|गर)\b", unquoted, re.I))
        has_reference_intent = bool(re.search(r"\b(reference|refrence|referance|as\s+ref|referencing|refer to)\b", unquoted, re.I))
        has_art_platform = bool(re.search(r"\b(pinterest|pintrest|pintrens|deviantart|safebooru|danbooru|pixiv|artstation)\b", unquoted, re.I))
        has_conversational_question = bool(re.search(
            r"\b(tell\s+me\s+about|who\s+is|what\s+is|explain|describe|remember|article|bio|why|how|wtf|didn'?t\s+ask\s+for\s+pictures|not\s+pictures|information\s+about|history\s+of)\b",
            unquoted,
            re.I,
        ))
        is_character_visual = bool(
            (has_fetch_verb or has_image_kw)
            and any(k in unquoted.lower().split() or k in unquoted.lower() for k in CHARACTER_ENTITY_MAP)
            and not is_generate_action
            and not has_reference_intent
            and not has_conversational_question
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
            and not has_conversational_question
            and not (has_research_or_web_intent and not has_image_kw and not has_art_platform)
            and (
                is_character_visual
                or (has_image_kw and (has_fetch_verb or has_visual_request or len(unquoted.split()) <= 4))
                or is_followup_fetch
                or has_art_platform
                or is_image_refinement
                or speech_promised_images
            )
        )

        if image_search_command and not any(t.toolName == "image_search" for t in plan.toolRequests):
            from hinaa_api.media.search_intelligence import (
                build_media_intent,
                compile_image_search_query,
                compiled_image_query_parameters,
                canonical_entity_from_text,
            )

            active_subject = None
            if self.dialogue_state_service is not None and session_id:
                try:
                    d_state = self.dialogue_state_service.load(session_id)
                    if d_state:
                        # Prioritize active_topic if it is set and not a generic placeholder
                        if d_state.active_topic and not any(k in d_state.active_topic.lower() for k in ("anime", "image", "general", "something")):
                            active_subject = d_state.active_topic
                        else:
                            from hinaa_api.dialogue_state import EntityReferenceResolver
                            active_subject = EntityReferenceResolver.get_active_character(d_state) or d_state.active_topic
                except Exception:
                    pass

            if not active_subject and session_id:
                try:
                    history = self.memory.context(session_id)
                    recent_user_turns = [c for r, c in reversed(history) if r == "user"][:3]
                    for content in recent_user_turns:
                        if content.strip().casefold() == plain_text.strip().casefold():
                            continue
                        prof = canonical_entity_from_text(content)
                        if prof:
                            active_subject = prof.canonical_name
                            break
                except Exception:
                    pass

            media_intent = build_media_intent(unquoted, active_subject=active_subject)
            if media_intent:
                spec = compile_image_search_query(media_intent)
                final_query = spec.primary_query
                canonical_subject = media_intent.canonical_subject
            else:
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
                    r"(?i)\s+(?:images?|imges?|pictures?|photos?|pics?|imgs?|wallpaper|wallpapers?|fanart|art|portrait|drawings?)$",
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
                if not resolved_query and d_state and getattr(d_state, "active_topic", None):
                    if not any(k in d_state.active_topic.lower() for k in ("anime", "image", "general", "something")):
                        resolved_query = d_state.active_topic

                if not resolved_query and session_id:
                    try:
                        history = self.memory.context(session_id)
                        for role, content in reversed(history):
                            if role == "user":
                                if content.strip().casefold() == plain_text.strip().casefold():
                                    continue
                                clean_prev = re.sub(r"^/[a-zA-Z0-9_-]+\s*", "", content).strip()
                                for alias in CHARACTER_ENTITY_MAP:
                                    neg_pat = (
                                        r"(?i)\b(?:not|no|stop|forget|leave|don'?t\s+(?:want|mention|search(?:\s+for)?|look(?:\s+for)?|fetch|show|talk(?:\s+about)?))\s+"
                                        r"(?:(?:more|about|searching(?:\s+for)?|looking(?:\s+for)?|fetching|showing|talking(?:\s+about)?)\s+)?"
                                        + re.escape(alias)
                                        + r"\b|\b"
                                        + re.escape(alias)
                                        + r"\s+(?:mat|nahi|nhi|na|haina|chaidaina)\b"
                                    )
                                    clean_prev = re.sub(neg_pat, " ", clean_prev).strip()
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

                final_query = resolved_query or query_candidate or plain_text or text
                final_query = re.sub(r"(?i)^\s*(?:what\s+about|how\s+about|what\s+of|and\s+what\s+about|and|now)\s+", "", final_query).strip()
                for alias, canonical in sorted(CHARACTER_ENTITY_MAP.items(), key=lambda x: -len(x[0])):
                    neg_pat = (
                        r"(?i)\b(?:not|no|stop|forget|leave|don'?t\s+(?:want|mention|search(?:\s+for)?|look(?:\s+for)?|fetch|show|talk(?:\s+about)?))\s+"
                        r"(?:(?:more|about|searching(?:\s+for)?|looking(?:\s+for)?|fetching|showing|talking(?:\s+about)?)\s+)?"
                        + re.escape(alias)
                    )
                    if re.search(neg_pat, final_query):
                        final_query = re.sub(neg_pat, " ", final_query).strip()
                        continue
                    if re.search(rf"\b{re.escape(alias)}\b", final_query, re.IGNORECASE):
                        final_query = re.sub(rf"\b{re.escape(alias)}\b", canonical, final_query, flags=re.IGNORECASE).strip()
                        break
                if final_query.lower() in CHARACTER_ENTITY_MAP:
                    final_query = CHARACTER_ENTITY_MAP[final_query.lower()]
                canonical_subject = final_query.title()

            # Whatever named this subject, a sentence is not one: measured in the
            # browser with an existing conversation, the compiler resolved the
            # turn to the user's own echoed words and the caption read
            # "Found 6 relevant i want pics of tokyo ghoul images.".
            compiled = compiled_image_query_parameters({"query": final_query, "count": 6})
            final_query = str(compiled.get("query") or final_query)
            canonical_subject = str(compiled.get("canonicalSubject") or canonical_subject)

            plan.toolRequests.append(ToolRequest(
                toolName="image_search",
                parameters={"query": final_query, "count": 6, "canonicalSubject": canonical_subject},
            ))

            if re.search(r"[\u0900-\u097F]", plain_text):
                plan.displayText = f"यहाँ {canonical_subject} की कुछ तस्वीरें हैं! ✨"
                plan.spokenText = f"यहाँ {canonical_subject} की कुछ तस्वीरें हैं!"
                plan.language = "hi-IN"
            else:
                plan.displayText = f"Found 6 relevant {canonical_subject} images."
                plan.spokenText = f"Found 6 relevant {canonical_subject} images."
                plan.language = "en-US"
            plan.emotion = Emotion(primary="happy", intensity=0.7, valence=0.7, arousal=0.5)

        image_command = bool(
            re.search(r"\b(?:generate|create|make|draw|paint|render|बनाओ|बनाऊ|बनाइदेऊ|गर)\b.*\b(?:image|images|picture|pictures|photo|photos|portrait|artwork|wallpaper|चित्र|तस्वीर)\b", unquoted, re.I)
            or re.search(r"\b(?:image|images|picture|pictures|photo|photos|चित्र|तस्वीर)\s+(?:generate|create|make|draw|करो|गर)\b", unquoted, re.I)
            or re.search(r"^\s*(?:(?:hey\s+)?hinaa?[\s,]+)?(?:please\s+)?(?:draw|paint)\s+[a-z0-9]", unquoted, re.I)
            or (
                re.search(r"^\s*(?:(?:hey\s+)?hinaa?[\s,]+)?(?:please\s+)?(?:generate|draw|paint|render|create)\s+", unquoted, re.I)
                and any(k in unquoted.lower() for k in ("hina", "hinaa", *CHARACTER_ENTITY_MAP))
            )
            or (
                bool(re.search(r"\b(?:same\s+one|use\s+this|use\s+that|use\s+this\s+image)\b", unquoted, re.I))
                and bool(re.search(r"\b(?:darker|brighter|better|variation|different|in\s+|with\s+|wearing\s+|sitting\s+|standing\s+|looking\s+|smiling)\b", unquoted, re.I))
            )
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

            img_count = 1
            count_m = re.search(r"\b(\d+)\s*(?:images?|pictures?|photos?|variations?|series)\b", lower_text)
            if count_m:
                img_count = min(max(1, int(count_m.group(1))), 4)
            elif re.search(r"\b(?:series\s+of\s+images?|image\s+series|multiple\s+images?|few\s+images?)\b", lower_text):
                img_count = 3
            elif re.search(r"\b(?:two|pair\s+of)\s+(?:images?|pictures?|photos?)\b", lower_text):
                img_count = 2
            elif re.search(r"\b(?:three)\s+(?:images?|pictures?|photos?)\b", lower_text):
                img_count = 3
            elif re.search(r"\b(?:four)\s+(?:images?|pictures?|photos?)\b", lower_text):
                img_count = 4

            image_parameters: dict[str, object] = {
                "prompt": clean_prompt,
                "count": img_count,
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

            # Reference image and subject entity resolution from dialogue state or cross-session memory
            ref_asset_id = None
            ref_entity = None
            if d_state:
                if d_state.selected_asset:
                    ref_asset_id = d_state.selected_asset.get("asset_id") or d_state.selected_asset.get("selected_asset_id")
                    ref_entity = d_state.selected_asset.get("canonical_subject")
                if not ref_asset_id:
                    from hinaa_api.dialogue_state import AssetReferenceResolver
                    ref_asset_id = AssetReferenceResolver.resolve_asset_id(unquoted, d_state)
                if not ref_entity:
                    ref_entity = d_state.active_topic or (d_state.active_entities[0]["name"] if d_state.active_entities and isinstance(d_state.active_entities[0], dict) and "name" in d_state.active_entities[0] else None)

            if not ref_asset_id and self.cross_session_retriever and uid:
                try:
                    evidences = self.cross_session_retriever.retrieve_relevant_context(uid, text, conversation_id=convo_id)
                    for ev in evidences:
                        if ev.source_type == "approved_asset" and ev.metadata and ev.metadata.get("asset_id"):
                            ref_asset_id = ev.metadata["asset_id"]
                            ref_entity = ev.metadata.get("entity") or ref_entity
                            break
                except Exception:
                    pass

            if ref_asset_id:
                image_parameters["reference_images"] = [ref_asset_id]
                image_parameters["reference_asset_id"] = ref_asset_id
            if ref_entity:
                image_parameters["subject_entity"] = ref_entity

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
            from hinaa_api.models import safe_extract_display_text

            topic_str = plain_text
            topic_str = re.sub(r"(?i)\b(?:like|please|pls|hina|bro|babe|can\s+you|could\s+you)\b", "", topic_str).strip()
            topic_str = re.sub(r"(?i)\b(?:i\s+need\s+to\s+complete\s+my\s+assignment|my\s+topic\s+is)\b", "", topic_str).strip()
            topic_str = re.sub(r"(?i)\b(?:make|create|generate|give\s+me|build|write|download)\s+(?:me\s+)?(?:a\s+)?pdf\s*(?:and\s+give\s+me)?\s*(?:based\s+on|about|of|on|for)?\b", "", topic_str).strip()
            topic_str = re.sub(r"(?i)\b(?:make|give\s+me)\s+a?\s*pdf\s*(?:based\s+on|about|of|on|for)?\b", "", topic_str).strip()
            topic_str = re.sub(r"(?i)\bpdf\s*(?:file|document|banao|banau|dinu)?\s*(?:based\s+on|about|of|on|for)?\b", "", topic_str).strip()
            topic_str = re.sub(r"[\"']", "", topic_str).strip()
            topic_str = re.sub(r"\s+", " ", topic_str).strip()

            is_referential = (
                not topic_str
                or len(topic_str) < 4
                or bool(
                    re.search(
                        r"(?i)^(?:based\s+on\s+)?(?:that|this|it|her|the\s+above|above|same|previous|last|what\s+you\s+(?:said|wrote|generated))(?:\s+(?:assignment|report|paper|doc|document|topic|conversation))?$",
                        topic_str,
                    )
                )
                or bool(
                    re.search(
                        r"(?i)^(?:the|that|this|my|her)?\s*(?:assignment|report|paper|doc|document|notes|topic)$",
                        topic_str,
                    )
                )
            )

            extracted_content = ""
            resolved_topic = ""

            # Check conversation context and dialogue state if referential or empty
            if session_id:
                try:
                    if self.dialogue_state_service is not None:
                        d_state = self.dialogue_state_service.load(session_id, user_id)
                        if d_state and d_state.active_topic:
                            resolved_topic = d_state.active_topic
                        elif d_state and d_state.slots.get("topic"):
                            resolved_topic = str(d_state.slots["topic"])
                        elif d_state and d_state.slots.get("subject"):
                            resolved_topic = str(d_state.slots["subject"])

                    history = self.memory.context(session_id)
                    for role, hist_content in reversed(history):
                        if hist_content.strip().casefold() == plain_text.strip().casefold():
                            continue
                        clean_text = safe_extract_display_text(hist_content).strip()
                        if role == "assistant" and len(clean_text) > 80 and not extracted_content:
                            extracted_content = clean_text
                            # Extract topic from title or header if available
                            title_m = re.search(r"^#{1,3}\s+(?:📄\s*)?([^\n]+)", clean_text)
                            if title_m and not resolved_topic:
                                raw_t = title_m.group(1).strip()
                                raw_t = re.sub(r"(?i)\b(?:assignment|report|overview|guide|breakdown|document)\b", "", raw_t).strip(" :-")
                                if len(raw_t) >= 3:
                                    resolved_topic = raw_t
                        elif role == "user" and not resolved_topic:
                            clean_user = re.sub(r"^/[a-zA-Z0-9_-]+\s*", "", clean_text).strip()
                            clean_user = re.sub(r"(?i)\b(?:assignment|complete|karna\s+hai|help\s+me|tell\s+me\s+about|what\s+is|explain|topic\s+is)\b", "", clean_user).strip()
                            clean_user = re.sub(r"[?!.,]", "", clean_user).strip()
                            if len(clean_user) >= 3 and not re.search(r"(?i)^(?:pdf|hi|hey|hello|yes|no|ok|okay|ha|haan)$", clean_user):
                                resolved_topic = clean_user
                except Exception:
                    pass

            if not is_referential and topic_str:
                final_topic = topic_str
            elif resolved_topic:
                final_topic = resolved_topic
            else:
                final_topic = "Comprehensive Academic Research"

            # Clean topic typos
            final_topic = re.sub(r"(?i)\bcryptogrpic\b", "Cryptography", final_topic)
            final_topic = re.sub(r"(?i)\bcryptogrp[a-z]*\b", "Cryptography", final_topic)
            final_topic = re.sub(r"(?i)\bww2\b", "World War II", final_topic)
            final_topic = re.sub(r"(?i)\bwwii\b", "World War II", final_topic)
            final_topic = re.sub(r"(?i)\bww1\b", "World War I", final_topic)

            clean_display_title = final_topic.strip().title()
            if clean_display_title.lower().endswith(("assignment", "report", "document")):
                doc_title = clean_display_title
            else:
                doc_title = f"{clean_display_title} Report"

            body_source = (
                "the write-up already in our conversation"
                if extracted_content
                else "a live multi-source research pass I am running now"
            )

            plan.toolRequests.append(ToolRequest(
                toolName="pdf_generate",
                parameters={
                    "topic": final_topic,
                    "title": doc_title,
                    "category": "Research Report",
                    "content": extracted_content,
                },
            ))

            plan.displayText = (
                f"### 📄 PDF: {clean_display_title}\n\n"
                f"I'm typesetting **{doc_title}** from {body_source}. The document builder only lays "
                f"that material out — it does not add sections, facts, or references of its own.\n\n"
                f"• **Title**: {doc_title}\n"
                f"• **Category**: Research Report\n"
                f"• **Layout**: ReportLab PDF with running header and page numbers\n\n"
                f"If the sources behind it don't answer, I'll tell you straight instead of handing over a filled template."
            )
            plan.spokenText = (
                f"Babe, I'm building your {final_topic} PDF right now from "
                f"{'what we already wrote here' if extracted_content else 'live research'} — "
                f"the download card appears here as soon as the file is really ready."
            )
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

    def _map_explicit_command(
        self, parsed_command: ParsedCommand, plan: AssistantTurnPlan, user_id: str | None = None
    ) -> None:
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

        # 0a. /memory is consent to write the store the memories panel reads. It is
        # resolved here, against the durable service, rather than proposed as a tool
        # call that no handler implements.
        if cmd in {"memory", "remember", "recall"}:
            self._apply_memory_command(clean_args, plan, user_id)
            return

        # 0. Character lookup shortcut (e.g. "/image gojo" or "/image mikasa")
        if clean_args.lower() in CHARACTER_ENTITY_MAP and not flags and cmd in {"image", "images", "img", "pics", "pictures", "search", "find"}:
            from hinaa_api.media.search_intelligence import build_media_intent, compile_image_search_query
            media_intent = build_media_intent(clean_args)
            if media_intent:
                spec = compile_image_search_query(media_intent)
                final_query = spec.primary_query
                canonical_sub = media_intent.canonical_subject
            else:
                canonical_sub = CHARACTER_ENTITY_MAP[clean_args.lower()]
                final_query = canonical_sub
            plan.toolRequests = [t for t in plan.toolRequests if t.toolName not in {"web_search", "image_search", "image_generate"}]
            plan.toolRequests.append(ToolRequest(
                toolName="image_search",
                parameters={"query": final_query, "count": 6, "canonicalSubject": canonical_sub},
            ))
            plan.displayText = f"Found 6 relevant {canonical_sub} images."
            plan.spokenText = f"Found 6 relevant {canonical_sub} images."
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
            # Strip trailing noise tokens like images, imges, pictures, pics, etc.
            prompt_text = re.sub(r"(?i)\b(images?|imges?|pictures?|photos?|pics?|wallpapers?)\b", "", prompt_text).strip()
            prompt_text = prompt_text or "beautiful digital artwork"
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
            from hinaa_api.media.search_intelligence import build_media_intent, compile_image_search_query
            media_intent = build_media_intent(clean_args)
            if media_intent:
                spec = compile_image_search_query(media_intent)
                final_query = spec.primary_query
                canonical_sub = media_intent.canonical_subject
            else:
                clean_q = re.sub(r"(?i)\b(images?|pictures?|photos?|pics?|imgs?|wallpaper|wallpapers?|pinterest|pintrest|pintrens|bro|and|of|from|please|pls)\b", "", clean_args).strip()
                clean_q = re.sub(r"\s+", " ", clean_q).strip()
                if clean_q.lower() in CHARACTER_ENTITY_MAP:
                    clean_q = CHARACTER_ENTITY_MAP[clean_q.lower()]
                final_query = clean_q or clean_args or "anime aesthetic"
                canonical_sub = final_query.title()
            plan.toolRequests = [t for t in plan.toolRequests if t.toolName not in {"web_search", "image_search"}]
            plan.toolRequests.append(ToolRequest(
                toolName="image_search",
                parameters={"query": final_query, "count": 6, "canonicalSubject": canonical_sub},
            ))
            plan.displayText = f"Found 6 relevant {canonical_sub} images."
            plan.spokenText = f"Found 6 relevant {canonical_sub} images."
            plan.language = "en-US"
            plan.emotion = Emotion(primary="happy", intensity=0.7, valence=0.7, arousal=0.5)
            return

        if cmd == "extract":
            urls = [u for u in clean_args.split() if re.match(r"^https?://", u, re.I)]
            if urls:
                plan.toolRequests.append(ToolRequest(toolName="web_extract", parameters={"urls": urls}))
            else:
                plan.toolRequests.append(ToolRequest(toolName="web_search", parameters={"query": clean_args}))
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
            "document": ("document_generate", {"title": clean_args, "content": "", "format": flags.get("format", "pdf")}),
            "create doc": ("document_generate", {"title": clean_args, "content": "", "format": "docx"}),
            "pdf": ("pdf_generate", {"topic": clean_args, "title": clean_args, "content": ""}),
            "gamma": ("create_gamma_presentation", {"topic": clean_args or "Presentation", "format": "presentation"}),
            "deck": ("create_gamma_presentation", {"topic": clean_args or "Pitch Deck", "format": "presentation"}),
            "gamma doc": ("create_gamma_presentation", {"topic": clean_args or "Document", "format": "document"}),
            "gamma webpage": ("create_gamma_presentation", {"topic": clean_args or "Webpage", "format": "webpage"}),
            "presentation": ("create_gamma_presentation", {"topic": clean_args or "Presentation Slides", "format": "presentation"}),
            "slides": ("create_gamma_presentation", {"topic": clean_args or "Presentation Slides", "format": "presentation"}),
            "analyze": ("analyze_text", {"target": clean_args, "focus": "summary"}),
            "summarize": ("summarize_text", {"target": clean_args, "length": "standard"}),
            "plan": ("create_plan", {"goal": clean_args, "horizon": "week"}),
            "play": ("youtube_playback_request", {"query": clean_args}),
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
            from hinaa_api.tools.registry import registry as tool_registry

            tool_name, base_params = command_to_tool[cmd]
            if tool_registry.get_tool(tool_name) is None:
                # No handler implements this action, so proposing it can only end
                # in a failed card. The turn stays conversational instead.
                return
            existing_req = next((t for t in plan.toolRequests if t.toolName == tool_name), None)
            if tool_name in {"pdf_generate", "document_generate"} and not clean_args and not existing_req:
                self._set_command_text(
                    plan,
                    "What should the document be about? Try `/pdf World War II`. I typeset either the "
                    "text you give me or a live research pass on the subject you name — I don't invent "
                    "one from an empty command.",
                )
                return
            if existing_req:
                for k, v in base_params.items():
                    if not existing_req.parameters.get(k):
                        existing_req.parameters[k] = v
            else:
                plan.toolRequests.append(ToolRequest(
                    toolName=tool_name,
                    parameters=base_params,
                ))

    _MEMORY_WRITE_ACTIONS = {"save", "remember", "store", "keep"}
    _MEMORY_READ_ACTIONS = {"recall", "list", "show"}
    _MEMORY_FORGET_ACTIONS = {"delete", "forget", "remove"}

    @staticmethod
    def _set_command_text(plan: AssistantTurnPlan, text: str, spoken: str | None = None) -> None:
        plan.displayText = text
        plan.spokenText = spoken or text
        plan.language = "en-US"

    def _apply_memory_command(
        self, args: str, plan: AssistantTurnPlan, user_id: str | None
    ) -> None:
        """Resolve an explicit /memory command against the durable store.

        The reply carries what the service reported -- a stored entry, a real
        listing, or the refusal reason -- never what the wording implied.
        """
        plan.toolRequests = [t for t in plan.toolRequests if t.toolName != "memory_manage"]

        head, _, tail = args.partition(" ")
        lead = head.lower()
        if lead in self._MEMORY_WRITE_ACTIONS:
            action, body = "save", tail.strip()
        elif lead in self._MEMORY_READ_ACTIONS:
            action, body = "recall", tail.strip()
        elif lead in self._MEMORY_FORGET_ACTIONS:
            action, body = "forget", tail.strip()
        else:
            action, body = "save", args.strip()

        if self.memory_service is None:
            self._set_command_text(
                plan,
                "Memories are not stored on this HINAA instance, so I could not do that.",
            )
            return
        if not user_id:
            self._set_command_text(
                plan,
                "I did not touch your memories: this turn has no signed-in owner to store them under.",
            )
            return

        if action == "save":
            if not body:
                self._set_command_text(
                    plan, "Tell me what to keep, for example: /memory save my favourite colour is teal."
                )
                return
            try:
                saved = self.memory_service.remember(
                    user_id=user_id, content=body, category="preference"
                )
            except HinaaError as err:
                self._set_command_text(plan, f"I did not save that: {err.message}")
                return
            self._set_command_text(
                plan,
                f"Saved to your memories: {saved['content']}",
                "That is saved in your memories.",
            )
            return

        try:
            stored = self.memory_service.list_memories(user_id)
        except HinaaError as err:
            self._set_command_text(plan, f"I could not read your memories: {err.message}")
            return

        needle = body.casefold()
        hits = [m for m in stored if not needle or needle in str(m.get("content", "")).casefold()]

        if action == "recall":
            if not hits:
                self._set_command_text(
                    plan,
                    f'None of your {len(stored)} saved memories mention "{body}".'
                    if needle
                    else "You have no saved memories yet.",
                )
                return
            listing = "\n".join(f"- {m.get('content')}" for m in hits[:8])
            self._set_command_text(
                plan,
                f"From your saved memories:\n{listing}",
                f"I found {len(hits)} of your saved memories.",
            )
            return

        if not hits:
            self._set_command_text(
                plan, f'I have no saved memory matching "{body}", so nothing was removed.'
            )
            return
        if len(hits) > 1:
            listing = "\n".join(f"- {m.get('content')}" for m in hits[:8])
            self._set_command_text(
                plan,
                f"More than one memory matches, so I removed none:\n{listing}\nName one of them exactly.",
                "Several memories match, so I removed none. Name one of them exactly.",
            )
            return
        try:
            self.memory_service.forget(user_id, str(hits[0]["id"]))
        except HinaaError as err:
            self._set_command_text(plan, f"I could not remove that memory: {err.message}")
            return
        self._set_command_text(
            plan,
            f"Removed from your memories: {hits[0].get('content')}",
            "That memory is removed.",
        )

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

    async def _fallback_candidate_modes(self, primary_mode: str) -> list[tuple[str, str | None]]:
        """Configured brains that can take this turn, strongest answer first.

        The point of falling back is to keep the conversation intelligent, so
        order follows answer quality rather than ease of reaching a gateway.
        Gemini stays last among the configured brains: it is the always-ready
        closer, and when the frontier brains are down a weaker real answer still
        beats no answer. Behind all of them sits the measured OmniRoute gateway,
        which only earns a slot while its ``/v1/models`` endpoint answers.
        """
        configured: dict[str, tuple[bool, str | None]] = {
            "claude": (self.settings.claude_configured, self.settings.active_claude_model),
            "codecraft": (self.settings.codecraft_configured, self.settings.active_codecraft_model),
            "custom": (self.settings.custom_configured, self.settings.active_custom_model),
            "cx-gateway": (self.settings.cx_gateway_configured, self.settings.cx_gateway_model),
            "qwen": (self.settings.qwen_configured, self.settings.qwen_model),
            "openai": (self.settings.openai_configured, self.settings.active_openai_model),
            "agent-router": (
                self.settings.agent_router_configured,
                self.settings.active_agent_router_model,
            ),
            "groq": (self.settings.groq_configured, self.settings.groq_model),
            "real": (self.settings.gemini_configured, self.settings.gemini_model),
        }
        primary = "real" if primary_mode == "gemini" else primary_mode

        ready: list[tuple[str, str | None]] = []
        cooling: list[tuple[str, str | None]] = []
        for mode, (is_configured, model) in configured.items():
            if not is_configured or mode == primary:
                continue
            breaker = peek_circuit_breaker(mode)
            if breaker is not None and breaker.cooldown_remaining() > 0:
                cooling.append((mode, model))
            else:
                ready.append((mode, model))

        last_resort: list[tuple[str, str | None]] = []
        if primary != "omniroute" and self.settings.omniroute_configured:
            # Inline on a live turn, so it gets a sub-second budget rather than
            # the reporting default: this machine takes ~2s to report a refused
            # loopback connection, and a stopped fallback container must not
            # cost a spoken turn that time.
            probe = await probe_gateway_models(
                self.settings.active_omniroute_base_url,
                api_key=self.settings.active_omniroute_key,
                timeout=0.6,
            )
            if probe.serving:
                last_resort.append(("omniroute", self.settings.omniroute_model))
            else:
                logger.info("OmniRoute fallback skipped: %s", probe.detail)

        # A brain in cooldown is still better than no candidate at all.
        return ready + cooling + last_resort

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

    def _durable_conversation_context(
        self,
        request: TurnRequest,
        user_id: str | None,
    ) -> tuple[tuple[tuple[str, str], ...], list[str]]:
        history: list[tuple[str, str]] = []
        blocks: list[str] = []
        convo_id = request.conversationId or request.sessionId
        if not user_id or not self.memory_service or not convo_id:
            return tuple(history), blocks

        try:
            ctx = self.memory_service.recent_working_context(user_id, convo_id, limit=6)
            for msg in ctx.get("recentMessages", []):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role and content:
                    history.append((role, content))

            summary = ctx.get("rollingSummary") or {}
            entities = ctx.get("entities") or []
            goal = summary.get("current_goal") or ""
            ent_str = ", ".join(e.get("displayName", "") for e in entities if e.get("displayName"))
            blocks.append(f"conversation_state: goal={goal}; entities={ent_str}")
        except Exception:
            pass

        try:
            res = self.memory_service.resolve_reference_intent(user_id, convo_id, request.text)
            if res and res.get("hasReference"):
                target = (res.get("targetEntity") or {}).get("displayName") or ""
                asset = (res.get("targetAsset") or {}).get("asset_id") or ""
                intent = res.get("intent") or ""
                blocks.append(f"reference_resolution: intent={intent}; target={target}; asset={asset}")
        except Exception:
            pass

        return tuple(history), blocks

    def _route_context_for_turn(
        self,
        request: TurnRequest,
        user_id: str | None,
        d_state: Any = None,
    ) -> "tuple[object, dict[str, Any]]":
        """Phase B2 — route the turn and decide context behavior.

        Directive §39: trivial turns ("yes", "ok", "hey") route FAST — hot
        context only, no heavy historical/vector retrieval, low latency.
        Directive §37: every turn records a ContextManifest for the developer
        inspector; retrieval work performed is observable per-turn.
        Returns (RouteDecision, metadata) — callers use metadata to skip or
        trim expensive retrieval phases.
        """
        from .agent.context_profiles import ContextProfile

        active_goal = getattr(d_state, "active_goal", None) if d_state is not None else None
        decision = self.context_compiler.router.route(
            request.text or "",
            has_active_task=False,
            has_active_project=False,
            has_selected_asset=bool(getattr(d_state, "selected_asset", None)) if d_state is not None else False,
        )
        meta: dict[str, Any] = {
            "profile": decision.profile.value,
            "domain": decision.domain,
            "routes": [r.value for r in decision.routes],
            "skip_recent_working_context": decision.profile is ContextProfile.FAST,
            "skip_history_ranking": False,
        }
        self._context_manifests.append(
            {
                "request_id": getattr(request, "requestId", None) or request.sessionId or "turn",
                "conversation_id": request.conversationId or request.sessionId,
                "profile": decision.profile.value,
                "routes": meta["routes"],
                "reason": decision.reason,
                "active_goal": getattr(active_goal, "goal", None),
            }
        )
        return decision, meta

    def _last_context_manifest(self) -> dict[str, Any] | None:
        """Developer inspector hook (§37) — most recent turn routing record."""
        return self._context_manifests[-1] if self._context_manifests else None

    def _compile_turn_context(
        self,
        *,
        request: TurnRequest,
        history: tuple[tuple[str, str], ...],
        approved: tuple[str, ...],
        session_memories: tuple[str, ...],
        dialogue_state_block: str,
        live_search_block: str,
        decision: Any,
    ) -> "tuple[tuple[tuple[str, str], ...], dict[str, Any]]":
        """B2.1 — canonical context SELECTION for one chat turn (directive §1).

        The ContextCompiler decides WHAT history/memory/live state the model
        receives; assembly and providers only decide HOW it is serialized.

        Returns (selected_history, selection_meta). ``selected_history`` is the
        compiler-ranked, budgeted turn sequence that assembly renders verbatim
        (history_preselected=True) and providers consume without re-slicing.
        Every include decision is recorded in the turn's ContextManifest.
        """
        from .agent.compiler import estimate_tokens
        from .agent.context_items import ContextManifest, ManifestStatus
        from .agent.context_profiles import ContextProfile

        profile = decision.profile
        history_list = [
            {"role": role, "content": content}
            for role, content in history
        ]

        # Canonical selection — ContextCompiler is the single canonical authority (§1/§2/§11)
        # deciding what history, memories, live state, and external evidence reach the model.
        compiled = self.context_compiler.compile(
            system_identity="",  # system identity is owned by assembly layers
            user_query=request.text or "",
            history=history_list,
            memories=[
                {"id": f"sm_{i}", "content": m}
                for i, m in enumerate(session_memories)
            ],
            profile=profile,
            request_id=getattr(request, "requestId", None) or request.sessionId or "turn",
            conversation_id=request.conversationId or request.sessionId,
            dialogue_state=dialogue_state_block or "",
            live_search_evidence=[live_search_block] if live_search_block else None,
            approved_memories=approved,
        )
        manifest = compiled.manifest
        assert manifest is not None

        # Compiler-selected conversation turns → the tuple assembly renders verbatim.
        selected: list[tuple[str, str]] = [
            (m.get("role", "user"), m.get("content", ""))
            for m in compiled.dialogue_messages
        ]

        # Serializing pre-selected history re-adds role prefixes and the
        # untrusted wrapper — reserve for them so the manifest stays honest.
        serialization_overhead = sum(
            estimate_tokens(f"{r}: {c}") + 8 for r, c in selected
        )
        manifest.token_estimate += serialization_overhead
        manifest.status = ManifestStatus.OK

        meta: dict[str, Any] = {
            "manifest_id": manifest.manifest_id,
            "profile": manifest.profile,
            "selected_history_turns": len(selected),
            "selected_history_tokens": sum(estimate_tokens(c) for _, c in selected),
            "compile_ms": manifest.compile_ms,
            "dedup_dropped": manifest.dedup_dropped,
            "excluded_count": len(manifest.excluded_items),
        }

        # Record the full manifest for the developer inspector (§37).
        self._context_manifests.append(manifest.to_dict())
        return tuple(selected), meta

    def _record_episode_turn(
        self,
        *,
        request: TurnRequest,
        user_id: str | None,
        assistant_text: str,
    ) -> None:
        """B2 §17–§22 — fold the finished turn into the persistent episode tree.

        Best-effort: episode summarization must never fail a chat turn.
        """
        if self.episode_summarizer is None:
            return
        convo_id = request.conversationId or request.sessionId
        try:
            seq = self._episode_turn_counters.get(convo_id, 0) + 1
            self._episode_turn_counters[convo_id] = seq
            # Keep the counter map bounded.
            if len(self._episode_turn_counters) > 2048:
                self._episode_turn_counters.popitem()
            boundary = self.episode_summarizer.detect_boundary(
                request.text or "",
                previous_turn_text=None,
                seconds_since_last_turn=None,
                current_episode_turns=0,
            )
            self.episode_summarizer.record_turn(
                conversation_id=convo_id,
                user_id=user_id,
                sequence=seq,
                user_text=request.text or "",
                assistant_text=assistant_text[:800],
                force_new_episode=boundary.new_episode,
                boundary_reason=boundary.reason,
            )
        except Exception:
            logger.debug("Episode summarization skipped", exc_info=True)

    def _should_pre_search(self, text: str, d_state: Any = None) -> bool:
        """True when the user query explicitly or implicitly asks for current/real-time facts."""
        if not text or len(text.strip()) < 4:
            return False
        lowered = text.strip().lower()

        # Suppress commands and generative tool requests
        if lowered.startswith(("/", "!", "\\")):
            return False
        if re.search(r"\b(generate|create|make|draw|paint|sketch|build|write\s+(?:a|me|an)?\s*(?:code|script|doc|pdf|essay|story|poem))\b", lowered):
            return False
        if re.search(r"\b(who\s+are\s+you|what\s+is\s+your\s+name|do\s+you\s+love\s+me|tell\s+me\s+a\s+joke|say\s+something)\b", lowered):
            return False
        if re.search(r"^(hi|hello|hey|yo|namaste|good\s+(?:morning|evening|afternoon|night)|k\s+cha|kasto\s+cha)[!., ]*$", lowered):
            return False

        # CRITICAL: She must not Google herself.
        # "What is the current state of Hina?" contains "current", which the
        # temporal indicators below treat as a live-facts signal. The search then
        # returns anime characters named Hina, and because retrieved web context is
        # declared authoritative she answers about One Piece instead of her own
        # runtime. Questions about her are answered from MEASURED SELF STATE.
        _SELF_TOPIC = (
            r"(?:system|state|status|architecture|subsystem|capabilit\w*|memory|memories|"
            r"tool\w*|brain|model|provider|limit\w*|feature\w*|voice|ability|abilities|dashboard)"
        )
        is_about_herself = bool(
            re.search(rf"\b(?:your|her)\s+{_SELF_TOPIC}\b", lowered)
            or re.search(rf"\bhinaa?'s\s+{_SELF_TOPIC}\b", lowered)
            or re.search(rf"\b{_SELF_TOPIC}\s+of\s+hinaa?\b", lowered)
            or re.search(r"\bhow\s+(?:do|does)\s+(?:you|she|hinaa?)\s+work\b", lowered)
            or re.search(r"\bhinaa?\b[^?.]{0,40}\bexplain\b", lowered)
        )
        if is_about_herself:
            logger.info("Pre-search suppressed: the question is about her own runtime.")
            return False

        # CRITICAL: Referent-Before-Research Guard.
        # If the user utterance is anaphoric/pronoun-based ("tell me more details about her", "who is she",
        # "tell me about him") without a concrete named entity in this turn, AND dialogue state has NO
        # active entity or topic antecedent, we MUST NOT fire an ungrounded web search!
        try:
            from hinaa_api.dialogue_state import build_semantic_turn_frame
            frame = build_semantic_turn_frame(text, d_state)
            if not frame.referent_resolved:
                logger.info("Pre-search suppressed: referent ungrounded for %r", text)
                return False
        except Exception:
            pass

        # Explicit search intent
        if re.search(r"\b(search\s+(?:the\s+)?web|search\s+online|google|look\s+up\s+online|check\s+online|browse)\b", lowered):
            return True

        # Real-time / temporal indicators requiring up-to-date knowledge
        temporal_indicators = [
            r"\blatest\b",
            r"\bcurrent(?:ly)?\b",
            r"\bnews\b",
            r"\btoday(?:'s)?\b",
            r"\byesterday\b",
            r"\btonight\b",
            r"\bright\s+now\b",
            r"\bthis\s+(?:week|month|year)\b",
            r"\brecent(?:ly)?\b",
            r"\bbreaking\b",
            r"\bupdates?\b",
            r"\bsituation\b",
            r"\bdetails?\s+(?:about|on|of)\b",
            r"\binfo(?:rmation)?\s+(?:about|on|regarding)\b",
            r"\bwho\s+is\s+(?:the\s+)?(?:current|new|present)\b",
            r"\bwhat\s+(?:is|are)\s+the\s+(?:latest|current|recent)\b",
            r"\bwhat(?:'s|\s+is)\s+happening\b",
            r"\bwhat\s+happened\s+(?:today|recently|in\s+202[4-9])\b",
            r"\bweather\s+(?:in|for|today|forecast)\b",
            r"\blive\s+score\b",
            r"\bstock\s+price\b",
            r"\b202[5-9]\b",
        ]
        try:
            from hinaa_api.intelligence.research_detector import ResearchNeedDetector
            needs_res, _ = ResearchNeedDetector.needs_research(text)
            if needs_res:
                return True
        except Exception:
            pass
        return any(re.search(pat, lowered) for pat in temporal_indicators)

    def _extract_search_query(self, text: str, d_state: Any = None) -> str:
        """Normalize user text to an effective search query without assistant names."""
        query = re.sub(
            r"(?i)^\s*(?:(?:hey\s+)?hinaa?\b|babe\b|bro\b|please\b|can\s+you\b|could\s+you\b|tell\s+me\b|check\b|search(?:\s+for)?\b|look\s+up\b|what\s+is\b|what\s+are\b|what's\b|find\b|[ ,!.-])+",
            "",
            text.strip(),
        ).strip(" ?!.,;:")
        # Strip trailing companion address names (e.g. "find details about it hina" -> "details about it")
        query = re.sub(
            r"(?i)\s+(?:hina|hinaa|babe|bro|please|pls)$",
            "",
            query,
        ).strip(" ?!.,;:")
        # Resolve referential pronouns using active dialogue state topic if available
        if d_state and getattr(d_state, "active_topic", None):
            topic = d_state.active_topic
            if re.search(r"(?i)\b(?:about|of|on|regarding)\s+(?:it|this|that|her|him|them)\b", query):
                query = re.sub(r"(?i)\b(?:about|of|on|regarding)\s+(?:it|this|that|her|him|them)\b", f"about {topic}", query)
            elif query.strip().lower() in {"it", "this", "that", "them", "her", "him", "details", "more details", "news"}:
                query = f"{topic} latest {query}".strip()
        return query if len(query) >= 3 else text.strip()

    async def create_plan(
        self, request: TurnRequest, *, user_id: str | None = None
    ) -> ProviderResult[AssistantTurnPlan]:
        convo_id = request.conversationId or request.sessionId
        d_state = None
        dialogue_state_block = ""
        live_search_block = ""
        if self.dialogue_state_service and convo_id:
            try:
                d_state = self.dialogue_state_service.load(convo_id, user_id=user_id)
                if d_state:
                    from hinaa_api.dialogue_state import DialogueStateService, EntityReferenceResolver
                    DialogueStateService.extract_goal_and_constraints(d_state, request.text)
                    EntityReferenceResolver.update_entities_from_text(d_state, request.text)
                    DialogueStateService.update_topic_from_request(d_state, request.text)
                    self.dialogue_state_service.save(d_state)
            except Exception:
                logger.debug("Failed to extract goal/constraints in plan", exc_info=True)

        if user_id:
            self._handle_continuity_promotions(user_id, convo_id, request.text)

        # Phase B2 — route this turn's context needs BEFORE heavy retrieval.
        try:
            _route_decision, _route_meta = self._route_context_for_turn(request, user_id, d_state)
        except Exception:
            logger.debug("Context routing failed — defaulting to STANDARD", exc_info=True)
            _route_decision, _route_meta = None, {"profile": "STANDARD", "routes": ["HOT"]}

        # Real-time pre-turn live web search grounding. Trivial FAST turns
        # never hit search (§39: simple chat must not suffer or pay for it).
        grounded_sources: list[Any] = []
        if (
            request.providerMode != "mock"
            and not _route_meta.get("skip_recent_working_context")
            and self._should_pre_search(request.text, d_state=d_state)
        ):
            search_query = self._extract_search_query(request.text, d_state=d_state)
            # Calculate bounded research budget (Light: 3-4, Standard: 6, Deep: 10, Max: 15)
            try:
                from hinaa_api.intelligence.answer_depth import AnswerDepth, AnswerDepthController
                _depth = AnswerDepthController.infer_depth(request.text, active_goal=getattr(d_state, "active_goal", None) if d_state else None)
                if _depth == AnswerDepth.QUICK:
                    search_budget = 4
                elif _depth == AnswerDepth.STANDARD:
                    search_budget = 6
                elif _depth == AnswerDepth.DETAILED:
                    search_budget = 8
                elif _depth == AnswerDepth.DEEP:
                    search_budget = 10
                else:
                    search_budget = 15
            except Exception:
                search_budget = 6

            try:
                from hinaa_api.tools.browser import search_web
                from hinaa_api.grounding.citations import EvidenceSource, CitationRenderer
                from datetime import datetime, timezone
                search_res = await asyncio.wait_for(
                    search_web({"query": search_query, "count": search_budget}),
                    timeout=5.0,
                )
                items = search_res.get("results") or search_res.get("sources") or []
                if items:
                    now = datetime.now(timezone.utc)
                    formatted_date = now.strftime("%A, %B %d, %Y")
                    grounded_sources = [
                        EvidenceSource(
                            source_id=str(idx),
                            title=itm.get("title") or "Source",
                            publisher=itm.get("domain") or "",
                            url=itm.get("url") or "",
                            date=itm.get("date"),
                            snippet=itm.get("snippet") or "",
                        )
                        for idx, itm in enumerate(items[:25], 1)
                    ]
                    lines = [
                        f"LIVE REAL-TIME WEB SEARCH INTELLIGENCE ({len(items)} Sources Retrieved {formatted_date} for query: {search_query!r}):",
                        "Synthesize these retrieved facts into an authoritative, structured response with verified claims:",
                    ]
                    for idx, s in enumerate(grounded_sources, 1):
                        clean_title = CitationRenderer.sanitize_untrusted_text(s.title)
                        clean_snippet = CitationRenderer.sanitize_untrusted_text(s.snippet)
                        lines.append(f"[{idx}] [{s.publisher}] {clean_title}: {clean_snippet} ({s.url})")
                    lines.extend([
                        "OPERATIONAL MANDATE (CRITICAL):",
                        "- Synthesize across these live sources into an authoritative, high-impact analysis or report.",
                        "- Attribute key claims with numbered bracket citations matching the sources above: e.g. [1], [2].",
                        "- ZERO REPETITION: Do NOT repeat paragraphs, regurgitate text blocks, or echo previous turns. Never cut off mid-thought.",
                        "- spokenText: Deliver a substantive, intelligent executive voice summary covering core findings and significance.",
                        "- Make displayText directly informative, structured with key bullets, clear headings, and zero repetitive filler.",
                    ])
                    live_search_block = "\n".join(lines)

                    if d_state is not None:
                        d_state.tool_result_sets.append({
                            "tool": "web_search",
                            "query": search_query,
                            "items": items[:25],
                            "timestamp": now.isoformat(),
                        })
                        try:
                            self.dialogue_state_service.save(d_state)
                        except Exception:
                            pass
            except Exception:
                logger.debug("Pre-search grounding skipped or timed out", exc_info=True)

        if d_state is not None:
            try:
                from hinaa_api.dialogue_state import build_dialogue_state_block
                dialogue_state_block = build_dialogue_state_block(d_state)
            except Exception:
                pass

        history = self.memory.context(request.sessionId)
        approved = self._approved_blocks(user_id)
        session_memories = _dedupe_session_facts(
            self.memory.learned_memories(request.sessionId), approved
        )
        # B2.1 §1 — canonical context selection BEFORE assembly. The compiler
        # (not the assembler/providers) decides which turns reach the model.
        route_decision, _route_meta = self._route_context_for_turn(request, user_id, d_state)
        history, selection_meta = self._compile_turn_context(
            request=request,
            history=history,
            approved=approved,
            session_memories=session_memories,
            dialogue_state_block=dialogue_state_block,
            live_search_block=live_search_block,
            decision=route_decision,
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
            dialogue_state_block=dialogue_state_block,
            live_search_block=live_search_block,
            history_preselected=True,
        )
        self._log_prompt_meta(
            request.sessionId,
            prompt.fingerprint,
            "rest",
            manifest_id=selection_meta.get("manifest_id"),
        )
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
        attempted_brain = request.providerMode

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
                attempted_brain = getattr(provider, "id", None) or request.providerMode
                result = await provider.create_plan(
                    request.text,
                    request.companionId,
                    request.language,
                    history,
                    prompt,
                )
                self._record_brain_call(
                    attempted_brain, ok=True, model=request.brainModel or ""
                )
                if request.providerMode == "mock" and self.cross_session_retriever and user_id:
                    try:
                        evs = self.cross_session_retriever.retrieve_relevant_context(
                            user_id, request.text, conversation_id=convo_id
                        )
                        for ev in evs:
                            if ev.source_type == "project" and ev.content:
                                result.value.displayText = ev.content
                                result.value.spokenText = ev.content
                                break
                    except Exception:
                        pass
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

            self._record_brain_call(attempted_brain, ok=False, error=error)

            if getattr(error, "code", None) == "SAFETY_REFUSAL":
                logger.warning("Primary brain returned SAFETY_REFUSAL; raising without fallback or retry.")
                raise error

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
                attempted_brain = getattr(provider, "id", None) or request.providerMode
                try:
                    async with asyncio.timeout(primary_plan_timeout):
                        result = await provider.create_plan(
                            request.text,
                            request.companionId,
                            request.language,
                            history,
                            prompt,
                        )
                    self._record_brain_call(
                        attempted_brain, ok=True, model=request.brainModel or ""
                    )
                    retry_succeeded = True
                except Exception as retry_err:
                    if isinstance(retry_err, HinaaError):
                        error = retry_err
                    else:
                        error = HinaaError("PROVIDER_UNAVAILABLE", str(retry_err), 503, True)
                    self._record_brain_call(attempted_brain, ok=False, error=error)

            if not retry_succeeded:
                if getattr(error, "code", None) == "SAFETY_REFUSAL":
                    logger.warning("Provider returned SAFETY_REFUSAL; raising without fallback.")
                    raise error
                if self.settings.auto_fallback_enabled and error.code in FALLBACK_ELIGIBLE_ERROR_CODES:
                    fallback_result = None
                    for fb_mode, fb_model in await self._fallback_candidate_modes(request.providerMode):
                        try:
                            logger.info(
                                "Primary brain %s failed with %s; falling back to %s (%s)",
                                request.providerMode,
                                error.code,
                                fb_mode,
                                fb_model,
                            )
                            fb_brain = fb_mode
                            fb_provider = self.router.llm(fb_mode, fb_model)
                            fb_brain = getattr(fb_provider, "id", None) or fb_mode
                            async with asyncio.timeout(max(45.0, primary_plan_timeout)):  # Enough for Gemini/other fallbacks
                                fallback_result = await fb_provider.create_plan(
                                    request.text,
                                    request.companionId,
                                    request.language,
                                    history,
                                    prompt,
                                )
                            self._record_brain_call(fb_brain, ok=True, model=fb_model or "")
                            logger.info("Fallback to %s succeeded", fb_mode)
                            is_fallback = True
                            fallback_reason = f"Primary {request.providerMode} failed: {error.code}"
                            resolved_provider = fb_mode
                            resolved_model = fb_model
                            break
                        except Exception as fb_exc:
                            self._record_brain_call(fb_brain, ok=False, error=fb_exc)
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
        _apply_response_quality_guard(result.value, evidence_sources=grounded_sources)
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
            user_id=user_id,
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

        # B2 summary tree (§17–§24): fold the finished turn into the open
        # episode. Incremental — only this turn's sequence is summarized.
        self._record_episode_turn(
            request=request,
            user_id=user_id,
            assistant_text=result.value.displayText or result.value.spokenText or "",
        )

        self._persist_learned_memories(user_id, request.sessionId)

        return result

    async def create_live_plan(
        self,
        request: TurnRequest,
        emit_delta: Callable[[str], Awaitable[None]],
        *,
        user_id: str | None = None,
        emit_event: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None,
    ) -> ProviderResult[AssistantTurnPlan]:
        from .providers.timing import ProviderTiming

        convo_id = request.conversationId or request.sessionId
        d_state = None
        dialogue_state_block = ""
        live_search_block = ""
        if self.dialogue_state_service and convo_id:
            try:
                d_state = self.dialogue_state_service.load(convo_id, user_id=user_id)
                if d_state:
                    from hinaa_api.dialogue_state import DialogueStateService, EntityReferenceResolver
                    DialogueStateService.extract_goal_and_constraints(d_state, request.text)
                    EntityReferenceResolver.update_entities_from_text(d_state, request.text)
                    DialogueStateService.update_topic_from_request(d_state, request.text)
                    self.dialogue_state_service.save(d_state)
            except Exception:
                logger.debug("Failed to extract goal/constraints in live plan", exc_info=True)

        if user_id:
            self._handle_continuity_promotions(user_id, convo_id, request.text)

        # Phase B2 — route this turn's context needs BEFORE heavy retrieval.
        try:
            _route_decision, _route_meta = self._route_context_for_turn(request, user_id, d_state)
        except Exception:
            logger.debug("Context routing failed — defaulting to STANDARD", exc_info=True)
            _route_decision, _route_meta = None, {"profile": "STANDARD", "routes": ["HOT"]}

        # Real-time pre-turn live web search grounding. Trivial FAST turns
        # never hit search (§39: simple chat must not suffer or pay for it).
        grounded_sources: list[Any] = []
        if (
            request.providerMode != "mock"
            and not _route_meta.get("skip_recent_working_context")
            and self._should_pre_search(request.text, d_state=d_state)
        ):
            search_query = self._extract_search_query(request.text, d_state=d_state)
            # Calculate bounded research budget (Light: 3-4, Standard: 6, Deep: 10, Max: 15)
            try:
                from hinaa_api.intelligence.answer_depth import AnswerDepth, AnswerDepthController
                _depth = AnswerDepthController.infer_depth(request.text, active_goal=getattr(d_state, "active_goal", None) if d_state else None)
                if _depth == AnswerDepth.QUICK:
                    search_budget = 4
                elif _depth == AnswerDepth.STANDARD:
                    search_budget = 6
                elif _depth == AnswerDepth.DETAILED:
                    search_budget = 8
                elif _depth == AnswerDepth.DEEP:
                    search_budget = 10
                else:
                    search_budget = 15
            except Exception:
                search_budget = 6

            if emit_event:
                try:
                    await emit_event("agent.step.started", {
                        "runId": convo_id or "run",
                        "stepId": "web_search",
                        "event": {
                            "event_type": "agent.step.started",
                            "run_id": convo_id or "run",
                            "step_id": "web_search",
                            "payload": {
                                "title": "Searching the live web",
                                "message": f"Looking up live information: \"{search_query}\"",
                            },
                        },
                    })
                    await emit_event("search.started", {
                        "query": search_query,
                        "correlationId": convo_id,
                    })
                except Exception:
                    pass
            try:
                from hinaa_api.tools.browser import search_web
                from hinaa_api.grounding.citations import EvidenceSource, CitationRenderer
                from datetime import datetime, timezone
                search_res = await asyncio.wait_for(
                    search_web({"query": search_query, "count": search_budget}),
                    timeout=5.0,
                )
                items = search_res.get("results") or search_res.get("sources") or []
                if emit_event:
                    try:
                        await emit_event("agent.step.completed", {
                            "runId": convo_id or "run",
                            "stepId": "web_search",
                            "event": {
                                "event_type": "agent.step.completed",
                                "run_id": convo_id or "run",
                                "step_id": "web_search",
                                "payload": {
                                    "title": "Web search completed",
                                    "message": f"Retrieved {len(items)} live sources",
                                },
                            },
                        })
                        await emit_event("search.completed", {
                            "query": search_query,
                            "sourcesCount": len(items),
                            "correlationId": convo_id,
                        })
                    except Exception:
                        pass
                if items:
                    now = datetime.now(timezone.utc)
                    formatted_date = now.strftime("%A, %B %d, %Y")
                    grounded_sources = [
                        EvidenceSource(
                            source_id=str(idx),
                            title=itm.get("title") or "Source",
                            publisher=itm.get("domain") or "",
                            url=itm.get("url") or "",
                            date=itm.get("date"),
                            snippet=itm.get("snippet") or "",
                        )
                        for idx, itm in enumerate(items[:25], 1)
                    ]
                    lines = [
                        f"LIVE REAL-TIME WEB SEARCH INTELLIGENCE ({len(items)} Sources Retrieved {formatted_date} for query: {search_query!r}):",
                        "Synthesize these retrieved facts into an authoritative, structured response with verified claims:",
                    ]
                    for idx, s in enumerate(grounded_sources, 1):
                        clean_title = CitationRenderer.sanitize_untrusted_text(s.title)
                        clean_snippet = CitationRenderer.sanitize_untrusted_text(s.snippet)
                        lines.append(f"[{idx}] [{s.publisher}] {clean_title}: {clean_snippet} ({s.url})")
                    lines.extend([
                        "OPERATIONAL MANDATE (CRITICAL):",
                        "- Synthesize across these live sources into an authoritative, high-impact analysis or report.",
                        "- Attribute key claims with numbered bracket citations matching the sources above: e.g. [1], [2].",
                        "- ZERO REPETITION: Do NOT repeat paragraphs, regurgitate text blocks, or echo previous turns. Never cut off mid-thought.",
                        "- spokenText: Deliver a substantive, intelligent executive voice summary covering core findings and significance.",
                        "- Make displayText directly informative, structured with key bullets, clear headings, and zero repetitive filler.",
                    ])
                    live_search_block = "\n".join(lines)

                    if d_state is not None:
                        d_state.tool_result_sets.append({
                            "tool": "web_search",
                            "query": search_query,
                            "items": items[:25],
                            "timestamp": now.isoformat(),
                        })
                        try:
                            self.dialogue_state_service.save(d_state)
                        except Exception:
                            pass
            except Exception:
                logger.debug("Live pre-search grounding skipped or timed out", exc_info=True)

        if d_state is not None:
            try:
                from hinaa_api.dialogue_state import build_dialogue_state_block
                dialogue_state_block = build_dialogue_state_block(d_state)
            except Exception:
                pass

        timing = ProviderTiming()
        history = self.memory.context(request.sessionId)
        approved = self._approved_blocks(user_id)
        session_memories = _dedupe_session_facts(
            self.memory.learned_memories(request.sessionId), approved
        )
        # B2.1 §1 — canonical context selection BEFORE assembly (realtime path).
        route_decision_rt, _route_meta_rt = self._route_context_for_turn(request, user_id, d_state)
        history, selection_meta_rt = self._compile_turn_context(
            request=request,
            history=history,
            approved=approved,
            session_memories=session_memories,
            dialogue_state_block=dialogue_state_block,
            live_search_block=live_search_block,
            decision=route_decision_rt,
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
            dialogue_state_block=dialogue_state_block,
            live_search_block=live_search_block,
            history_preselected=True,
        )
        timing.mark("prompt_built")
        self._log_prompt_meta(
            request.sessionId,
            prompt.fingerprint,
            "realtime",
            manifest_id=selection_meta_rt.get("manifest_id"),
        )
        fast_provider_id: str | None = None
        requested_provider = request.providerMode
        requested_model = request.brainModel
        resolved_provider = requested_provider
        resolved_model = requested_model
        is_fallback = False
        fallback_reason: str | None = None

        is_remote_primary = request.providerMode in ("claude", "agent-router", "cx-gateway", "custom")
        primary_idle_timeout = self.settings.llm_stream_idle_timeout_seconds
        primary_live_timeout = max(
            self.settings.llm_stream_ceiling_seconds, primary_idle_timeout
        )
        primary_text: list[str] = []
        primary_idle_expired: Callable[[], bool] = lambda: False
        attempted_brain = request.providerMode

        try:
            async with live_generation_window(
                ceiling_s=primary_live_timeout,
                idle_s=primary_idle_timeout,
                forward=emit_delta,
                sink=primary_text,
            ) as (primary_emit, idle_expired):
                primary_idle_expired = idle_expired
                provider = self._fast_casual_provider(
                    request.providerMode, request.text, history
                )
                fast_provider_id = getattr(provider, "id", None)
                if provider is None:
                    provider = self.router.llm(
                        request.providerMode, request.brainModel
                    )
                attempted_brain = getattr(provider, "id", None) or request.providerMode
                if isinstance(provider, GeminiLLMProvider | GroqLLMProvider | OpenAILLMProvider | AgentRouterOpenAIProvider | AgentRouterAnthropicProvider):
                    result = await provider.create_live_plan(
                        request.text,
                        request.companionId,
                        request.language,
                        history,
                        primary_emit,
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
                    # The interface now names the brain that answered, so record
                    # the one that actually ran rather than the one requested.
                    resolved_provider = getattr(provider, "id", None) or resolved_provider
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

                    # If mock mode and cross-session project fact was queried
                    if self.cross_session_retriever and user_id and ("nova" in request.text.lower() or "what db" in request.text.lower() or "which db" in request.text.lower() or "database" in request.text.lower()):
                        try:
                            evs = self.cross_session_retriever.retrieve_relevant_context(
                                user_id, request.text, conversation_id=convo_id
                            )
                            for ev in evs:
                                if ev.source_type == "project" and ev.content:
                                    result.value.displayText = ev.content
                                    result.value.spokenText = ev.content
                                    break
                        except Exception:
                            pass

                    display = result.value.displayText
                    for start in range(0, len(display), 7):
                        chunk = display[start : start + 7]
                        timing.mark("first_text_delta")
                        await primary_emit(chunk)
                        await asyncio.sleep(0.006)
                    timing.mark("text_complete")
                    result = ProviderResult(
                        result.value,
                        result.provider,
                        result.latency_ms,
                        stages=timing.snapshot(),
                    )
            self._record_brain_call(
                attempted_brain, ok=True, model=request.brainModel or ""
            )
        except (HinaaError, TimeoutError, Exception) as raw_error:
            if isinstance(raw_error, TimeoutError):
                timed_out_idle = primary_idle_expired()
                error = HinaaError(
                    "PROVIDER_TIMEOUT",
                    (
                        f"Live primary brain {request.providerMode} went silent for "
                        f"{primary_idle_timeout}s."
                        if timed_out_idle
                        else f"Live primary brain {request.providerMode} exceeded the "
                        f"{primary_live_timeout}s ceiling for one turn."
                    ),
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

            self._record_brain_call(attempted_brain, ok=False, error=error)

            if getattr(error, "code", None) == "SAFETY_REFUSAL":
                logger.warning("Live primary brain returned SAFETY_REFUSAL; raising without fallback or retry.")
                raise error

            kept_text = "".join(primary_text).strip()
            keep_streamed_text = len(kept_text) >= _MIN_STREAMED_CHARS_TO_KEEP
            if keep_streamed_text:
                # The user already watched this brain answer. Shipping another
                # model's reply over the top of it would put words on screen that
                # she never wrote, so finish with what she actually produced.
                logger.warning(
                    "Live primary %s ended with %s chars already streamed; keeping her "
                    "own text instead of answering with a fallback brain (%s).",
                    request.providerMode,
                    len(kept_text),
                    error.code,
                )
                result = ProviderResult(
                    build_plan_from_text(
                        text=kept_text,
                        companion_id=request.companionId,
                        language=request.language,
                        depth=prompt.response_depth,
                    ),
                    provider=request.providerMode,
                    latency_ms=timing.ms_since_start("prompt_built") or 0,
                    stages=timing.snapshot(),
                )

            live_retry_succeeded = False
            if (
                not keep_streamed_text
                and fast_provider_id
                and error.code in {
                    "PROVIDER_KEY_INVALID",
                    "PROVIDER_UNAVAILABLE",
                    "PROVIDER_RATE_LIMIT",
                }
            ):
                self._mark_fast_key_bad(fast_provider_id)
                selected_provider = self.router.llm(request.providerMode, request.brainModel)
                attempted_brain = getattr(selected_provider, "id", None) or attempted_brain
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
                            self._record_brain_call(
                                attempted_brain, ok=True, model=request.brainModel or ""
                            )
                            live_retry_succeeded = True
                    except HinaaError as retry_err:
                        error = retry_err
                        self._record_brain_call(attempted_brain, ok=False, error=error)
                    except Exception as retry_error:
                        error = HinaaError(
                            "PROVIDER_UNAVAILABLE",
                            "The selected brain could not complete this live turn.",
                            503,
                            True,
                        )
                        self._record_brain_call(attempted_brain, ok=False, error=error)

            if not live_retry_succeeded and not keep_streamed_text:
                if getattr(error, "code", None) == "SAFETY_REFUSAL":
                    logger.warning("Live provider returned SAFETY_REFUSAL; raising without fallback.")
                    raise error
                if self.settings.auto_fallback_enabled and error.code in FALLBACK_ELIGIBLE_ERROR_CODES:
                    fallback_live_result = None
                    for fb_mode, fb_model in await self._fallback_candidate_modes(request.providerMode):
                        try:
                            logger.info(
                                "Live primary %s failed with %s; attempting fallback to %s (%s)",
                                request.providerMode,
                                error.code,
                                fb_mode,
                                fb_model,
                            )
                            fb_brain = fb_mode
                            fb_provider = self.router.llm(fb_mode, fb_model)
                            fb_brain = getattr(fb_provider, "id", None) or fb_mode
                            async with live_generation_window(
                                ceiling_s=primary_live_timeout,
                                idle_s=primary_idle_timeout,
                                forward=emit_delta,
                            ) as (fallback_emit, _):
                                if isinstance(fb_provider, GeminiLLMProvider | GroqLLMProvider | OpenAILLMProvider | AgentRouterOpenAIProvider | AgentRouterAnthropicProvider):
                                    fallback_live_result = await fb_provider.create_live_plan(
                                        request.text,
                                        request.companionId,
                                        request.language,
                                        history,
                                        fallback_emit,
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
                            self._record_brain_call(fb_brain, ok=True, model=fb_model or "")
                            logger.info("Live fallback to %s succeeded", fb_mode)
                            is_fallback = True
                            fallback_reason = f"Primary {request.providerMode} failed: {error.code}"
                            resolved_provider = fb_mode
                            resolved_model = fb_model
                            break
                        except Exception as fb_exc:
                            self._record_brain_call(fb_brain, ok=False, error=fb_exc)
                            logger.warning("Live fallback provider %s failed: %r", fb_mode, fb_exc)
                    if fallback_live_result is not None:
                        result = fallback_live_result
                    else:
                        raise error
                else:
                    raise error

        _apply_response_quality_guard(result.value, is_live=True, evidence_sources=grounded_sources)
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
            user_id=user_id,
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

        # True token-by-token streaming and live research event dispatch.
        # Provider deltas and real-time research events are relayed onto the
        # wire the instant they are produced instead of waiting for the whole
        # plan, so the interface reveals web search animations and text continuously.
        queue: asyncio.Queue[tuple[str, Any] | None] = asyncio.Queue()

        async def emit_delta(delta: str) -> None:
            await queue.put(("delta", delta))

        async def emit_event(name: str, payload: dict[str, Any]) -> None:
            await queue.put(("event", (name, payload)))

        turn_task = asyncio.create_task(
            self.create_live_plan(request, emit_delta, user_id=user_id, emit_event=emit_event)
        )
        emitted: list[str] = []
        delta_sequence = 0

        def _make_delta_event(delta_text: str, seg_id: int = 0) -> bytes:
            nonlocal delta_sequence
            ev = self._event(
                "text.delta",
                {
                    "delta": delta_text,
                    "streamId": correlation_id,
                    "segmentId": seg_id,
                    "sequence": delta_sequence,
                },
            )
            delta_sequence += 1
            return ev

        try:
            while True:
                getter = asyncio.create_task(queue.get())
                done, _ = await asyncio.wait(
                    {getter, turn_task}, return_when=asyncio.FIRST_COMPLETED
                )
                if getter in done:
                    item = getter.result()
                    if item is not None:
                        kind, data = item
                        if kind == "delta":
                            emitted.append(data)
                            yield _make_delta_event(data)
                        elif kind == "event":
                            event_name, payload = data
                            yield self._event(event_name, payload)
                    continue
                getter.cancel()
                # The turn finished; drain any deltas/events queued a beat earlier.
                while not queue.empty():
                    item = queue.get_nowait()
                    if item is not None:
                        kind, data = item
                        if kind == "delta":
                            emitted.append(data)
                            yield _make_delta_event(data)
                        elif kind == "event":
                            event_name, payload = data
                            yield self._event(event_name, payload)
                break
            result = await turn_task
            # Guarantee full display text even if a provider finished without
            # streaming (or emitted a different final polish than its deltas).
            full_text = result.value.displayText or ""
            streamed_so_far = "".join(emitted)
            if not streamed_so_far and full_text:
                # Provider emitted no deltas at all during execution; yield full text once
                yield _make_delta_event(full_text)
            elif streamed_so_far and full_text:
                if full_text.startswith(streamed_so_far):
                    remainder = full_text[len(streamed_so_far):]
                    if remainder:
                        yield _make_delta_event(remainder)
                elif full_text.strip().startswith(streamed_so_far.strip()):
                    s_stripped = streamed_so_far.strip()
                    idx = full_text.find(s_stripped)
                    if idx != -1:
                        remainder = full_text[idx + len(s_stripped):]
                        if remainder:
                            yield _make_delta_event(remainder)
                else:
                    import os
                    common = os.path.commonprefix([full_text, streamed_so_far])
                    # Only emit remainder if common prefix covers >= 80% of streamed_so_far
                    if len(common) >= int(len(streamed_so_far) * 0.8):
                        remainder = full_text[len(common):]
                        if remainder:
                            yield _make_delta_event(remainder)
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
            if tool_req.toolName in {"image_search", "web_search"} and isinstance(tool_req.parameters, dict):
                # Whatever planned this call, the vendor gets a subject rather
                # than the sentence he typed, and the card shows the same thing.
                from hinaa_api.media.search_intelligence import (
                    compiled_image_query_parameters,
                    compiled_web_query_parameters,
                )

                compile_query = (
                    compiled_image_query_parameters
                    if tool_req.toolName == "image_search"
                    else compiled_web_query_parameters
                )
                tool_req.parameters = compile_query(tool_req.parameters)
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


    def _log_prompt_meta(
        self, session_id: str, fingerprint: str, mode: str, *, manifest_id: str | None = None
    ) -> None:
        # B2.1 §7: every model invocation carries a context_manifest_id trace.
        # A missing manifest_id on a production turn is a selection-bypass bug.
        logger.info(
            "prompt_assembled",
            extra={
                "session_id": session_id,
                "prompt_version": PROMPT_VERSION,
                "fingerprint": fingerprint,
                "interaction_mode": mode,
                "context_manifest_id": manifest_id,
            },
        )

    @staticmethod
    def _event(event_type: str, payload: dict[str, object]) -> bytes:
        return (json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n").encode()
