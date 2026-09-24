"""HINA ASTRA — Pronoun & Deictic Reference Resolver.

Resolves conversational pronouns ('her', 'him', 'it', 'them', 'that file')
against the active entity graph, returning canonical substitutions and tool queries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from .models import EntityState

# Pronoun patterns
_FEMALE_PRONOUNS_RE = re.compile(r"\b(her|she)\b", re.I)
_MALE_PRONOUNS_RE = re.compile(r"\b(him|he|his)\b", re.I)
_OBJECT_PRONOUNS_RE = re.compile(r"\b(it|this|that|that\s+file|this\s+file|that\s+component)\b", re.I)
_DEICTIC_MEDIA_RE = re.compile(
    r"\b(pics?|images?|pictures?|photos?|wallpapers?)\s+(?:of\s+)?(her|him|them|it|character)\b|"
    r"\b(?:show|get|fetch|find|give\s+me)\s+(?:more\s+)?(?:pics?|images?|photos?)\b",
    re.I,
)


@dataclass
class ResolvedReference:
    """The result of resolving conversational deictic references against active entities."""
    original_text: str
    has_reference: bool
    resolved_entity: EntityState | None = None
    canonical_query: str = ""
    grounded_tool_query: str = ""
    substitution_applied: bool = False


class ReferenceResolver:
    """Resolves pronouns and implicit subject queries using conversation entity history."""

    def resolve(
        self,
        text: str,
        active_entities: Sequence[EntityState],
    ) -> ResolvedReference:
        trimmed = text.strip()
        if not active_entities:
            return ResolvedReference(
                original_text=trimmed,
                has_reference=False,
                canonical_query=trimmed,
                grounded_tool_query=trimmed,
            )

        lower = trimmed.lower()
        clean_lower = re.sub(r"[^\w\s]", " ", lower).strip()
        matched_entity: EntityState | None = None
        has_ref = False

        # 1. Check for female pronoun references ("her", "she")
        if _FEMALE_PRONOUNS_RE.search(lower):
            has_ref = True
            # Find highest-salience female entity first, fallback to top character
            for ent in active_entities:
                if ent.attributes.get("gender") == "female":
                    matched_entity = ent
                    break
            if not matched_entity:
                matched_entity = active_entities[0]

        # 2. Check for male pronoun references ("him", "he", "his")
        elif _MALE_PRONOUNS_RE.search(lower):
            has_ref = True
            for ent in active_entities:
                if ent.attributes.get("gender") == "male":
                    matched_entity = ent
                    break
            if not matched_entity:
                matched_entity = active_entities[0]

        # 3. Check for implicit media follow-ups or explicit media queries naming an active entity
        # e.g., "show me images.", "show images", "show me images of Mikasa", "pics of her"
        elif re.search(r"\b(pics?|images?|pictures?|photos?|wallpapers?)\b", clean_lower):
            for ent in active_entities:
                names = [ent.canonical_name.lower()] + [a.lower() for a in ent.aliases]
                if any(re.search(rf"\b{re.escape(n)}\b", clean_lower) for n in names):
                    matched_entity = ent
                    has_ref = True
                    break
            if not matched_entity and (
                re.search(r"\b(show|get|fetch|find|give|more|see)\b", clean_lower)
                or re.search(r"\b(her|him|them|it|character)\b", clean_lower)
                or clean_lower in ("images", "pics", "pictures", "photos")
            ):
                matched_entity = active_entities[0]
                has_ref = True

        # 4. Check for object / file references ("that file", "it")
        elif _OBJECT_PRONOUNS_RE.search(lower):
            has_ref = True
            for ent in active_entities:
                if ent.entity_type in {"file", "concept", "technology"}:
                    matched_entity = ent
                    break
            if not matched_entity:
                matched_entity = active_entities[0]

        if not has_ref or matched_entity is None:
            return ResolvedReference(
                original_text=trimmed,
                has_reference=False,
                canonical_query=trimmed,
                grounded_tool_query=trimmed,
            )

        # Build clean grounded queries
        entity_name = matched_entity.canonical_name
        domain = f" {matched_entity.domain}" if matched_entity.domain else ""

        # Canonical query: replace pronoun or alias with canonical name
        canonical = trimmed
        if _FEMALE_PRONOUNS_RE.search(lower) or _MALE_PRONOUNS_RE.search(lower) or _OBJECT_PRONOUNS_RE.search(lower):
            canonical = re.sub(r"\b(her|him|it|them)\b", entity_name, canonical, flags=re.I)
        for a in matched_entity.aliases:
            if re.search(rf"\b{re.escape(a)}\b", canonical, re.I) and not re.search(rf"\b{re.escape(entity_name)}\b", canonical, re.I):
                canonical = re.sub(rf"\b{re.escape(a)}\b", entity_name, canonical, flags=re.I)
                break

        # Grounded tool query: clean subject + domain
        tool_query = f"{entity_name}{domain}".strip()

        return ResolvedReference(
            original_text=trimmed,
            has_reference=True,
            resolved_entity=matched_entity,
            canonical_query=canonical,
            grounded_tool_query=tool_query,
            substitution_applied=True,
        )
