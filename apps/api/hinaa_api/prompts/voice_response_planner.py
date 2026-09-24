"""Voice Response Planner — Semantic intent classification and quality voice summaries (P0.13 / B2.1 §9–§10).

Target semantic intents:
1. SHORT_FULL — concise turns; speaks display text verbatim or model's own natural spoken text.
2. QUESTION — clarification or inquiry to the user; never overwritten with summary.
3. EXECUTIVE_SUMMARY — long document/report; speaks substantive core accomplishment/finding.
4. PROGRESS_UPDATE — long-running activity in flight.
5. ERROR — safe, graceful recovery explanation.
6. COMPLETION — tool or structured task completed.
7. ARTIFACT_READY — document/code artifact generated.

Supports duration estimation and duration preferences:
- brief: 5–15s spoken duration
- normal: 10–25s spoken duration
- detailed: 30–60s spoken duration
"""

from __future__ import annotations

import re
from enum import Enum
from typing import NamedTuple

from hinaa_api.prompts.performance import extract_executive_voice_summary


class VoiceIntent(str, Enum):
    """Semantic voice response targets (directive §9)."""

    SHORT_FULL = "SHORT_FULL"
    QUESTION = "QUESTION"
    EXECUTIVE_SUMMARY = "EXECUTIVE_SUMMARY"
    PROGRESS_UPDATE = "PROGRESS_UPDATE"
    ERROR = "ERROR"
    COMPLETION = "COMPLETION"
    ARTIFACT_READY = "ARTIFACT_READY"


class VoicePlanResult(NamedTuple):
    intent: VoiceIntent
    spoken_text: str
    target_duration_seconds: float = 0.0
    estimated_duration_seconds: float = 0.0


_BRIEF_PREF_RE = re.compile(
    r"\b(?:quick(?:ly)?|brief(?:ly)?|short(?:er)?\s+(?:summary|voice|version)|in\s+short|keep\s+it\s+short|quick\s+version)\b",
    re.IGNORECASE,
)
_DETAILED_PREF_RE = re.compile(
    r"\b(?:detailed|explain\s+aloud|tell\s+me\s+everything|full\s+(?:summary|explanation)|deep\s+dive\s+aloud|read\s+it\s+all)\b",
    re.IGNORECASE,
)


def infer_voice_preference(user_text: str) -> str:
    """Infer voice duration preference ('brief', 'normal', 'detailed') from user text."""
    if not user_text:
        return "normal"
    if _BRIEF_PREF_RE.search(user_text):
        return "brief"
    if _DETAILED_PREF_RE.search(user_text):
        return "detailed"
    return "normal"


def estimate_speech_duration(text: str, language: str = "en-US", pace: float = 1.0) -> float:
    """Estimate speech duration in seconds based on language, words/characters, and pace."""
    if not text or not text.strip():
        return 0.0
    clean = re.sub(r"[#*_`~[\]()|]", " ", text)
    effective_pace = max(0.2, min(pace or 1.0, 3.0))
    has_devanagari_or_cjk = bool(re.search(r"[\u0900-\u097F\u4E00-\u9FFF\u3040-\u30FF]", clean))
    if has_devanagari_or_cjk:
        chars = len(clean.replace(" ", ""))
        return round(max(0.5, (chars / 10.0) / effective_pace), 2)
    else:
        words = len(clean.split())
        return round(max(0.5, (words / 2.5) / effective_pace), 2)


def _truncate_at_clause_boundary(text: str, limit: int = 450) -> str:
    """Trim text at a natural clause or word boundary without cutting mid-thought."""
    if len(text) <= limit:
        return text
    window = text[:limit]
    for sep in (". ", "! ", "? ", "; ", " — ", ", "):
        idx = window.rfind(sep)
        if idx >= int(limit * 0.45):
            cut = window[:idx].rstrip(" ,;—")
            if not re.search(r"[.!?\u0964\u0965]$", cut):
                cut += "."
            return cut
    # Fallback to last space
    last_space = window.rfind(" ")
    if last_space != -1:
        cut = window[:last_space].rstrip(" ,;—")
        if not re.search(r"[.!?\u0964\u0965]$", cut):
            cut += "."
        return cut
    return window


class VoiceResponsePlanner:
    """Plans concise, substantive spoken voice responses respecting semantic quality and target durations."""

    def __init__(
        self,
        *,
        target_chars: int = 450,
        max_chars: int = 700,
    ) -> None:
        self.target_chars = target_chars
        self.max_chars = max_chars

    def plan(
        self,
        display_text: str,
        spoken_text: str,
        *,
        has_artifact: bool = False,
        has_pdf: bool = False,
        has_image: bool = False,
        has_error: bool = False,
        is_progress: bool = False,
        artifact_title: str | None = None,
        user_preference: str | None = None,
        user_text: str = "",
        language: str = "en-US",
        pace: float = 1.0,
    ) -> VoicePlanResult:
        display = (display_text or "").strip()
        spoken = (spoken_text or "").strip()

        # Resolve duration preference
        pref = user_preference or infer_voice_preference(user_text)
        if pref == "brief":
            effective_target_chars = min(self.target_chars, 220)
            effective_max_chars = min(self.max_chars, 320)
            target_duration = 10.0  # 5–15s
        elif pref == "detailed":
            effective_target_chars = max(self.target_chars, 600)
            effective_max_chars = max(self.max_chars, 900)
            target_duration = 45.0  # 30–60s
        else:
            effective_target_chars = self.target_chars
            effective_max_chars = self.max_chars
            target_duration = 18.0  # 10–25s

        # 1. Error path
        if has_error:
            if spoken and len(spoken) <= effective_max_chars and re.search(r"[.!?\u0964\u0965]", spoken):
                final = spoken
            else:
                final = "Something went wrong on my side — give me another try? 💜"
            return VoicePlanResult(
                VoiceIntent.ERROR,
                final,
                target_duration_seconds=5.0,
                estimated_duration_seconds=estimate_speech_duration(final, language, pace),
            )

        # 2. Artifact path
        if has_artifact:
            title = artifact_title or "your document"
            final = f"I've created {title} for you! You can view and edit it right here. ✨"
            return VoicePlanResult(
                VoiceIntent.ARTIFACT_READY,
                final,
                target_duration_seconds=6.0,
                estimated_duration_seconds=estimate_speech_duration(final, language, pace),
            )

        # 3. PDF generation
        if has_pdf:
            final = "I've generated your PDF! You can download it right below. ✨"
            return VoicePlanResult(
                VoiceIntent.COMPLETION,
                final,
                target_duration_seconds=5.0,
                estimated_duration_seconds=estimate_speech_duration(final, language, pace),
            )

        # 4. Image generation
        if has_image:
            final = "Here are the images you requested! ✨"
            return VoicePlanResult(
                VoiceIntent.COMPLETION,
                final,
                target_duration_seconds=4.0,
                estimated_duration_seconds=estimate_speech_duration(final, language, pace),
            )

        # 5. Progress update
        if is_progress:
            if spoken and len(spoken) <= 200:
                final = spoken
            else:
                final = "Working on it — I'll have it ready shortly! ✨"
            return VoicePlanResult(
                VoiceIntent.PROGRESS_UPDATE,
                final,
                target_duration_seconds=4.0,
                estimated_duration_seconds=estimate_speech_duration(final, language, pace),
            )

        # 6. Question: User is being asked for input
        if spoken.endswith("?") or (not spoken and display.rstrip().endswith("?")):
            question = spoken or display
            if len(question) <= effective_max_chars:
                final = question
            else:
                final = _truncate_at_clause_boundary(question, effective_max_chars)
            return VoicePlanResult(
                VoiceIntent.QUESTION,
                final,
                target_duration_seconds=7.0,
                estimated_duration_seconds=estimate_speech_duration(final, language, pace),
            )

        # 7. Short conversational response (< 600 chars display)
        if len(display) <= 600:
            candidate = spoken or display
            if len(candidate) <= effective_max_chars and re.search(r"[.!?:\u0964\u0965]\s*$", candidate.rstrip()):
                final = candidate
            elif len(display) <= effective_max_chars:
                final = display
            else:
                distilled = extract_executive_voice_summary(display, limit=effective_target_chars)
                final = distilled or "I've put the full breakdown in chat for you! ✨"

            return VoicePlanResult(
                VoiceIntent.SHORT_FULL,
                final,
                target_duration_seconds=min(15.0, max(5.0, target_duration)),
                estimated_duration_seconds=estimate_speech_duration(final, language, pace),
            )

        # 8. Long document: Executive summary answering:
        # What did Hina accomplish? What is the main result?
        clean_spoken = spoken.strip()
        is_substantive_spoken = (
            len(clean_spoken) >= 40
            and len(clean_spoken) <= effective_max_chars
            and bool(re.search(r"[.!?:\u0964\u0965💜✨🌟🌸💖]\s*$", clean_spoken))
            and not any(marker in clean_spoken for marker in ("```", "\n", "•", "|", "###", "##"))
            and not clean_spoken.lower().startswith("here is your")
            and not clean_spoken.lower().startswith("i have generated")
        )
        if is_substantive_spoken:
            return VoicePlanResult(
                VoiceIntent.EXECUTIVE_SUMMARY,
                clean_spoken,
                target_duration_seconds=target_duration,
                estimated_duration_seconds=estimate_speech_duration(clean_spoken, language, pace),
            )

        summary = extract_executive_voice_summary(display, limit=effective_target_chars)
        if not summary:
            summary = extract_executive_voice_summary(spoken, limit=effective_target_chars)
        if not summary:
            summary = _truncate_at_clause_boundary(spoken or display, effective_target_chars)

        # Ensure sentence completion
        if summary and not re.search(r"[.!?:\u0964\u0965]\s*$", summary.rstrip()):
            summary = _truncate_at_clause_boundary(summary, effective_target_chars)

        if pref == "brief":
            final_spoken = summary
        else:
            final_spoken = f"{summary} The full document is in chat for you! ✨"
            if len(final_spoken) > effective_max_chars:
                final_spoken = summary

        return VoicePlanResult(
            VoiceIntent.EXECUTIVE_SUMMARY,
            final_spoken,
            target_duration_seconds=target_duration,
            estimated_duration_seconds=estimate_speech_duration(final_spoken, language, pace),
        )