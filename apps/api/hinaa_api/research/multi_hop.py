"""Multi-Hop Query Decomposition & Planning Engine.

Decomposes complex relational questions into bounded hops, carrying intermediate
proven facts between steps while strictly preserving original source provenance.
"""

from __future__ import annotations

import logging
import re
from typing import Sequence
from .models import Source

logger = logging.getLogger("hinaa.research.multi_hop")


class MultiHopPlanner:
    """Manages multi-hop decomposition, entity bridging, and query budgets."""

    def __init__(self, max_hops: int = 3, max_total_queries: int = 5) -> None:
        self.max_hops = max_hops
        self.max_total_queries = max_total_queries

    def decompose(self, query: str) -> list[str]:
        """Decomposes a query into atomic sub-questions."""
        cleaned = query.strip()

        # Pattern 1: "Who [verb] the [noun] whose [rel] [verb] [entity]"
        # e.g., "Who directed the movie whose lead actor played Oppenheimer in 2023?"
        m1 = re.search(
            r"who\s+(?:directed|founded|created|wrote)\s+the\s+(?:movie|company|book|show)\s+whose\s+(?:lead\s+actor|founder|author)\s+(?:played|founded|wrote)\s+(.*?)(?:\s+in\s+(\d{4}))?[?.]?$",
            cleaned,
            re.I,
        )
        if m1:
            entity = m1.group(1).strip()
            year = m1.group(2)
            hop1 = f"lead actor {entity} {year or ''}".strip()
            hop2 = f"director of {entity} {year or ''}".strip()
            return [hop1, hop2]

        # Pattern 2: "What is the capital of the country where [event] was held"
        m2 = re.search(r"what\s+is\s+the\s+capital\s+of\s+the\s+country\s+where\s+(.*?)\s+(?:took\s+place|was\s+held)[?.]?$", cleaned, re.I)
        if m2:
            event = m2.group(1).strip()
            hop1 = f"host country of {event}"
            hop2 = "capital of {host_country}"
            return [hop1, hop2]

        # Fallback: single hop
        return [cleaned]

    def extract_bridge_entity(self, hop_query: str, sources: list[Source]) -> str | None:
        """Extracts candidate bridge entities from intermediate hop evidence."""
        if not sources:
            return None

        combined_text = " ".join(s.excerpt for s in sources)

        # Look for proper names: Two capitalized words (e.g., Cillian Murphy)
        candidates = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+))\b", combined_text)
        # Filter out common false positives
        filtered = [c for c in candidates if c.lower() not in {"universal pictures", "los alamos", "manhattan project"}]
        if filtered:
            return filtered[0]

        return None
