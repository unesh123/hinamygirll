from __future__ import annotations

import difflib
import re
from typing import Any


class ResponseIntelligenceController:
    """Enterprise response intelligence and deduplication controller.

    Prevents verbatim input echoing, removes redundant block repetitions,
    detects continuation/critique prompts and deduplicates previous answers,
    enforces code diff presentation rules for workspace files,
    formats structured document artifacts into summary cards,
    and routes response depth.
    """

    @staticmethod
    def detect_input_echo(user_text: str, assistant_text: str, threshold: float = 0.40) -> bool:
        """Detect if assistant output contains excessive verbatim echo of user prompt.

        Ignores brief explicit quoting ("As you asked...", "Quote:").
        Returns True if >threshold of user_text is copied into assistant_text.
        """
        user_clean = user_text.strip()
        asst_clean = assistant_text.strip()
        if len(user_clean) < 40 or not asst_clean:
            return False

        # If user explicitly asked to repeat or echo, allow it
        lower_user = user_clean.lower()
        if any(w in lower_user for w in ("repeat after me", "echo this", "verbatim", "say exactly", "quote this")):
            return False

        # Check direct substring containment of large user inputs
        if len(user_clean) > 80 and user_clean in asst_clean:
            return True

        # Check sequence similarity ratio
        matcher = difflib.SequenceMatcher(None, user_clean, asst_clean[: len(user_clean) * 2])
        longest_match = matcher.find_longest_match(0, len(user_clean), 0, min(len(asst_clean), len(user_clean) * 2))
        if longest_match.size > 0 and (longest_match.size / len(user_clean)) >= threshold and longest_match.size > 50:
            return True

        return False

    @staticmethod
    def strip_input_echo(user_text: str, assistant_text: str) -> str:
        """Strip verbatim user prompt echoing from the beginning of assistant response."""
        user_clean = user_text.strip()
        asst_clean = assistant_text.strip()
        if not asst_clean or len(user_clean) < 30:
            return assistant_text

        # 1. Strip common prefixes like "You said: <user_text>" or "Regarding: <user_text>"
        preambles = [
            r"^(?:You said|You asked|Regarding|In response to|Prompt|Query):\s*[\"']?.*[\"']?\s*\n+",
            r"^(?:Based on your request|According to your prompt):\s*[\"']?.*[\"']?\s*\n+",
        ]
        for pattern in preambles:
            m = re.match(pattern, asst_clean, flags=re.IGNORECASE)
            if m:
                asst_clean = asst_clean[m.end():].lstrip()

        # 2. If assistant starts with exact user_text block, strip it
        if asst_clean.startswith(user_clean):
            asst_clean = asst_clean[len(user_clean):].lstrip(" :\n-")

        return asst_clean or assistant_text

    @staticmethod
    def deduplicate_blocks(text: str) -> str:
        """Remove consecutive duplicate or near-identical paragraphs and blocks."""
        if not text:
            return ""

        # Split on double newlines (blocks/paragraphs)
        blocks = re.split(r"\n{2,}", text)
        cleaned_blocks: list[str] = []
        seen_normalized: list[str] = []

        for block in blocks:
            raw = block.strip()
            if not raw:
                continue
            # Normalize whitespace and case for comparison
            normalized = re.sub(r"\s+", " ", raw.lower())

            # Check if this block is identical or >95% similar to the immediate previous block
            is_dup = False
            if seen_normalized:
                prev = seen_normalized[-1]
                if normalized == prev:
                    is_dup = True
                elif len(normalized) > 40 and len(prev) > 40:
                    sim = difflib.SequenceMatcher(None, normalized, prev).ratio()
                    if sim > 0.95:
                        is_dup = True

            if not is_dup:
                cleaned_blocks.append(raw)
                seen_normalized.append(normalized)

        return "\n\n".join(cleaned_blocks)

    @staticmethod
    def deduplicate_previous_answer(
        previous_output: str,
        current_output: str,
        user_query: str,
        overlap_threshold: float = 0.50,
    ) -> str:
        """Deduplicate previous answer when user asks a continuation or improvement query."""
        prev = previous_output.strip()
        curr = current_output.strip()
        if not prev or not curr or len(prev) < 50:
            return current_output

        q_lower = user_query.strip().lower()
        is_continuation = any(
            k in q_lower
            for k in (
                "continue",
                "what next",
                "what's next",
                "go on",
                "proceed",
                "keep going",
                "and then",
                "more",
                "next step",
                "improve it",
                "expand",
            )
        )

        if not is_continuation:
            return current_output

        # If current output starts with previous output, strip the repeated prefix
        if curr.startswith(prev):
            remainder = curr[len(prev):].lstrip("\n -:")
            if remainder:
                return remainder

        # Check block-level overlap from the beginning of current_output
        prev_blocks = [b.strip() for b in re.split(r"\n{2,}", prev) if b.strip()]
        curr_blocks = [b.strip() for b in re.split(r"\n{2,}", curr) if b.strip()]

        # Find matching leading blocks
        matched_leading = 0
        for i in range(min(len(prev_blocks), len(curr_blocks))):
            p_norm = re.sub(r"\s+", " ", prev_blocks[i].lower())
            c_norm = re.sub(r"\s+", " ", curr_blocks[i].lower())
            if p_norm == c_norm or difflib.SequenceMatcher(None, p_norm, c_norm).ratio() > 0.90:
                matched_leading += 1
            else:
                break

        if matched_leading > 0 and matched_leading < len(curr_blocks):
            # If at least half of previous blocks were regurgitated at start, keep only the new blocks
            if (matched_leading / len(prev_blocks)) >= overlap_threshold:
                new_blocks = curr_blocks[matched_leading:]
                return "\n\n".join(new_blocks)

        return current_output

    @staticmethod
    def enforce_code_output_rule(output: str, written_files: list[str] | None = None) -> str:
        """Format code outputs to summarize repository modifications rather than echoing 500-line files."""
        if not written_files:
            return output

        # If files were written, ensure files are clearly summarized
        file_summary_lines = [f"- `{f}`" for f in written_files]
        summary_banner = "### Modified Workspace Files\n" + "\n".join(file_summary_lines)

        if any(f in output for f in written_files):
            return output

        return f"{output}\n\n{summary_banner}"

    @staticmethod
    def enforce_artifact_output_rule(output: str, artifacts: list[dict[str, Any]] | None = None) -> str:
        """Present document/presentation/sheet artifacts with summary and download card."""
        if not artifacts:
            return output

        cards: list[str] = []
        for art in artifacts:
            name = art.get("name", "Document")
            kind = art.get("kind", "artifact")
            path = art.get("path") or art.get("url", "#")
            summary = art.get("summary", "")
            cards.append(f"> [!NOTE]\n> **{name}** ({kind.upper()})\n> {summary}\n> [Open / Download Artifact]({path})")

        card_block = "\n\n".join(cards)
        return f"{output}\n\n{card_block}"

    @staticmethod
    def route_response_depth(query: str, mode: str | None = None) -> str:
        """Classify user query and mode into response depth tier: QUICK, NORMAL, DEEP, EXHAUSTIVE, ARTIFACT."""
        q = query.strip().lower()
        if mode == "artifact" or any(k in q for k in ("create a file", "generate a pdf", "create presentation", "generate doc")):
            return "ARTIFACT"

        # Exhaustive triggers
        exhaustive_triggers = (
            "full spec",
            "complete specification",
            "exhaustive",
            "in depth",
            "every detail",
            "all edge cases",
            "step-by-step implementation",
        )
        if any(t in q for t in exhaustive_triggers):
            return "EXHAUSTIVE"

        # Deep triggers
        deep_triggers = (
            "deep dive",
            "architectural breakdown",
            "explain thoroughly",
            "comprehensive analysis",
            "compare and contrast",
        )
        if any(t in q for t in deep_triggers) or mode in ("architect", "deep_research"):
            return "DEEP"

        # Quick triggers
        quick_triggers = (
            "quick",
            "briefly",
            "short answer",
            "tldr",
            "tl;dr",
            "one sentence",
            "in a nutshell",
            "yes or no",
        )
        if any(t in q for t in quick_triggers) or mode == "casual":
            return "QUICK"

        return "NORMAL"

    def process_plan(
        self,
        plan: Any,
        user_query: str,
        previous_output: str | None = None,
        written_files: list[str] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
    ) -> Any:
        """Apply full intelligence pipeline to an AssistantTurnPlan."""
        display = getattr(plan, "displayText", "") or ""
        if not display:
            return plan

        # 1. Deduplicate consecutive identical blocks
        display = self.deduplicate_blocks(display)

        # 2. Strip verbatim input echoes
        display = self.strip_input_echo(user_query, display)

        # 3. Deduplicate previous answers on continuation
        if previous_output:
            display = self.deduplicate_previous_answer(previous_output, display, user_query)

        # 4. Enforce code output rules
        if written_files:
            display = self.enforce_code_output_rule(display, written_files)

        # 5. Enforce artifact rules
        if artifacts:
            display = self.enforce_artifact_output_rule(display, artifacts)

        plan.displayText = display.strip()
        return plan
