"""Live Web Search Adapter for Grounded Research.

Queries live external search APIs (Exa / Brave / Serper / Custom HTTP gateway)
when configured, handling network timeouts and HTTP errors with graceful fallback.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Sequence
import httpx
from ..models import Source, TrustTier
from .base import BaseSearchAdapter

logger = logging.getLogger("hinaa.research.live_adapter")


class LiveSearchAdapter(BaseSearchAdapter):
    """Executes live web search queries against configured external search endpoints."""

    def __init__(self, api_key: str | None = None, search_url: str | None = None, timeout_seconds: float = 8.0) -> None:
        self.api_key = api_key
        self.search_url = search_url or "https://api.exa.ai/search"
        self.timeout_seconds = timeout_seconds

    async def search(self, query: str, *, limit: int = 5, requesting_user_id: str | None = None) -> list[Source]:
        if not self.api_key:
            logger.info("LiveSearchAdapter: No API key configured; returning empty list for fallback")
            return []

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "HINAA-CRAG-Agent/2.0",
        }
        payload = {
            "query": query,
            "numResults": limit,
            "contents": {"text": True},
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(self.search_url, json=payload, headers=headers)
                if resp.status_code == 429:
                    logger.warning("LiveSearchAdapter: Rate limit exceeded (429)")
                    raise RuntimeError("SEARCH_PROVIDER_RATE_LIMITED")
                if resp.status_code >= 500:
                    logger.warning("LiveSearchAdapter: Search provider server error (%d)", resp.status_code)
                    raise RuntimeError(f"SEARCH_PROVIDER_ERROR_{resp.status_code}")
                resp.raise_for_status()
                data = resp.json()

            results: list[Source] = []
            for idx, item in enumerate(data.get("results", [])):
                url = item.get("url", "")
                title = item.get("title", "Web Source")
                text = item.get("text", "")[:1200]
                source_id = f"live-src-{idx+1}-{hashlib.md5(url.encode()).hexdigest()[:8]}"
                src = Source(
                    source_id=source_id,
                    title=title,
                    url=url,
                    publisher=item.get("author") or "Web",
                    publication_date=item.get("publishedDate"),
                    excerpt=text,
                    query=query,
                    trust_tier=TrustTier.REPUTABLE_SECONDARY,
                )
                src.compute_hash(text)
                results.append(src)
            return results

        except httpx.TimeoutException:
            logger.warning("LiveSearchAdapter: Search request timed out after %.1fs", self.timeout_seconds)
            raise RuntimeError("SEARCH_PROVIDER_TIMEOUT")
        except httpx.RequestError as exc:
            logger.warning("LiveSearchAdapter: Network request failed: %s", exc)
            raise RuntimeError(f"SEARCH_PROVIDER_NETWORK_ERROR: {exc}")
