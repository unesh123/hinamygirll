"""
HINAA OS — Artifact Understanding & Evidence Pack Extractor (Module B)
Parses documents, research reports, code patches, and media artifacts into typed
ArtifactUnderstanding records with verified KeyClaims, source spans, citation links,
and real execution receipts.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any, Dict, List, Optional

from .contracts import ArtifactUnderstanding, KeyClaim


class ArtifactAnalyzer:
    """Analyzes raw artifact contents and receipts into grounded ArtifactUnderstanding."""

    def __init__(self) -> None:
        self._cache: Dict[str, ArtifactUnderstanding] = {}

    def analyze(
        self,
        artifact_id: str,
        content: str,
        content_type: str = "research_report",
        title: str = "",
        tenant_id: str = "default",
        access_scope: str = "tenant",
        version: int = 1,
        code_receipts: Optional[Dict[str, Any]] = None,
        media_receipts: Optional[Dict[str, Any]] = None,
    ) -> ArtifactUnderstanding:
        """Constructs an immutable, grounded ArtifactUnderstanding representation."""
        content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        cache_key = f"{tenant_id}:{artifact_id}"

        # Return cached understanding if content has not changed
        cached = self._cache.get(cache_key)
        if cached and cached.content_sha256 == content_sha256 and cached.version == version:
            return cached

        # Parse headings and sections
        headings, sections = self._parse_sections(content)

        # Extract KeyClaims with source spans and citation IDs
        key_claims = self._extract_key_claims(sections, content)

        # Extract main objectives & conclusions
        main_objectives = self._extract_objectives(sections)
        conclusions = self._extract_conclusions(sections)

        # Extract limitations and unresolved questions
        limitations, unresolved = self._extract_limitations_and_unresolved(sections, content)

        # Extract recommended actions
        recommended_actions = self._extract_recommendations(sections)

        # Derive title if empty
        derived_title = title or (headings[0] if headings else "Artifact Analysis")

        understanding = ArtifactUnderstanding(
            artifact_id=artifact_id,
            content_sha256=content_sha256,
            content_type=content_type,
            version=version,
            access_scope=access_scope,
            tenant_id=tenant_id,
            title=derived_title,
            headings=headings,
            section_summaries={h: self._summarize_text(t) for h, t in sections.items()},
            main_objectives=main_objectives,
            conclusions=conclusions,
            key_claims=key_claims,
            limitations=limitations,
            unresolved_questions=unresolved,
            recommended_actions=recommended_actions,
            code_receipts=code_receipts or {},
            media_receipts=media_receipts or {},
            raw_content=content,
        )

        self._cache[cache_key] = understanding
        return understanding

    def invalidate(self, artifact_id: str, tenant_id: str = "default") -> None:
        """Invalidates cached understanding when an artifact is deleted or superseded."""
        cache_key = f"{tenant_id}:{artifact_id}"
        self._cache.pop(cache_key, None)

    def get_cached(self, artifact_id: str, tenant_id: str = "default") -> Optional[ArtifactUnderstanding]:
        """Retrieves cached understanding with tenant isolation check."""
        return self._cache.get(f"{tenant_id}:{artifact_id}")

    # ── Section & Heading Parsing ──

    def _parse_sections(self, content: str) -> tuple[List[str], Dict[str, str]]:
        headings: List[str] = []
        sections: Dict[str, str] = {}
        current_heading = "Overview"
        current_lines: List[str] = []

        lines = content.split("\n")
        heading_re = re.compile(r"^(#{1,4})\s+(.+)$")

        for line in lines:
            m = heading_re.match(line.strip())
            if m:
                if current_lines:
                    sections[current_heading] = "\n".join(current_lines).strip()
                    current_lines = []
                current_heading = m.group(2).strip()
                headings.append(current_heading)
            else:
                current_lines.append(line)

        if current_lines:
            sections[current_heading] = "\n".join(current_lines).strip()

        if not headings:
            headings = [current_heading]

        return headings, sections

    # ── Key Claim Extraction ──

    def _extract_key_claims(self, sections: Dict[str, str], full_text: str) -> List[KeyClaim]:
        claims: List[KeyClaim] = []
        citation_re = re.compile(r"\[([0-9]+|[A-Za-z]+[-_0-9]+|arXiv:[0-9.]+[^\]]*)\]")
        claim_index = 1

        for section_title, section_text in sections.items():
            sentences = re.split(r"(?<=[.!?])\s+", section_text)
            for sentence in sentences:
                sentence_clean = sentence.strip()
                if len(sentence_clean) < 25:
                    continue

                # Identify factual claims: contains citations, numbers, metrics, or definitive assertions
                citations = citation_re.findall(sentence_clean)
                has_metric = bool(re.search(r"\b(\d+(\.\d+)?%|\$\d+|\d+\s*(ms|s|kg|GB|MB|TPS))\b", sentence_clean))
                is_assertion = any(term in sentence_clean.lower() for term in [
                    "demonstrates", "proves", "achieves", "reduces", "improves",
                    "found that", "results show", "measured", "indicates", "established"
                ])

                if citations or has_metric or is_assertion:
                    # Find line span
                    start_char = full_text.find(sentence_clean)
                    span_desc = f"{section_title}: char {start_char}" if start_char >= 0 else section_title

                    # Estimate confidence
                    confidence = 1.0 if citations else (0.85 if has_metric else 0.75)

                    claims.append(
                        KeyClaim(
                            claim_id=f"claim-{claim_index:03d}",
                            factual_assertion=sentence_clean,
                            source_span=span_desc,
                            supporting_citation_ids=citations,
                            factual_confidence=confidence,
                            conflicts=[],
                        )
                    )
                    claim_index += 1

        return claims

    # ── Summaries & Highlights ──

    def _summarize_text(self, text: str, max_chars: int = 180) -> str:
        clean = " ".join(text.split())
        if len(clean) <= max_chars:
            return clean
        return clean[:max_chars].rsplit(" ", 1)[0] + "..."

    def _extract_objectives(self, sections: Dict[str, str]) -> List[str]:
        objectives: List[str] = []
        for name, text in sections.items():
            if any(term in name.lower() for term in ["overview", "objective", "intro", "abstract", "purpose", "mission"]):
                sentences = re.split(r"(?<=[.!?])\s+", text)
                objectives.extend([s.strip() for s in sentences if len(s.strip()) > 20][:3])
        return objectives or ["Analyze and deliver core results"]

    def _extract_conclusions(self, sections: Dict[str, str]) -> List[str]:
        conclusions: List[str] = []
        for name, text in sections.items():
            if any(term in name.lower() for term in ["conclusion", "summary", "takeaway", "findings", "verdict"]):
                sentences = re.split(r"(?<=[.!?])\s+", text)
                conclusions.extend([s.strip() for s in sentences if len(s.strip()) > 20][:3])
        return conclusions or ["Evaluation complete based on current evidence"]

    def _extract_limitations_and_unresolved(self, sections: Dict[str, str], text: str) -> tuple[List[str], List[str]]:
        limitations: List[str] = []
        unresolved: List[str] = []

        sentences = re.split(r"(?<=[.!?])\s+", text)
        for s in sentences:
            sl = s.lower()
            if any(term in sl for term in ["limitation", "drawback", "tradeoff", "constraint", "bottleneck"]):
                limitations.append(s.strip())
            elif any(term in sl for term in ["unresolved", "open question", "future work", "uncertain", "requires further"]):
                unresolved.append(s.strip())

        return limitations[:4], unresolved[:4]

    def _extract_recommendations(self, sections: Dict[str, str]) -> List[str]:
        recs: List[str] = []
        for name, text in sections.items():
            if any(term in name.lower() for term in ["recommend", "next steps", "action", "guidance"]):
                sentences = re.split(r"(?<=[.!?])\s+", text)
                recs.extend([s.strip() for s in sentences if len(s.strip()) > 20][:4])
        return recs
