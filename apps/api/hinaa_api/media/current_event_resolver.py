from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ResolvedCurrentEvent:
    event_name: str
    location: str
    canonical_subject: str
    specific_search_query: str
    temporal_anchor: str = "2026"
    alternate_queries: tuple[str, ...] = field(default_factory=tuple)
    evidence: tuple[str, ...] = field(default_factory=tuple)
    expected_entities: tuple[str, ...] = field(default_factory=tuple)
    negative_terms: tuple[str, ...] = (
        "anime", "manga", "cartoon", "booru", "drawing", "illustration",
        "waifu", "cosplay", "render", "3d model", "genshin", "sketch",
    )


# Curated real-time event signatures for known high-frequency regions & incidents
_EVENT_KNOWLEDGE_BASE: list[dict[str, Any]] = [
    {
        "location_pattern": r"\b(nepal|kathmandu|lalitpur|bhaktapur|pokhara|koshi)\b",
        "event_pattern": r"\b(incident|incidents|flood|floods|flooding|landslide|landslides|monsoon|rain|rains|disaster)\b",
        "event_name": "Monsoon Floods and Landslides",
        "location": "Kathmandu, Nepal",
        "canonical_subject": "Nepal Monsoon Floods & Landslides",
        "specific_search_query": "Nepal Kathmandu monsoon flood landslide damage rescue photos news 2026",
        "alternate_queries": (
            "Kathmandu valley flooding disaster aftermath news",
            "Nepal Bagmati river overflow emergency photos",
            "Nepal disaster rescue operations landslide photos",
        ),
        "expected_entities": ("Nepal", "Kathmandu", "Floods", "Landslide"),
    },
    {
        "location_pattern": r"\b(nepal|kathmandu)\b",
        "event_pattern": r"\b(plane|aircraft|crash|aviation|airport)\b",
        "event_name": "Kathmandu Aviation Incident",
        "location": "Kathmandu, Nepal",
        "canonical_subject": "Kathmandu Airport Aviation Incident",
        "specific_search_query": "Kathmandu airport aircraft incident emergency response news photos 2026",
        "alternate_queries": (
            "Nepal aviation accident site investigation pictures",
            "Tribhuvan airport emergency services photos news",
        ),
        "expected_entities": ("Kathmandu", "Nepal", "Aviation", "Airport"),
    },
    {
        "location_pattern": r"\b(japan|tokyo|noto|ishikawa|osaka|kyoto)\b",
        "event_pattern": r"\b(earthquake|quake|tremor|tsunami|seismic)\b",
        "event_name": "Japan Seismic Event",
        "location": "Tokyo, Japan",
        "canonical_subject": "Japan Earthquake & Emergency Response",
        "specific_search_query": "Japan Tokyo earthquake seismic damage rescue news photos 2026",
        "alternate_queries": (
            "Japan earthquake emergency response pictures news",
            "Tokyo seismic tremor structural inspection photos",
        ),
        "expected_entities": ("Japan", "Tokyo", "Earthquake"),
    },
    {
        "location_pattern": r"\b(usa|america|california|los\s+angeles|texas)\b",
        "event_pattern": r"\b(fire|wildfire|blaze|burn)\b",
        "event_name": "California Wildfire Emergency",
        "location": "California, USA",
        "canonical_subject": "California Wildfire Emergency Response",
        "specific_search_query": "California wildfire emergency containment evacuation news photos 2026",
        "alternate_queries": (
            "California firefighting operations smoke aerial pictures",
            "US wildfire emergency response crews photos news",
        ),
        "expected_entities": ("California", "Wildfire", "Fire"),
    },
]

_EVENT_ROOTS: list[tuple[str, str]] = [
    ("flood", r"\b(floods?|flooding)\b"),
    ("landslide", r"\b(landslides?)\b"),
    ("monsoon", r"\b(monsoons?)\b"),
    ("earthquake", r"\b(earthquakes?|quakes?|tremors?)\b"),
    ("wildfire", r"\b(wildfires?|fire|blazes?)\b"),
    ("storm", r"\b(storms?|cyclones?|typhoons?|hurricanes?)\b"),
    ("crash", r"\b(crash|aviation|plane|aircraft)\b"),
    ("disaster", r"\b(disasters?|crisis)\b"),
]


class CurrentEventResolver:
    """Discovers concrete real-world events from locations, incident markers, and live news headlines before query compilation.
    
    Prevents vague queries like 'Nepal Current Incident photos news' by resolving the specific
    event (e.g. 'Nepal Kathmandu monsoon flood landslide damage rescue photos news 2026') from live evidence.
    """

    @classmethod
    def resolve_event_from_evidence(
        cls,
        text: str,
        evidence_items: list[str] | list[dict[str, Any]],
        *,
        location: str | None = None,
    ) -> ResolvedCurrentEvent | None:
        """Synthesizes a concrete ResolvedCurrentEvent directly from live evidence (e.g. news headlines, snippets)."""
        if not evidence_items:
            return None

        headline_texts: list[str] = []
        for item in evidence_items:
            if isinstance(item, str):
                headline_texts.append(item)
            elif isinstance(item, dict):
                title = item.get("title") or item.get("snippet") or ""
                if title:
                    headline_texts.append(title)

        if not headline_texts:
            return None

        combined_evidence = " ".join(headline_texts).lower()

        # Find detected location
        detected_loc = location
        if not detected_loc:
            for kb in _EVENT_KNOWLEDGE_BASE:
                m = re.search(kb["location_pattern"], combined_evidence)
                if m:
                    detected_loc = m.group(1).title()
                    break

        if not detected_loc:
            # Check prompt text for location hints
            m = re.search(r"\b(nepal|kathmandu|tokyo|japan|california|sydney|london|paris|beijing)\b", text.lower())
            if m:
                detected_loc = m.group(1).title()
            else:
                detected_loc = "Local"

        # Discover matching concrete event keywords in live evidence (distinct roots)
        discovered_roots: list[str] = []
        for root_name, pattern in _EVENT_ROOTS:
            if re.search(pattern, combined_evidence):
                discovered_roots.append(root_name)

        if not discovered_roots:
            return None

        # Build synthesized event name
        primary_kw = discovered_roots[0].title()
        secondary_kw = discovered_roots[1].title() if len(discovered_roots) > 1 else ""
        event_name = f"{primary_kw} and {secondary_kw}" if secondary_kw and secondary_kw != primary_kw else primary_kw

        # Extract top 3 evidence citations
        top_evidence = tuple(headline_texts[:4])

        specific_query = f"{detected_loc} {primary_kw.lower()} {secondary_kw.lower()} damage rescue aftermath photos news 2026".strip()
        specific_query = re.sub(r"\s{2,}", " ", specific_query)

        return ResolvedCurrentEvent(
            event_name=f"{detected_loc} {event_name}",
            location=detected_loc,
            canonical_subject=f"{detected_loc} {event_name}",
            specific_search_query=specific_query,
            alternate_queries=(
                f"{detected_loc} {primary_kw.lower()} disaster emergency response photos",
                f"{detected_loc} breaking news {primary_kw.lower()} latest pictures",
            ),
            evidence=top_evidence,
            expected_entities=tuple({detected_loc, primary_kw, *discovered_roots[:3]}),
        )

    @classmethod
    async def resolve_event_live(
        cls,
        text: str,
        *,
        location: str | None = None,
    ) -> ResolvedCurrentEvent | None:
        """Asynchronously discovers current event via live web search before falling back to heuristics."""
        try:
            from hinaa_api.tools.browser import search_web
            search_query = f"{location or text} latest news headlines 2026 breaking"
            res = await search_web({"query": search_query, "count": 6})
            sources = res.get("sources") or res.get("results") or []
            if sources:
                resolved = cls.resolve_event_from_evidence(text, sources, location=location)
                if resolved:
                    return resolved
        except Exception:
            pass

        # Fallback to synchronous resolver
        return cls.resolve_event(text, location=location)

    @classmethod
    def resolve_event(
        cls,
        text: str,
        *,
        location: str | None = None,
        event_marker: str | None = None,
        evidence: list[str] | None = None,
    ) -> ResolvedCurrentEvent | None:
        lowered = text.lower()

        # 1. If explicit evidence was passed, resolve from evidence first
        if evidence:
            from_ev = cls.resolve_event_from_evidence(text, evidence, location=location)
            if from_ev:
                return from_ev

        # 2. Match against known knowledge base patterns
        for entry in _EVENT_KNOWLEDGE_BASE:
            loc_match = re.search(entry["location_pattern"], lowered)
            evt_match = re.search(entry["event_pattern"], lowered)
            if loc_match and evt_match:
                return ResolvedCurrentEvent(
                    event_name=entry["event_name"],
                    location=entry["location"],
                    canonical_subject=entry["canonical_subject"],
                    specific_search_query=entry["specific_search_query"],
                    alternate_queries=entry["alternate_queries"],
                    evidence=(f"matched_kb:{entry['event_name']}",),
                    expected_entities=entry["expected_entities"],
                )

        # 3. Dynamic synthesis when location and event markers exist but are not in the predefined table
        if location:
            loc_clean = location.title().strip()
            evt_name = "Current Incident"
            evt_match = re.search(
                r"\b(flood|flooding|earthquake|landslide|crash|fire|protest|riot|disaster|storm|cyclone|crisis)\b",
                lowered,
            )
            if evt_match:
                evt_name = evt_match.group(1).title()

            specific_query = f"{loc_clean} {evt_name.lower()} news emergency rescue damage photos 2026"
            return ResolvedCurrentEvent(
                event_name=f"{loc_clean} {evt_name}",
                location=loc_clean,
                canonical_subject=f"{loc_clean} {evt_name}",
                specific_search_query=specific_query,
                alternate_queries=(
                    f"{loc_clean} {evt_name.lower()} latest pictures news",
                    f"{loc_clean} news report aftermath emergency",
                ),
                evidence=("dynamic_location_event_synthesis",),
                expected_entities=(loc_clean, evt_name),
            )

        return None
