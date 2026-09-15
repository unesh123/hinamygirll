"""Predictive Context Retriever (inspired by SKULLFIRE07/cortex-memory).

Monitors conversation context and streaming output to predict subsequent turn topics,
anticipating follow-up questions and pre-fetching relevant knowledge/memories
into an in-memory cache for zero-latency consecutive turns.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("hinaa.rag.predictive")

# Patterns indicating potential follow-up exploration directions
_EXPLORATION_PATTERNS = [
    re.compile(r"(?:next steps?|future work|alternatives?|recommendations?):?\s*([^\n.]+)", re.IGNORECASE),
    re.compile(r"(?:compare(?:d)? with|vs\.?|versus)\s+([A-Za-z0-9_ -]{3,30})", re.IGNORECASE),
    re.compile(r"(?:further details on|more information regarding)\s+([^\n.]+)", re.IGNORECASE),
    re.compile(r"(?:risk(?:s)?|challenges?|mitigation)\s*(?:in|for|of)?\s*([^\n.]+)", re.IGNORECASE),
]


@dataclass
class PreFetchItem:
    topic: str
    content: str
    source: str
    timestamp: float = field(default_factory=time.time)
    expires_at: float = 0.0


class PredictiveContextRetriever:
    """Multi-tiered predictive context engine.

    Extracts latent topics and entity targets during active turns and asynchronously
    pre-fetches candidate facts so subsequent queries hit hot cache.
    """

    def __init__(self, ttl_seconds: float = 300.0, max_cache_size: int = 128) -> None:
        self._ttl = ttl_seconds
        self._max_size = max_cache_size
        self._cache: OrderedDict[str, PreFetchItem] = OrderedDict()
        self._lock = asyncio.Lock()

    def predict_followup_topics(self, user_text: str, generated_text: str) -> list[str]:
        """Extract high-probability next-turn candidate topics from text."""
        candidates: list[str] = []
        combined = f"{user_text}\n{generated_text}"

        for pattern in _EXPLORATION_PATTERNS:
            for match in pattern.finditer(combined):
                target = match.group(1).strip()
                if 4 <= len(target) <= 60:
                    candidates.append(target)

        # Extract capitalized multi-word technical entities/locations
        entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", generated_text)
        for ent in entities[:5]:
            if ent not in candidates and len(ent) <= 50:
                candidates.append(ent)

        return candidates[:6]

    async def prefetch_background(
        self,
        topics: list[str],
        fetcher_fn: Callable[[str], Any] | None = None,
    ) -> None:
        """Asynchronously pre-fetch background facts for predicted topics."""
        if not topics:
            return

        for topic in topics:
            key = topic.lower().strip()
            async with self._lock:
                if key in self._cache:
                    # Refresh LRU position
                    self._cache.move_to_end(key)
                    continue

            try:
                content = ""
                if fetcher_fn is not None:
                    if inspect.iscoroutinefunction(fetcher_fn):
                        content = await fetcher_fn(topic)
                    else:
                        content = fetcher_fn(topic)
                else:
                    content = f"Prefetched background reference for topic: {topic}"

                if content:
                    async with self._lock:
                        now = time.time()
                        self._cache[key] = PreFetchItem(
                            topic=topic,
                            content=str(content),
                            source="predictive_cache",
                            timestamp=now,
                            expires_at=now + self._ttl,
                        )
                        if len(self._cache) > self._max_size:
                            self._cache.popitem(last=False)
            except Exception:
                logger.debug("Failed to prefetch predictive topic '%s'", topic, exc_info=True)

    async def get_prefetched(self, query: str) -> str | None:
        """Retrieve cached pre-fetched knowledge if a predicted topic matches query."""
        now = time.time()
        q_clean = query.lower().strip()

        async with self._lock:
            for key, item in list(self._cache.items()):
                if now > item.expires_at:
                    del self._cache[key]
                    continue
                if key in q_clean or q_clean in key:
                    self._cache.move_to_end(key)
                    return item.content

        return None

    def clear(self) -> None:
        self._cache.clear()
