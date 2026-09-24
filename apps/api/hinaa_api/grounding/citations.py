"""Grounded Citation Pipeline — Structured evidence attribution, deterministic citation rendering, and citation quality metrics.

Guarantees:
1. Citations like [1], [2] map deterministically to verified EvidenceSource objects.
2. The model cannot hallucinate URLs or fabricate bibliography sections — sources are rendered
   deterministically from structured retrieved evidence.
3. Hostile / prompt-injection snippets in retrieved sources are sanitized and treated strictly
   as passive data.
4. Quality metrics (CitationCorrectness, CitationCoverage, FabricatedCitationRate) are calculable.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence


# Regex to detect freeform LLM-generated sources/references sections at the end of text
_UNVERIFIED_SOURCES_SECTION_RE = re.compile(
    r"(?:\n\s*#{1,4}\s*(?:Sources|References|Sources & References|References & Sources|Citations|External Links)[\s\S]*$)",
    re.IGNORECASE,
)

# Regex to detect bracket citations in text: [1], [2], [SRC_1], [Source 1], [SRC_A], etc.
# Excludes markdown links like [Title](url) or image tags ![Alt](url)
_BRACKET_CITATION_RE = re.compile(
    r"(?<!\!)\[(?P<ref>\d{1,3}|SRC_[A-Za-z0-9_-]+|Source\s*\d{1,3})\](?!\()",
    re.IGNORECASE,
)

# Known prompt-injection patterns in untrusted source data (for classification only, NOT for destructive stripping)
_PROMPT_INJECTION_RE = re.compile(
    r"(?i)\b(?:(?:ignore|disregard)\s+(?:all\s+)?(?:previous\s+)?(?:instructions|rules|prompts)|system\s+prompt|you\s+are\s+now\s+DAN|jailbreak)\b"
)


def sanitize_transport_control_chars(text: str) -> str:
    """Non-destructive transport sanitization (P0.15 §5/§7).

    Strips NUL bytes and unprintable ASCII control characters (C0 control codes
    except \n, \r, \t). NEVER strips semantic words or attack phrases like
    'ignore previous instructions' or 'SYSTEM:'. Semantic text is preserved
    verbatim as passive data.
    """
    if not text:
        return ""
    # Strip NUL bytes and C0 control codes except newline, carriage return, and tab
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)


@dataclass
class ExternalEvidence:
    """Non-destructive envelope for untrusted external content (P0.15 §6)."""
    source_id: str
    raw_content: str
    source_metadata: dict[str, Any] = field(default_factory=dict)
    trust: str = "external_data"
    instruction_authority: str = "none"

    def to_envelope(self) -> str:
        safe_content = sanitize_transport_control_chars(self.raw_content)
        return (
            f'<external_evidence id="{self.source_id}" authority="{self.instruction_authority}">\n'
            f"{safe_content}\n"
            f"</external_evidence>"
        )


@dataclass(frozen=True)
class EvidenceSpan:
    """A specific passage or quote supporting a claim (P0.15 §15)."""
    source_id: str
    span_id: str
    text: str
    location: str = ""
    start_offset: int | None = None
    end_offset: int | None = None
    retrieved_at: str | None = None


@dataclass
class EvidenceSource:
    """A verified, structured evidence document or web source with stable identity (P0.15 §11)."""
    source_id: str
    title: str
    publisher: str = ""
    url: str = ""
    date: str | None = None
    published_year: int | None = None
    retrieved_at: str | None = None
    evidence_spans: list[EvidenceSpan] = field(default_factory=list)
    snippet: str = ""
    raw_source_content: str = ""
    normalized_display_content: str = ""
    provider_safe_data_content: str = ""
    reliability_score: float = 1.0
    is_stale: bool = False
    is_adversarial: bool = False

    def __post_init__(self) -> None:
        if not self.publisher and self.url:
            try:
                parsed = urllib.parse.urlparse(self.url)
                netloc = parsed.netloc.lower()
                if netloc.startswith("www."):
                    netloc = netloc[4:]
                self.publisher = netloc
            except Exception:
                self.publisher = "Web"
        elif not self.publisher:
            self.publisher = "Source"

        if not self.raw_source_content and self.snippet:
            self.raw_source_content = self.snippet
        if not self.provider_safe_data_content and self.raw_source_content:
            self.provider_safe_data_content = sanitize_transport_control_chars(self.raw_source_content)
        if not self.normalized_display_content and self.raw_source_content:
            self.normalized_display_content = sanitize_transport_control_chars(self.raw_source_content).strip()

        # Parse published year if available
        if not self.published_year and self.date:
            year_m = re.search(r"\b(19\d\d|20\d\d)\b", self.date)
            if year_m:
                self.published_year = int(year_m.group(1))

        # Check for adversarial content in raw text (tagging only, non-destructive)
        combined = f"{self.title} {self.raw_source_content}"
        if _PROMPT_INJECTION_RE.search(combined):
            self.is_adversarial = True

    def calculate_freshness_weight(self, query: str) -> float:
        """Query-aware freshness evaluation (P0.15 §18).

        If query asks for historical context (e.g. 'in 2018', 'history of'),
        historical sources are not penalized.
        """
        historical_intent = bool(re.search(r"\b(in\s+20\d\d|history|historical|past|timeline|originally|earlier)\b", query, re.I))
        if historical_intent:
            return 1.0
        return 0.5 if self.is_stale else 1.0

    def to_envelope(self) -> str:
        """Render source into non-destructive untrusted content envelope (P0.15 §16)."""
        safe_content = self.provider_safe_data_content or sanitize_transport_control_chars(self.raw_source_content)
        header = f"[{self.publisher}] {self.title}: " if self.publisher else f"{self.title}: "
        return (
            f'<external_evidence id="{self.source_id}" authority="none">\n'
            f"{header}{safe_content}\n"
            f"</external_evidence>"
        )


@dataclass
class ClaimAttribution:
    """Structured attribution linking a generated claim to evidence (P0.15 §12)."""
    claim_id: str
    text: str
    source_ids: list[str] = field(default_factory=list)
    evidence_span_ids: list[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class EvidenceConflict:
    """Explicit representation of contradictory credible sources (P0.15 §17)."""
    topic: str
    sources: list[str] = field(default_factory=list)
    disagreement: str = ""


@dataclass
class CitationMetrics:
    """Quality metrics for citation precision, coverage, and hallucination (P0.15 §16)."""
    citation_correctness: float = 1.0      # Overall correctness
    reference_validity: float = 1.0        # % of cited references resolving to valid declared sources
    claim_support_accuracy: float = 1.0    # % of claims where source content actually contains claim tokens
    citation_coverage: float = 1.0         # % of claims/paragraphs containing citations
    fabricated_citation_rate: float = 0.0  # % of citations pointing to non-existent sources
    source_freshness: float = 1.0
    source_authority: float = 1.0
    total_citations_found: int = 0
    valid_citations_count: int = 0
    fabricated_citations_count: int = 0


class CitationRenderer:
    """Authoritative renderer that replaces freeform bibliographies with structured citations (P0.15 §11–§14)."""

    def __init__(self, sources: Sequence[EvidenceSource] | None = None) -> None:
        self.sources = list(sources or [])

    @staticmethod
    def sanitize_untrusted_text(text: str) -> str:
        """Non-destructive sanitization of untrusted text (P0.15 §7)."""
        return sanitize_transport_control_chars(text)

    @staticmethod
    def strip_unverified_sources_section(text: str) -> str:
        """Strip any freeform sources/references markdown block generated by LLM."""
        if not text:
            return ""
        return _UNVERIFIED_SOURCES_SECTION_RE.sub("", text).rstrip()

    @staticmethod
    def extract_citation_refs(text: str) -> list[str]:
        """Extract all bracket citation references from text (e.g. ['1', '2', 'SRC_1', 'Source 1'])."""
        if not text:
            return []
        matches = _BRACKET_CITATION_RE.findall(text)
        return [m.strip() for m in matches if m.strip()]

    def deduplicate_sources(self, sources: Sequence[EvidenceSource]) -> list[EvidenceSource]:
        """Deduplicate sources by URL or normalized title."""
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        deduped: list[EvidenceSource] = []

        for s in sources:
            norm_url = s.url.strip().lower() if s.url else ""
            norm_title = re.sub(r"\W+", " ", s.title.strip().lower()).strip()

            if norm_url and norm_url in seen_urls:
                continue
            if norm_title and norm_title in seen_titles:
                continue

            if norm_url:
                seen_urls.add(norm_url)
            if norm_title:
                seen_titles.add(norm_title)
            deduped.append(s)

        return deduped

    def render(
        self,
        text: str,
        sources: Sequence[EvidenceSource] | None = None,
        *,
        append_sources: bool = True,
        remove_fabricated: bool = True,
        attributions: Sequence[ClaimAttribution] | None = None,
        query: str = "",
    ) -> tuple[str, list[EvidenceSource], CitationMetrics]:
        """Process response text and render verified citations and sources section.

        The renderer OWNS citation numbering (P0.15 §13). Any model-emitted source ID
        (e.g. [SRC_4], [Source 1], [1]) is remapped to sequential presentation order [1], [2]...
        Any unsupported numbers (e.g. [12] with no source) are rejected or stripped.

        Returns: (rendered_text, ordered_cited_sources, metrics)
        """
        raw_sources = list(sources) if sources is not None else self.sources
        unique_sources = self.deduplicate_sources(raw_sources)

        # Lookup tables for declared sources
        source_by_id: dict[str, EvidenceSource] = {}
        for s in unique_sources:
            source_by_id[str(s.source_id)] = s
            # also index normalized forms: "1", "SRC_1", "Source 1"
            clean_num = re.sub(r"(?i)^(?:SRC_|Source\s*)", "", str(s.source_id)).strip()
            source_by_id[clean_num] = s
            source_by_id[f"SRC_{clean_num}"] = s
            source_by_id[f"Source {clean_num}"] = s

        source_by_index: dict[int, EvidenceSource] = {
            i + 1: s for i, s in enumerate(unique_sources)
        }

        # Step 1: Strip model-invented bibliography block
        cleaned_body = self.strip_unverified_sources_section(text)

        # Step 2: Match all bracket citations in text
        # We find matches with their span locations to renumber deterministically
        matches = list(_BRACKET_CITATION_RE.finditer(cleaned_body))
        total_found = len(matches)

        # Build dynamic presentation numbering map: source_id -> presentation_index
        ordered_sources: list[EvidenceSource] = []
        source_to_presentation: dict[str, int] = {}
        valid_count = 0
        fabricated_count = 0
        supported_claims = 0

        # Replace map: (start, end) -> "[N]" or ""
        replacements: list[tuple[int, int, str]] = []

        for m in matches:
            ref_str = m.group("ref").strip()
            resolved_source: EvidenceSource | None = None

            # If pure digits, prefer 1-based index in unique_sources first, fallback to ID lookup
            if ref_str.isdigit():
                idx = int(ref_str)
                if idx in source_by_index:
                    resolved_source = source_by_index[idx]
                elif ref_str in source_by_id:
                    resolved_source = source_by_id[ref_str]
            elif ref_str in source_by_id:
                resolved_source = source_by_id[ref_str]

            if resolved_source is not None:
                valid_count += 1
                sid = str(resolved_source.source_id)
                if sid not in source_to_presentation:
                    ordered_sources.append(resolved_source)
                    source_to_presentation[sid] = len(ordered_sources)
                pres_idx = source_to_presentation[sid]
                replacements.append((m.start(), m.end(), f"[{pres_idx}]"))

                # Check claim support accuracy: does surrounding sentence share keywords with source?
                sentence_start = max(0, cleaned_body.rfind(".", 0, m.start()) + 1)
                sentence_text = cleaned_body[sentence_start:m.start()].lower()
                source_text = f"{resolved_source.title} {resolved_source.raw_source_content} {resolved_source.snippet}".lower()
                sentence_words = set(re.findall(r"\w{4,}", sentence_text))
                source_words = set(re.findall(r"\w{4,}", source_text))
                if sentence_words & source_words or not sentence_words:
                    supported_claims += 1
            else:
                fabricated_count += 1
                # Reject unsupported bracket citation
                replacements.append((m.start(), m.end(), "" if remove_fabricated else f"[{ref_str}]"))

        # Apply replacements in reverse order to preserve string indices
        rendered_body = cleaned_body
        for start, end, repl in reversed(replacements):
            rendered_body = rendered_body[:start] + repl + rendered_body[end:]

        # Clean up possible double spaces or empty brackets
        rendered_body = re.sub(r" +", " ", rendered_body)
        rendered_body = re.sub(r" \.", ".", rendered_body)

        # Compute metrics (P0.15 §16)
        ref_validity = (valid_count / total_found) if total_found > 0 else 1.0
        claim_accuracy = (supported_claims / valid_count) if valid_count > 0 else 1.0
        correctness = ref_validity
        fabricated_rate = (fabricated_count / total_found) if total_found > 0 else 0.0

        # Paragraph citation coverage
        paragraphs = [p.strip() for p in rendered_body.split("\n\n") if p.strip() and not p.startswith("#")]
        if paragraphs:
            cited_paragraphs = sum(1 for p in paragraphs if re.search(r"\[\d+\]", p))
            coverage = min(1.0, cited_paragraphs / len(paragraphs))
        else:
            coverage = 1.0

        # Query-aware freshness and authority
        sources_to_use = ordered_sources if ordered_sources else unique_sources
        if sources_to_use:
            freshness = sum(s.calculate_freshness_weight(query) for s in sources_to_use) / len(sources_to_use)
            authority = sum(s.reliability_score for s in sources_to_use) / len(sources_to_use)
        else:
            freshness = 1.0
            authority = 1.0

        metrics = CitationMetrics(
            citation_correctness=round(correctness, 3),
            reference_validity=round(ref_validity, 3),
            claim_support_accuracy=round(claim_accuracy, 3),
            citation_coverage=round(coverage, 3),
            fabricated_citation_rate=round(fabricated_rate, 3),
            source_freshness=round(freshness, 3),
            source_authority=round(authority, 3),
            total_citations_found=total_found,
            valid_citations_count=valid_count,
            fabricated_citations_count=fabricated_count,
        )

        if append_sources and sources_to_use:
            sources_block = self.render_sources_section(sources_to_use)
            final_text = f"{rendered_body.rstrip()}\n\n{sources_block}"
        else:
            final_text = rendered_body

        return final_text, sources_to_use, metrics

    def render_sources_section(self, sources: Sequence[EvidenceSource]) -> str:
        """Render deterministic Markdown Sources & References section from structured sources."""
        if not sources:
            return ""

        lines = ["### Sources & References"]
        for idx, s in enumerate(sources, 1):
            sanitized_title = self.sanitize_untrusted_text(s.title or "Untitled")
            pub = s.publisher or "Source"
            date_part = f" ({s.date})" if s.date else ""
            stale_note = " [Archived/Historical]" if s.is_stale else ""

            if s.url:
                lines.append(f"[{idx}] [{pub}]({s.url}) — {sanitized_title}{date_part}{stale_note}")
            else:
                lines.append(f"[{idx}] {pub} — {sanitized_title}{date_part}{stale_note}")

        return "\n".join(lines)
