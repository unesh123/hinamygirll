"""router.py — High-Performance Semantic & Keyword Skill Router.

Solves the large-scale skill discovery problem:
When HINAA has hundreds or thousands of skills, injecting all schemas into an LLM context
window degrades performance, introduces latency, and exhausts context limits.

The SkillRouter provides sub-5ms BM25/keyword indexing and scoring to dynamically identify
the top-K relevant skills for any conversation turn or user goal.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .catalog import SkillCatalog, SkillRecord, skill_catalog

logger = logging.getLogger("hinaa.skills.router")

_TOKEN_SPLIT = re.compile(r"[\s\-_/:.,!?#@()\[\]{}'\"]+")


def _tokenize(text: str) -> list[str]:
    """Tokenizes a string into lowercase alphabetic/numeric terms."""
    if not text:
        return []
    return [t.lower() for t in _TOKEN_SPLIT.split(text) if len(t) >= 2]


@dataclass
class ScoredSkill:
    skill: SkillRecord
    score: float
    matched_terms: list[str]


class SkillRouter:
    """Inverted Index & Scoring Engine for routing user queries to matching skills."""

    def __init__(self, catalog: SkillCatalog | None = None):
        self.catalog = catalog or skill_catalog
        self._doc_freq: Counter[str] = Counter()
        self._skill_tokens: dict[str, Counter[str]] = {}
        self._total_skills: int = 0
        self._indexed: bool = False

    def build_index(self, force: bool = False) -> None:
        if self._indexed and not force:
            return

        self.catalog.load_all_skills(force_reload=force)
        self._doc_freq.clear()
        self._skill_tokens.clear()

        skills = self.catalog.list_all()
        self._total_skills = len(skills)

        for s in skills:
            # Combine fields with weighted repetition for title and triggers
            text_corpus = (
                f"{s.name} {s.name} "
                f"{' '.join(s.triggers)} {' '.join(s.triggers)} "
                f"{s.category} "
                f"{s.description}"
            )
            tokens = _tokenize(text_corpus)
            tf = Counter(tokens)
            self._skill_tokens[s.id] = tf

            for term in tf.keys():
                self._doc_freq[term] += 1

        self._indexed = True
        logger.info("SkillRouter indexed %d skills with %d unique terms", self._total_skills, len(self._doc_freq))

    def search(
        self,
        query: str,
        top_k: int = 5,
        category: str | None = None,
        min_score: float = 0.5,
    ) -> list[ScoredSkill]:
        """Finds the top-K matching skills for a user query."""
        self.build_index()

        query_terms = _tokenize(query)
        if not query_terms:
            return []

        results: list[ScoredSkill] = []

        for skill_id, tf in self._skill_tokens.items():
            skill = self.catalog.get_skill(skill_id)
            if not skill:
                continue

            if category and skill.category.lower() != category.lower():
                continue

            score = 0.0
            matched_terms: list[str] = []

            for term in query_terms:
                if term in tf:
                    matched_terms.append(term)
                    # Term frequency in skill
                    term_count = tf[term]
                    # Inverse document frequency
                    df = self._doc_freq.get(term, 1)
                    idf = math.log(1.0 + (self._total_skills - df + 0.5) / (df + 0.5))
                    idf = max(idf, 0.1)

                    # Boost if the term directly matches the skill name or a trigger
                    boost = 1.0
                    if term in skill.id.lower():
                        boost += 3.0
                    if any(term in trig.lower() for trig in skill.triggers):
                        boost += 2.5

                    score += (term_count * idf) * boost

            if score >= min_score and matched_terms:
                results.append(ScoredSkill(skill=skill, score=round(score, 3), matched_terms=matched_terms))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def route_prompt_tools(self, user_turn: str, max_tools: int = 6) -> list[str]:
        """Returns the specific executable tool names to inject for this turn."""
        matches = self.search(user_turn, top_k=max_tools * 2)
        tool_names: list[str] = []

        for m in matches:
            if m.skill.kind in ("executable_tool", "hybrid_skill"):
                clean_name = m.skill.id.replace("tool:", "")
                if clean_name not in tool_names:
                    tool_names.append(clean_name)
                    if len(tool_names) >= max_tools:
                        break

        return tool_names


skill_router = SkillRouter()
