"""Recency + relevance ranking."""

from __future__ import annotations

import math
from datetime import UTC, datetime

from .text import Article, title_tokens

HALF_LIFE_HOURS = 24.0


def relevance(article: Article, queries: list[str]) -> float:
    """Best share of a query's terms found (title counts double), 0..1; 0.5 when nothing to match."""
    groups = [t for t in (title_tokens(q) for q in queries) if t]
    if not groups:
        return 0.5
    title, body = title_tokens(article.title), title_tokens(article.summary)
    best = 0.0
    for group in groups:
        hits = sum(2 if t in title else 1 if t in body else 0 for t in group)
        best = max(best, hits / (2 * len(group)))
    return min(best, 1.0)


def recency(article: Article, now: datetime) -> float:
    if article.published is None:
        return 0.3
    age_hours = max((now - article.published).total_seconds() / 3600, 0.0)
    return math.exp(-math.log(2) * age_hours / HALF_LIFE_HOURS)


def rank(articles: list[Article], queries: list[str], now: datetime | None = None) -> list[Article]:
    moment = now or datetime.now(UTC)
    for a in articles:
        corroboration = min(len(a.also), 3) * 0.05
        a.score = round(0.6 * relevance(a, queries) + 0.4 * recency(a, moment) + corroboration, 6)
    return sorted(articles, key=lambda a: (-a.score, a.title.lower()))

# ruff: noqa: E501
