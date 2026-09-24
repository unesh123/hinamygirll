"""HINA ASTRA — Entity Extractor.

Extracts named entities, series, files, and domain concepts from conversational text.
Integrates with the high-confidence canonical entity registry and regex patterns.
"""

from __future__ import annotations

import re
from typing import Any

from .models import EntityState

# High-confidence canonical entity dictionary
KNOWN_ENTITIES: dict[str, dict[str, Any]] = {
    "mikasa ackerman": {
        "canonical_name": "Mikasa Ackerman",
        "entity_type": "character",
        "domain": "Attack on Titan",
        "aliases": ["mikasa", "ackerman", "mikas ackerman", "mikasa akerman"],
        "attributes": {"gender": "female", "role": "soldier", "series": "Attack on Titan"},
    },
    "eren yeager": {
        "canonical_name": "Eren Yeager",
        "entity_type": "character",
        "domain": "Attack on Titan",
        "aliases": ["eren", "yeager", "jaeger", "eren jaeger"],
        "attributes": {"gender": "male", "role": "protagonist", "series": "Attack on Titan"},
    },
    "levi ackerman": {
        "canonical_name": "Levi Ackerman",
        "entity_type": "character",
        "domain": "Attack on Titan",
        "aliases": ["levi", "captain levi"],
        "attributes": {"gender": "male", "role": "captain", "series": "Attack on Titan"},
    },
    "gojo satoru": {
        "canonical_name": "Gojo Satoru",
        "entity_type": "character",
        "domain": "Jujutsu Kaisen",
        "aliases": ["gojo", "satoru gojo", "satoru"],
        "attributes": {"gender": "male", "role": "sorcerer", "series": "Jujutsu Kaisen"},
    },
    "naruto uzumaki": {
        "canonical_name": "Naruto Uzumaki",
        "entity_type": "character",
        "domain": "Naruto",
        "aliases": ["naruto", "uzumaki naruto"],
        "attributes": {"gender": "male", "role": "hokage", "series": "Naruto"},
    },
    "monkey d luffy": {
        "canonical_name": "Monkey D. Luffy",
        "entity_type": "character",
        "domain": "One Piece",
        "aliases": ["luffy", "straw hat luffy", "monkey d. luffy"],
        "attributes": {"gender": "male", "role": "pirate", "series": "One Piece"},
    },
}

# Reverse lookup alias map
_ALIAS_LOOKUP: dict[str, dict[str, Any]] = {}
for item in KNOWN_ENTITIES.values():
    _ALIAS_LOOKUP[item["canonical_name"].lower()] = item
    for a in item["aliases"]:
        _ALIAS_LOOKUP[a.lower()] = item

# File pattern regex: matches e.g. "Hero.tsx", "main.py", "styles.css", "schema.sql"
_FILE_RE = re.compile(r"\b([A-Za-z0-9_-]+\.(?:tsx?|jsx?|py|json|md|html|css|sql|ya?ml))\b", re.I)

# Technology stack pattern
_TECH_RE = re.compile(r"\b(React|Next\.js|TypeScript|Python|FastAPI|PostgreSQL|Tailwind|Docker|Redis|Vite|Playwright)\b", re.I)


class EntityExtractor:
    """Extracts known and candidate entities from conversational text."""

    def extract(self, text: str, conversation_id: str = "", turn: int = 1) -> list[EntityState]:
        extracted: list[EntityState] = []
        seen_names: set[str] = set()
        lower = text.lower()

        # 1. Match known canonical entities and aliases
        # Sort keys by descending length so "mikasa ackerman" matches before "mikasa"
        sorted_keys = sorted(_ALIAS_LOOKUP.keys(), key=len, reverse=True)
        for key in sorted_keys:
            pattern = rf"\b{re.escape(key)}\b"
            if re.search(pattern, lower):
                info = _ALIAS_LOOKUP[key]
                canon = info["canonical_name"]
                if canon not in seen_names:
                    seen_names.add(canon)
                    extracted.append(
                        EntityState(
                            conversation_id=conversation_id,
                            canonical_name=canon,
                            entity_type=info["entity_type"],
                            domain=info["domain"],
                            aliases=list(info["aliases"]),
                            attributes=dict(info["attributes"]),
                            salience=1.0,
                            confidence=0.98,
                            first_turn=turn,
                            last_turn=turn,
                        )
                    )

        # 2. Match source code files
        for m in _FILE_RE.finditer(text):
            filename = m.group(1)
            if filename not in seen_names:
                seen_names.add(filename)
                extracted.append(
                    EntityState(
                        conversation_id=conversation_id,
                        canonical_name=filename,
                        entity_type="file",
                        domain="code",
                        aliases=[],
                        attributes={"filename": filename},
                        salience=0.9,
                        confidence=0.95,
                        first_turn=turn,
                        last_turn=turn,
                    )
                )

        # 3. Match major technology names
        for m in _TECH_RE.finditer(text):
            tech = m.group(1)
            if tech not in seen_names:
                seen_names.add(tech)
                extracted.append(
                    EntityState(
                        conversation_id=conversation_id,
                        canonical_name=tech,
                        entity_type="technology",
                        domain="software",
                        aliases=[tech.lower()],
                        attributes={},
                        salience=0.85,
                        confidence=0.90,
                        first_turn=turn,
                        last_turn=turn,
                    )
                )

        return extracted
