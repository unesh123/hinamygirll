from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from .registry import ToolDefinition, registry


def _destination_url(href: str) -> str:
    """Unwrap DuckDuckGo result redirects without following arbitrary URLs."""
    parsed = urlparse(href)
    values = parse_qs(parsed.query).get("uddg", [])
    if values:
        return unquote(values[0])
    if href.startswith("//"):
        return f"https:{href}"
    return href


async def search_web(params: dict[str, Any]) -> dict[str, Any]:
    """Perform a small, source-attributed web search after user approval."""
    query = str(params.get("query", "")).strip()
    if not query:
        return {"error": "Query is required", "results": [], "sources": []}

    headers = {"User-Agent": "HinaaLocalResearch/1.0 (+local-first assistant)"}
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers=headers,
            )
            response.raise_for_status()
    except httpx.HTTPError as error:
        return {
            "error": "Search provider could not be reached.",
            "detail": str(error),
            "query": query,
            "results": [],
            "sources": [],
        }

    soup = BeautifulSoup(response.text, "html.parser")
    results: list[dict[str, str]] = []
    for item in soup.select(".result"):
        link = item.select_one("a.result__a, a.result__url")
        if not link:
            continue
        href = _destination_url(str(link.get("href") or "").strip())
        title = link.get_text(" ", strip=True)
        snippet_node = item.select_one(".result__snippet")
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
        if not href or not title or not href.startswith(("https://", "http://")):
            continue
        if any(existing["url"] == href for existing in results):
            continue
        results.append({"title": title, "url": href, "snippet": snippet})
        if len(results) >= 5:
            break

    sources = [
        {
            "id": f"S{index}",
            "title": result["title"],
            "url": result["url"],
            "snippet": result["snippet"],
        }
        for index, result in enumerate(results, start=1)
    ]
    return {"query": query, "results": results, "sources": sources, "sourceCount": len(sources)}


web_search_def = ToolDefinition(
    name="web_search",
    display_name="Search the Web",
    description="Search the web for current information and return source-attributed results.",
    parameters={
        "query": {"type": "string", "description": "The search query to execute"}
    },
    required_parameters=["query"],
    requires_confirmation=True,
    cancellable=True,
    voice_aliases=["search for", "look up", "find"],
)

registry.register(web_search_def, search_web)
