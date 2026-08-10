"""Genuine web search via DuckDuckGo's HTML endpoint (no API key needed)."""

import html as html_lib
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from .registry import ToolDefinition, registry

_RESULT_LINK = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
_RESULT_SNIPPET = re.compile(
    r'<a[^>]+class="result__snippet[^"]*"[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
_TAG = re.compile(r"<[^>]+>")


def _clean(fragment: str) -> str:
    return html_lib.unescape(_TAG.sub("", fragment)).strip()


def _resolve_redirect(href: str) -> str:
    """DuckDuckGo wraps result URLs in a /l/?uddg=<encoded> redirect."""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return unquote(target)
    return href


async def search_web(params: dict[str, Any]) -> dict[str, Any]:
    query = str(params.get("query", "")).strip()
    if not query:
        return {"error": "Query is required"}

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers=headers,
            )
            resp.raise_for_status()
    except httpx.HTTPError as e:
        return {"error": f"Search request failed: {e}"}

    page = resp.text
    links = _RESULT_LINK.findall(page)
    snippets = [_clean(s) for s in _RESULT_SNIPPET.findall(page)]

    results = []
    for i, (href, title_html) in enumerate(links[:8]):
        url = _resolve_redirect(href)
        if not url.startswith("http"):
            continue
        results.append(
            {
                "title": _clean(title_html),
                "url": url,
                "snippet": snippets[i] if i < len(snippets) else "",
            }
        )

    return {"query": query, "results": results[:5]}


web_search_def = ToolDefinition(
    name="web_search",
    display_name="Search the Web",
    description="Search the web for real-time information.",
    parameters={"query": {"type": "string", "description": "The search query to execute"}},
    required_parameters=["query"],
    cancellable=True,
    voice_aliases=["search for", "look up", "find"],
)

registry.register(web_search_def, search_web)
