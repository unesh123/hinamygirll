from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any


class TopicTransition(str, Enum):
    SAME_TOPIC = "SAME_TOPIC"
    SUBTOPIC = "SUBTOPIC"
    EXPLICIT_SWITCH = "EXPLICIT_SWITCH"
    RETURN_TO_PREVIOUS = "RETURN_TO_PREVIOUS"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class EntityProfile:
    entity_id: str
    canonical_name: str
    entity_type: str = "character"
    aliases: tuple[str, ...] = ()
    franchise: str | None = None


@dataclass(frozen=True)
class MediaSubjectResolution:
    subject: str
    canonical_subject: str
    source_tier: int  # 1..8 priority tier
    confidence: float
    is_current_event: bool = False
    location: str | None = None
    temporal_anchor: str | None = None
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class MediaIntent:
    intent_type: str
    subject: str
    canonical_subject: str
    entity_ids: tuple[str, ...] = ()
    subject_type: str = "unknown"
    modifiers: tuple[str, ...] = ()
    quantity: int = 6
    confidence: float = 0.0
    evidence: tuple[str, ...] = ()
    is_current_event: bool = False
    location: str | None = None


@dataclass(frozen=True)
class SearchQuerySpec:
    primary_query: str
    alternate_queries: tuple[str, ...] = ()
    negative_terms: tuple[str, ...] = ()
    expected_entities: tuple[str, ...] = ()
    provider_profile: str = "general_web_image_search"


ENTITY_REGISTRY: dict[str, EntityProfile] = {
    "mikasa_ackerman": EntityProfile(
        entity_id="mikasa_ackerman",
        canonical_name="Mikasa Ackerman",
        aliases=(
            "mikasa",
            "mikasa ackerman",
            "mikas ackerman",
            "mikasa akerman",
            "mikas akerman",
            "mikas",
        ),
        franchise="Attack on Titan",
    ),
    "gojo_satoru": EntityProfile(
        entity_id="gojo_satoru",
        canonical_name="Gojo Satoru",
        aliases=("gojo", "gojo satoru", "satoru gojo", "gozo", "gojo saturo"),
        franchise="Jujutsu Kaisen",
    ),
    "naruto_uzumaki": EntityProfile(
        entity_id="naruto_uzumaki",
        canonical_name="Naruto Uzumaki",
        aliases=("naruto", "naruto uzumaki", "uzumaki naruto"),
        franchise="Naruto",
    ),
    "eren_yeager": EntityProfile(
        entity_id="eren_yeager",
        canonical_name="Eren Yeager",
        aliases=("eren", "eren yeager", "eren jaeger"),
        franchise="Attack on Titan",
    ),
    "levi_ackerman": EntityProfile(
        entity_id="levi_ackerman",
        canonical_name="Levi Ackerman",
        aliases=("levi", "levi ackerman"),
        franchise="Attack on Titan",
    ),
    "monkey_d_luffy": EntityProfile(
        entity_id="monkey_d_luffy",
        canonical_name="Monkey D. Luffy",
        aliases=("luffy", "monkey d luffy", "monkey d. luffy"),
        franchise="One Piece",
    ),
}

_ALIAS_TO_PROFILE: dict[str, EntityProfile] = {
    alias.casefold(): profile
    for profile in ENTITY_REGISTRY.values()
    for alias in (profile.canonical_name, *profile.aliases)
}

_MEDIA_WORD_RE = re.compile(r"\b(images?|pictures?|photos?|pics?|imgs?|wallpapers?|gallery|references?)\b", re.I)
_SEARCH_VERB_RE = re.compile(r"\b(fetch|find|search|show|sho|display|get|bring|see|load|look\s+for)\b", re.I)
_GENERIC_REF_RE = re.compile(
    r"^(?:her|him|it|them|this|that|these|those|same|more|show\s+more(?:\s+of\s+(?:her|him|it|them))?|more\s+of\s+(?:her|him|it|them)|more\s+(?:her|him|them|it)|fetch\s+them|get\s+them|more\s+images?|another\s+one|images?|pics?)$",
    re.I,
)
_DEICTIC_PHRASE_RE = re.compile(
    r"\b(show\s+more|fetch\s+them|get\s+them|see\s+them|another\s+one|same|(?:about|of|for|on|with|describe|explain|tell\s+me\s+about)\s+(?:her|him|them|it|character)|(?:about|of|for)\s+this\s+(?:character|person|topic)|about\s+her|about\s+him|about\s+them)\b",
    re.I,
)
_COMMAND_NOISE_RE = re.compile(
    r"\b(?:i|need|want|wanna|hinaa?|hina|please|pls|bro|babe|fetch|find|search|show|sho|display|get|bring|see|load|look|for|me|some|them|these|those|images?|imges|pictures?|photos?|pics?|gallery|of|about|full|description|details?|now|also|then|can\s+you|could\s+you)\b",
    re.I,
)

# Current event and geographic detection patterns
_CURRENT_EVENT_MARKERS_RE = re.compile(
    r"\b(incident|incidents|flood|floods|flooding|earthquake|landslide|crash|protest|protests|election|elections|disaster|breaking|news|fire|riot|explosion|summit|scandal|crisis|situation|update|updates)\b",
    re.I,
)
_TEMPORAL_ANCHOR_RE = re.compile(
    r"\b(current|latest|recent|today|yesterday|now|breaking|this\s+week|live)\b",
    re.I,
)
_KNOWN_LOCATIONS_RE = re.compile(
    r"\b(nepal|kathmandu|pokhara|japan|tokyo|kyoto|india|delhi|mumbai|china|beijing|shanghai|usa|america|california|new\s+york|uk|britain|london|france|paris|germany|berlin|korea|seoul)\b",
    re.I,
)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \t\r\n.,!?;:：")


def _is_entity_negated(alias: str, text: str) -> bool:
    neg_pat = (
        r"(?i)\b(?:not|no|stop|forget|leave|don'?t\s+(?:want|mention|search(?:\s+for)?|look(?:\s+for)?|fetch|show|talk(?:\s+about)?))\s+"
        r"(?:(?:more|about|searching(?:\s+for)?|looking(?:\s+for)?|fetching|showing|talking(?:\s+about)?)\s+)?"
        + re.escape(alias)
        + r"\b|\b"
        + re.escape(alias)
        + r"\s+(?:mat|nahi|nhi|na|haina|chaidaina)\b"
    )
    return bool(re.search(neg_pat, text))


def canonical_entity_from_text(text: str) -> EntityProfile | None:
    lowered = f" {text.casefold()} "
    for alias, profile in sorted(_ALIAS_TO_PROFILE.items(), key=lambda item: -len(item[0])):
        if re.search(rf"\b{re.escape(alias)}\b", lowered, re.I):
            if _is_entity_negated(alias, text):
                continue
            return profile
    compact = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
    for alias, profile in sorted(_ALIAS_TO_PROFILE.items(), key=lambda item: -len(item[0])):
        alias_compact = re.sub(r"[^a-z0-9]+", " ", alias).strip()
        if alias_compact and alias_compact in compact:
            if _is_entity_negated(alias, text):
                continue
            return profile
    return None


def clean_raw_image_query(text: str) -> str:
    cleaned = normalize_space(text)
    # Strip any negated character phrases first
    for alias in _ALIAS_TO_PROFILE:
        neg_pat = (
            r"(?i)\b(?:not|no|stop|forget|leave|don'?t\s+(?:want|mention|search(?:\s+for)?|look(?:\s+for)?|fetch|show|talk(?:\s+about)?))\s+"
            r"(?:(?:more|about|searching(?:\s+for)?|looking(?:\s+for)?|fetching|showing|talking(?:\s+about)?)\s+)?"
            + re.escape(alias)
            + r"\b|\b"
            + re.escape(alias)
            + r"\s+(?:mat|nahi|nhi|na|haina|chaidaina)\b"
        )
        cleaned = re.sub(neg_pat, " ", cleaned)

    # Strip leading greetings, conversational preambles, and conversational adverbs like 'now', 'so'
    cleaned = re.sub(
        r"(?i)^\s*(?:now|so|and|then|also|okay|ok)?\s*(?:hey\s+)?(?:hinaa?|hina|babe|bro)?[,\s]*(?:please|pls)?[,\s]*(?:can|could|would|will)?\s*(?:you|u)?\s*",
        "",
        cleaned,
    )
    # Strip imperative query verbs + optional image noun phrase
    cleaned = re.sub(
        r"(?i)^\s*(?:now|so)?\s*(?:i\s+)?(?:need|want|wanna|would\s+like)?\s*(?:to\s+)?(?:fetch|find|search|show|sho|display|get|bring|see|load|look\s+for)?\s*(?:me\s+)?(?:some\s+)?(?:images?|imges|pictures?|photos?|pics?|gallery)?\s*(?:of|for|about)?\s*",
        "",
        cleaned,
    )
    # Strip trailing image and noise words
    cleaned = re.sub(
        r"(?i)\s+(?:images?|imges|pictures?|photos?|pics?|wallpapers?|gallery|please|pls|for\s+me|now|hina|hinaa?|bro)\s*$",
        "",
        cleaned,
    )
    return normalize_space(cleaned)


def is_media_search_request(text: str) -> bool:
    lowered = text.casefold()
    if re.search(r"\b(full\s+description|details?\s+about|tell\s+me\s+about|who\s+is|what\s+is|explain)\b", lowered):
        return False
    return bool(
        (_MEDIA_WORD_RE.search(lowered) and _SEARCH_VERB_RE.search(lowered))
        or re.search(r"\b(show more|fetch them|get them|more images?)\b", lowered)
        or re.search(r"\b(fetch|show|find)\s+.*\b(images?|photos?|pictures?)\b", lowered)
    )


def _profile_from_active(active_subject: str | None) -> EntityProfile | None:
    if not active_subject:
        return None
    return canonical_entity_from_text(active_subject) or next(
        (profile for profile in ENTITY_REGISTRY.values() if profile.canonical_name.casefold() == active_subject.casefold()),
        None,
    )


def detect_topic_transition(
    current_text: str,
    *,
    active_topic: str | None = None,
    active_entities: list[dict[str, Any]] | None = None,
    active_thread: Any | None = None,
) -> TopicTransition:
    """Classifies the semantic transition relation between current user input and active conversation state."""
    cleaned = clean_raw_image_query(current_text)
    lowered = current_text.lower().strip()

    # 1. Check if the input is purely deictic or referential to the ongoing subject
    is_deictic = bool(
        _GENERIC_REF_RE.fullmatch(cleaned)
        or _GENERIC_REF_RE.fullmatch(lowered)
        or _DEICTIC_PHRASE_RE.search(lowered)
        or (active_topic and re.search(r"\b(?:about|on|for|describe|explain)?\s*(?:her|him|she|he|his|them)\b", lowered))
    )
    if is_deictic:
        # If it specifically names a new subject or location in addition, don't treat as same topic
        has_new_loc = bool(_KNOWN_LOCATIONS_RE.search(lowered))
        has_new_event = bool(_CURRENT_EVENT_MARKERS_RE.search(lowered))
        if not (has_new_loc or has_new_event):
            return TopicTransition.SAME_TOPIC

    # 2. Check if a new explicit entity from the registry is named
    explicit_entity = canonical_entity_from_text(current_text)
    if explicit_entity:
        if active_topic and explicit_entity.canonical_name.casefold() == active_topic.casefold():
            return TopicTransition.SAME_TOPIC
        return TopicTransition.EXPLICIT_SWITCH

    # 3. Check for explicit geographic locations or real-world current event markers
    has_loc = bool(_KNOWN_LOCATIONS_RE.search(lowered))
    has_event = bool(_CURRENT_EVENT_MARKERS_RE.search(lowered))
    if has_loc or has_event:
        # Check if the active topic already matches this location/event
        if active_topic and any(term in active_topic.lower() for term in (cleaned.lower(),)):
            return TopicTransition.SAME_TOPIC
        return TopicTransition.EXPLICIT_SWITCH

    # 4. Check if substantive cleaned query is provided and does not match active topic
    if len(cleaned) >= 3 and not _GENERIC_REF_RE.fullmatch(cleaned):
        if active_topic and cleaned.lower() in active_topic.lower():
            return TopicTransition.SAME_TOPIC
        return TopicTransition.EXPLICIT_SWITCH

    return TopicTransition.SAME_TOPIC if active_topic else TopicTransition.AMBIGUOUS


def resolve_media_subject(
    text: str,
    *,
    active_subject: str | None = None,
    selected_subject: str | None = None,
    active_entities: list[dict[str, Any]] | None = None,
    transition: TopicTransition | None = None,
) -> MediaSubjectResolution | None:
    """Enforces the 8-tier topic precedence hierarchy:
    Tier 1: Explicit subject in current message (canonical registry or named entity)
    Tier 2: Explicit event / location / time in current message
    Tier 3: Explicit attached / clicked asset reference (selected_subject)
    Tier 4: Pending media action
    Tier 5: Current active thread
    Tier 6: Current active entity (active_subject)
    Tier 7: Recent compatible entity
    Tier 8: Historical / cross-session memory
    LAW: Tiers 5-8 must NEVER override Tiers 1-3.
    """
    cleaned = clean_raw_image_query(text)
    lowered = text.lower()
    transition = transition or detect_topic_transition(
        text,
        active_topic=active_subject,
        active_entities=active_entities,
    )

    # Check Tier 1: Explicit registry entity in current message
    explicit_entity = canonical_entity_from_text(text)
    if explicit_entity:
        return MediaSubjectResolution(
            subject=explicit_entity.canonical_name,
            canonical_subject=explicit_entity.canonical_name,
            source_tier=1,
            confidence=0.98,
            is_current_event=False,
            evidence=("tier1_explicit_entity",),
        )

    # Check Tier 2: Explicit event / location in current message
    has_loc = _KNOWN_LOCATIONS_RE.search(lowered)
    has_event = _CURRENT_EVENT_MARKERS_RE.search(lowered)
    has_temporal = _TEMPORAL_ANCHOR_RE.search(lowered)
    loc_str = has_loc.group(0).title() if has_loc else None
    temp_str = has_temporal.group(0).lower() if has_temporal else None

    # If the user named a substantive non-generic subject (or explicit location/event)
    is_explicit_request = (
        transition == TopicTransition.EXPLICIT_SWITCH
        or bool(has_loc or has_event)
        or (len(cleaned) >= 2 and not _GENERIC_REF_RE.fullmatch(cleaned) and transition != TopicTransition.SAME_TOPIC)
    )

    if is_explicit_request and len(cleaned) >= 2 and not _GENERIC_REF_RE.fullmatch(cleaned):
        without_noise = normalize_space(_COMMAND_NOISE_RE.sub(" ", cleaned))
        subject = without_noise or cleaned
        is_current = bool(has_loc or has_event or has_temporal)
        return MediaSubjectResolution(
            subject=subject,
            canonical_subject=subject.title(),
            source_tier=2 if is_current else 1,
            confidence=0.92 if is_current else 0.85,
            is_current_event=is_current,
            location=loc_str,
            temporal_anchor=temp_str,
            evidence=("tier2_explicit_event_or_location" if is_current else "tier1_explicit_text_subject",),
        )

    # Check Tier 3: Explicit selected subject / asset reference
    if selected_subject and not _is_entity_negated(selected_subject, text):
        prof = _profile_from_active(selected_subject)
        canonical = prof.canonical_name if prof else selected_subject
        return MediaSubjectResolution(
            subject=canonical,
            canonical_subject=canonical,
            source_tier=3,
            confidence=0.88,
            is_current_event=False,
            evidence=("tier3_selected_asset_subject",),
        )

    # Tiers 5-6: Active thread & active entity (ONLY allowed when request is deictic or same topic)
    if active_subject and not _is_entity_negated(active_subject, text):
        if not any(k in active_subject.lower() for k in ("anime", "image", "general", "something")):
            prof = _profile_from_active(active_subject)
            canonical = prof.canonical_name if prof else active_subject
            return MediaSubjectResolution(
                subject=canonical,
                canonical_subject=canonical,
                source_tier=6,
                confidence=0.82,
                is_current_event=False,
                evidence=("tier6_active_entity_reference",),
            )

    return None


def build_media_intent(
    text: str,
    *,
    active_subject: str | None = None,
    selected_subject: str | None = None,
    active_entities: list[dict[str, Any]] | None = None,
    quantity: int = 6,
) -> MediaIntent | None:
    resolution = resolve_media_subject(
        text,
        active_subject=active_subject,
        selected_subject=selected_subject,
        active_entities=active_entities,
    )
    if not resolution:
        return None

    prof = next(
        (p for p in ENTITY_REGISTRY.values() if p.canonical_name.casefold() == resolution.canonical_subject.casefold()),
        None,
    )
    subject_type = prof.entity_type if prof else ("current_event" if resolution.is_current_event else "topic")
    entity_ids = (prof.entity_id,) if prof else ()

    return MediaIntent(
        intent_type="SEARCH_IMAGES",
        subject=resolution.subject,
        canonical_subject=resolution.canonical_subject,
        entity_ids=entity_ids,
        subject_type=subject_type,
        quantity=quantity,
        confidence=resolution.confidence,
        evidence=resolution.evidence,
        is_current_event=resolution.is_current_event,
        location=resolution.location,
    )


def compile_image_search_query(intent: MediaIntent) -> SearchQuerySpec:
    profile = next((p for p in ENTITY_REGISTRY.values() if p.canonical_name == intent.canonical_subject), None)
    if profile and profile.franchise:
        primary = f"{profile.canonical_name} {profile.franchise}"
        alternates = (
            f"{profile.canonical_name} official art",
            f"{profile.canonical_name} anime",
            f"{profile.canonical_name} Shingeki no Kyojin" if profile.franchise == "Attack on Titan" else f"{profile.canonical_name} {profile.franchise}",
        )
        expected = (profile.canonical_name, profile.franchise, *profile.aliases)
        return SearchQuerySpec(
            primary_query=primary,
            alternate_queries=tuple(dict.fromkeys(alternates)),
            negative_terms=("stock photo", "pronoun", "gender sign", "random person", "vector icon"),
            expected_entities=expected,
            provider_profile="general_web_named_character",
        )

    # Current event image search
    if intent.is_current_event or intent.subject_type in ("current_event", "event", "location") or any(
        m in intent.canonical_subject.lower() for m in ("incident", "flood", "earthquake", "news", "protest", "crash")
    ):
        try:
            from .current_event_resolver import CurrentEventResolver
            resolved = CurrentEventResolver.resolve_event(
                intent.canonical_subject,
                location=intent.location,
            )
        except Exception:
            resolved = None

        if resolved:
            return SearchQuerySpec(
                primary_query=resolved.specific_search_query,
                alternate_queries=resolved.alternate_queries,
                negative_terms=tuple(dict.fromkeys(
                    list(resolved.negative_terms) + [
                        "fanart", "safebooru", "attack on titan", "mikasa", "naruto", "gojo"
                    ]
                )),
                expected_entities=resolved.expected_entities,
                provider_profile="news_image_search",
            )

        primary = f"{intent.canonical_subject} photos news"
        alternates = (
            f"{intent.canonical_subject} latest pictures",
            f"{intent.canonical_subject} news report",
            f"{intent.canonical_subject} breaking",
        )
        expected = (intent.canonical_subject,)
        if intent.location:
            expected = (intent.canonical_subject, intent.location)
        return SearchQuerySpec(
            primary_query=primary,
            alternate_queries=alternates,
            negative_terms=(
                "anime", "manga", "fanart", "illustration", "cosplay", "safebooru",
                "cartoon", "vector", "drawing", "attack on titan", "mikasa", "naruto", "gojo"
            ),
            expected_entities=expected,
            provider_profile="news_image_search",
        )

    return SearchQuerySpec(
        primary_query=intent.canonical_subject,
        alternate_queries=(
            f"{intent.canonical_subject} photos",
            f"{intent.canonical_subject} news",
            f"{intent.canonical_subject} latest",
        ),
        negative_terms=(),
        expected_entities=(intent.canonical_subject,),
        provider_profile="general_web_image_search",
    )


def relevance_score(item: dict[str, Any], spec: SearchQuerySpec) -> float:
    haystack = " ".join(
        str(item.get(key) or "")
        for key in ("title", "description", "snippet", "alt", "source", "pageUrl", "url", "imageUrl", "thumbnailUrl")
    ).casefold()
    score = 0.0

    # Cross-domain consistency penalty: if searching for news/real-world events, heavily penalize anime/fantasy keywords
    if spec.provider_profile in ("news_image_search", "general_web_image_search") and any("anime" in neg for neg in spec.negative_terms):
        for bad in ("anime", "manga", "attack on titan", "shingeki", "mikasa", "booru", "fanart", "cosplay", "otaku"):
            if bad in haystack:
                return -10.0

    expected = [term.casefold() for term in spec.expected_entities if term]
    for term in expected:
        if term and term in haystack:
            score += 3.0 if " " in term else 1.5
    for token in re.findall(r"[a-z0-9]+", spec.primary_query.casefold()):
        if len(token) >= 4 and token in haystack:
            score += 0.7
    for bad in spec.negative_terms:
        if bad.casefold() in haystack:
            score -= 3.0
    if any(domain in haystack for domain in ("fandom", "anidb", "myanimelist", "attackontitan", "shingeki", "wallpaper", "zerochan", "alphacoders", "pinterest", "deviantart")):
        if spec.provider_profile == "general_web_named_character":
            score += 0.8
        else:
            score -= 2.0
    return score


def verify_image_results(
    images: list[dict[str, Any]],
    spec: SearchQuerySpec,
    *,
    threshold: float | None = None,
    limit: int = 6,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    effective_threshold = threshold if threshold is not None else (2.0 if spec.provider_profile == "general_web_named_character" else 0.7)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in images:
        url_key = str(item.get("imageUrl") or item.get("thumbnailUrl") or item.get("url") or item.get("pageUrl") or "")
        title_key = normalize_space(str(item.get("title") or "")).casefold()
        dedupe_key = url_key or f"{title_key}:{item.get('source')}"
        if dedupe_key in seen:
            rejected.append({**item, "relevanceScore": 0.0, "rejectionReason": "duplicate"})
            continue
        seen.add(dedupe_key)
        score = relevance_score(item, spec)
        enriched = {**item, "relevanceScore": round(score, 3)}
        if score >= effective_threshold:
            accepted.append(enriched)
        else:
            rejected.append({**enriched, "rejectionReason": "low_relevance_or_cross_domain"})
        if len(accepted) >= limit:
            break
    return accepted, rejected


def concise_media_text(subject: str, count: int) -> str:
    if count <= 0:
        return f"I couldn't find relevant {subject} images from this source."
    return f"Found {count} relevant {subject} image{'s' if count != 1 else ''}."


def new_result_set_id() -> str:
    return f"rs_{uuid.uuid4().hex[:12]}"
