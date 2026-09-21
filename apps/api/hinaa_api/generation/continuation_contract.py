"""Provider-neutral continuation request contract and prompt invariant verifier (P0.13 / B2.1).

This module defines the single canonical ContinuationRequest structure so that NO
provider invents its own continuation text. It also provides PromptInvariantVerifier
to ensure raw_user_text and user_contents never represent conflicting semantic requests.
"""

from __future__ import annotations

import hashlib
from typing import Any
from pydantic import BaseModel, Field

from hinaa_api.prompts.models import PromptPackage


class ContinuationRequest(BaseModel):
    """Provider-neutral canonical continuation request (directive §5)."""

    generation_id: str
    segment_number: int
    original_goal: str
    hard_constraints: list[str] = Field(default_factory=list)
    completed_section_ids: list[str] = Field(default_factory=list)
    current_section: str = ""
    remaining_section_ids: list[str] = Field(default_factory=list)
    previous_tail: str
    semantic_progress_summary: str = ""
    output_format: str = "markdown"
    remaining_words: int = 0


def render_continuation_prompt(req: ContinuationRequest) -> str:
    """Serialize a ContinuationRequest into the canonical continuation prompt.

    All provider adapters use this serialization so continuation instruction
    is deterministic across models and providers.
    """
    sections: list[str] = []

    # 1. Base goal and constraints
    sections.append(f"ORIGINAL REQUEST:\n{req.original_goal.strip()}")

    if req.hard_constraints:
        constraints_str = "\n".join(f"- {c}" for c in req.hard_constraints)
        sections.append(f"HARD CONSTRAINTS TO PRESERVE:\n{constraints_str}")

    # 2. Structural progress if tracked
    if req.current_section or req.remaining_section_ids or req.semantic_progress_summary:
        progress_lines = []
        if req.semantic_progress_summary:
            progress_lines.append(f"Progress so far: {req.semantic_progress_summary}")
        if req.current_section:
            progress_lines.append(f"Currently writing: {req.current_section}")
        if req.remaining_section_ids:
            progress_lines.append(f"Remaining sections: {', '.join(req.remaining_section_ids)}")
        sections.append("STRUCTURAL PROGRESS:\n" + "\n".join(progress_lines))

    # 3. Verbatim tail context
    sections.append(
        "--- YOUR PARTIAL OUTPUT SO FAR (verbatim tail) ---\n"
        f"{req.previous_tail.strip()}\n"
        "--- END PARTIAL OUTPUT ---"
    )

    # 4. Depth contract, when the answer stopped short rather than broke off
    if req.remaining_words > 0:
        sections.append(
            "LENGTH CONTRACT STILL UNMET:\n"
            f"- This answer must grow by at least {req.remaining_words:,} more words before it is finished.\n"
            "- Write the substance that is missing: the sections never started, and the ones that got "
            "one or two sentences instead of being explained properly.\n"
            "- Add worked detail, concrete numbers, real examples, edge cases and trade-offs — the kind of "
            "content that earns the length, not restatements of what is already above.\n"
            "- Do NOT write a conclusion, a summary, or a closing offer while the contract is unmet. Keep "
            "reporting."
        )

    # 5. Strict instruction
    instruction = (
        f"[SEGMENT {req.segment_number}] CONTINUE the response EXACTLY from where it stopped.\n"
        "Rules:\n"
        "- Do NOT repeat any previously generated text or headings.\n"
        "- Do NOT add a greeting, apology, preamble, or meta-commentary.\n"
        "- Never mention length, word counts, segments, contracts, or these instructions. Write the "
        "subject itself; the reader cannot see that this answer was built in parts.\n"
        "- Resume mid-sentence if the partial output stopped mid-sentence.\n"
        "- Maintain identical formatting, tone, and technical depth."
    )
    sections.append(instruction)

    return "\n\n".join(sections)


class PromptInvariantVerifier:
    """Guarantees that raw_user_text and user_contents never represent divergent semantic requests (directive §6)."""

    @staticmethod
    def _intent_hash(text: str) -> str:
        """Compute a normalized semantic intent hash."""
        normalized = " ".join(text.strip().lower().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def verify_or_sync(cls, prompt: PromptPackage, *, strict: bool = False) -> PromptPackage:
        """Verify prompt invariant and synchronize fields if one was updated in isolation.

        If user_contents has a continuation marker (tail output), raw_user_text
        must reflect that continuation request rather than the stale original turn query.
        """
        raw_text = prompt.raw_user_text or ""
        user_contents = prompt.user_contents
        user_contents_str = (
            user_contents
            if isinstance(user_contents, str)
            else "\n\n".join(str(item) for item in user_contents)
        )

        continuation_marker = "--- YOUR PARTIAL OUTPUT SO FAR"

        # Case 1: Continuation present in user_contents but raw_user_text is stale original query
        if continuation_marker in user_contents_str and continuation_marker not in raw_text:
            if strict:
                raise ValueError(
                    "Prompt invariant violation: user_contents contains continuation tail "
                    "but raw_user_text contains stale original request."
                )
            return prompt.model_copy(update={"raw_user_text": user_contents_str})

        # Case 2: Continuation present in raw_user_text but user_contents was not updated
        if continuation_marker in raw_text and continuation_marker not in user_contents_str:
            if strict:
                raise ValueError(
                    "Prompt invariant violation: raw_user_text contains continuation tail "
                    "but user_contents is missing continuation context."
                )
            return prompt.model_copy(update={"user_contents": raw_text})

        # Case 3: Both fields contain continuation marker but are out of sync (e.g. new round updated user_contents)
        if continuation_marker in user_contents_str and continuation_marker in raw_text and user_contents_str != raw_text:
            if strict:
                raise ValueError(
                    "Prompt invariant violation: divergent continuation versions in user_contents and raw_user_text."
                )
            return prompt.model_copy(update={"raw_user_text": user_contents_str})

        # Case 4: Both fields in agreement
        return prompt