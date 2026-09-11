"""Deep research agent — parallel multi-source investigation for HINAA.

When a user asks to research a topic, this fans out across independent
corroboration sources concurrently (general web via You.com when configured,
Wikipedia, arXiv, GitHub, Hacker News, Stack Exchange), merges and de-dupes
what comes back, and returns a structured, cited brief the assistant can
speak and the interface can render source-by-source as it lands. Every
source is bounded, best-effort, and independently timeout-guarded: one dead
API must never sink the research.
"""

from __future__ import annotations

import asyncio
import re
import time
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote_plus

import httpx

from ..config import get_settings
from .registry import ToolDefinition, registry

SOURCE_TIMEOUT_SECONDS = 12.0
MAX_ITEMS_PER_SOURCE = 6

_PUNCT = re.compile(r"[^a-z0-9 ]+")


def _dedupe_key(item: dict[str, Any]) -> str:
    url = str(item.get("url") or item.get("link") or "")
    return url.split("#")[0].rstrip("/") or str(item.get("title", "")).casefold()


def _clean(text: str, limit: int = 420) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[: limit - 1] + "…" if len(text) > limit else text


async def _search_wikipedia(query: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=SOURCE_TIMEOUT_SECONDS, follow_redirects=True) as client:
        search = await client.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query", "list": "search", "srsearch": query,
                "srlimit": 4, "format": "json",
            },
            headers={"User-Agent": "HINAA-companion/1.0 (local research assistant)"},
        )
        search.raise_for_status()
        hits = search.json().get("query", {}).get("search", [])
        pages = [
            {
                "title": hit.get("title", ""),
                "snippet": _clean(re.sub(r"<[^>]+>", "", hit.get("snippet", ""))),
                "url": f"https://en.wikipedia.org/wiki/{quote_plus(hit.get('title', ''))}",
                "source": "Wikipedia",
            }
            for hit in hits[:4]
        ]
        return pages


async def _search_arxiv(query: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=SOURCE_TIMEOUT_SECONDS) as client:
        response = await client.get(
            "http://export.arxiv.org/api/query",
            params={"search_query": f"all:{query}", "start": 0, "max_results": 4},
        )
        response.raise_for_status()
        namespace = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(response.content)
        items: list[dict[str, Any]] = []
        for entry in root.findall("a:entry", namespace)[:4]:
            link_el = entry.find("a:id", namespace)
            authors_nodes = entry.findall("a:author/a:name", namespace)
            items.append({
                "title": _clean(entry.findtext("a:title", default="", namespaces=namespace) or "", 180),
                "snippet": _clean(entry.findtext("a:summary", default="", namespaces=namespace) or ""),
                "url": (link_el.text or "").strip() if link_el is not None else "",
                "source": "arXiv",
                "authors": ", ".join((a.text or "").strip() for a in authors_nodes[:3]),
                "published": (entry.findtext("a:published", default="", namespaces=namespace) or "")[:10],
            })
        return items


async def _search_github(query: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=SOURCE_TIMEOUT_SECONDS) as client:
        response = await client.get(
            "https://api.github.com/search/repositories",
            params={"q": query, "sort": "stars", "per_page": 3},
            headers={"Accept": "application/vnd.github+json", "User-Agent": "HINAA-companion"},
        )
        if response.status_code != 200:
            return []
        body = response.json()
        return [
            {
                "title": item.get("full_name", ""),
                "snippet": _clean(item.get("description") or ""),
                "url": item.get("html_url", ""),
                "source": "GitHub",
                "stars": item.get("stargazers_count", 0),
            }
            for item in (body.get("items") or [])[:3]
        ]


async def _search_hackernews(query: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=SOURCE_TIMEOUT_SECONDS) as client:
        response = await client.get(
            "https://hn.algolia.com/api/v1/search",
            params={"query": query, "tags": "story", "hitsPerPage": 4},
        )
        response.raise_for_status()
        hits = response.json().get("hits", [])
        return [
            {
                "title": _clean(hit.get("title") or "", 180),
                "snippet": _clean(re.sub(r"<[^>]+>", " ", hit.get("story_text") or hit.get("title") or ""), 220),
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                "source": "Hacker News",
                "points": hit.get("points") or 0,
                "published": (hit.get("created_at") or "")[:10],
            }
            for hit in hits[:4]
        ]


async def _search_stackexchange(query: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=SOURCE_TIMEOUT_SECONDS) as client:
        response = await client.get(
            "https://api.stackexchange.com/2.3/search/advanced",
            params={
                "order": "desc", "sort": "relevance", "q": query,
                "site": "stackoverflow", "pagesize": 3, "filter": "withbody",
            },
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        return [
            {
                "title": _clean(re.sub(r"<[^>]+>", "", item.get("title", "")), 180),
                "snippet": _clean(re.sub(r"<[^>]+>", " ", item.get("excerpt") or item.get("body") or "")),
                "url": item.get("link", ""),
                "source": "Stack Overflow",
                "score": item.get("score", 0),
                "tags": ", ".join((item.get("tags") or [])[:4]),
            }
            for item in items[:3]
        ]


async def _search_youcom(query: str, count: int) -> list[dict[str, Any]]:
    from ..providers.youcom import YouComClient, YouComError

    settings = get_settings()
    if not settings.youcom_configured:
        return []
    try:
        result = await YouComClient(settings).search(query, count=count, extraction_mode="highlights")
    except YouComError:
        return []
    items: list[dict[str, Any]] = []
    for source in (result.get("sources") or [])[:count]:
        highlights = source.get("highlights") or source.get("snippets") or []
        if isinstance(highlights, list) and highlights:
            snippet = _clean(" ".join(str(h) for h in highlights[:2])[:900])
        else:
            snippet = _clean(str(source.get("snippet") or ""))
        items.append({
            "title": _clean(source.get("title") or "", 180),
            "snippet": snippet,
            "url": source.get("url") or source.get("link") or "",
            "source": "You.com Web",
        })
    return items


SOURCE_RUNNERS = {
    "youcombined": _search_youcom,
    "wikipedia": _search_wikipedia,
    "arxiv": _search_arxiv,
    "github": _search_github,
    "hackernews": _search_hackernews,
    "stackoverflow": _search_stackexchange,
}


async def _run_source(name: str, query: str, count: int) -> tuple[str, list[dict[str, Any]], str | None]:
    try:
        runner = SOURCE_RUNNERS[name]
        if name == "youcombined":
            items = await asyncio.wait_for(runner(query, count), timeout=SOURCE_TIMEOUT_SECONDS + 4)
        else:
            items = await asyncio.wait_for(runner(query), timeout=SOURCE_TIMEOUT_SECONDS + 4)
        return name, items or [], None
    except asyncio.TimeoutError:
        return name, [], "timed out"
    except Exception as error:  # noqa: BLE001 - per-source failure is surfaced, never fatal
        return name, [], _clean(str(error), 160)


def _compose_report(topic: str, per_source: dict[str, list[dict[str, Any]]], statuses: dict[str, str | None]) -> str:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    round_no = 0
    # Round-robin merge keeps every represented source near the top.
    while True:
        progressed = False
        for source in ["youcombined", "wikipedia", "arxiv", "github", "hackernews", "stackoverflow"]:
            items = per_source.get(source) or []
            if round_no < len(items):
                progressed = True
                item = items[round_no]
                key = _dedupe_key(item)
                if key and key not in seen:
                    seen.add(key)
                    merged.append(item)
        round_no += 1
        if not progressed:
            break

    lines = [f"## Research brief — {topic}", ""]
    if not merged:
        lines.append("No corroborating sources answered this pass. Each source ran independently and failed or timed out; try narrowing the topic.")
        return "\n".join(lines)

    lines.append(f"{len(merged)} independent findings across {sum(1 for v in per_source.values() if v)} live sources:")
    lines.append("")
    for index, item in enumerate(merged[:20], start=1):
        label = item.get("source", "web")
        title = item.get("title") or item.get("url") or "untitled"
        lines.append(f"**[{index}]** {title} — *{label}*  ")
        if item.get("snippet"):
            lines.append(f"{item['snippet']}  ")
        if item.get("url"):
            lines.append(f"<{item['url']}>")
        lines.append("")
    failures = [f"{name} ({why})" for name, why in statuses.items() if why]
    if failures:
        lines.append(f"_Sources that did not answer: {', '.join(failures)}._")
    return "\n".join(lines)


async def deep_research_handler(params: dict[str, Any]) -> dict[str, Any]:
    topic = str(params.get("topic") or params.get("query") or "").strip()
    if not topic:
        return {"status": "error", "error": "A research topic is required.", "code": "RESEARCH_EMPTY_QUERY"}

    depth = max(4, min(int(params.get("depth", 20) or 20), 24))
    per_source_count = max(2, min(depth // max(len(SOURCE_RUNNERS), 1), MAX_ITEMS_PER_SOURCE))

    started = time.perf_counter()
    names = list(SOURCE_RUNNERS.keys())
    outcomes = await asyncio.gather(*(_run_source(name, topic, per_source_count) for name in names))

    per_source: dict[str, list[dict[str, Any]]] = {}
    statuses: dict[str, str | None] = {}
    sources_view: list[dict[str, Any]] = []
    for name, items, error in outcomes:  # type: ignore[misc]
        per_source[name] = items
        statuses[name] = error
        sources_view.append({
            "id": name,
            "label": {"youcombined": "You.com", "stackoverflow": "Stack Overflow"}.get(name, name.title()),
            "count": len(items),
            "status": "failed" if error else ("ok" if items else "empty"),
            "error": error,
        })

    all_items = [item for items in per_source.values() for item in items]
    report = _compose_report(topic, per_source, statuses)
    return {
        "status": "success",
        "topic": topic,
        "depth": depth,
        "findingCount": len(all_items),
        "sources": sources_view,
        "items": all_items[:24],
        "report": report,
        "elapsedMs": int((time.perf_counter() - started) * 1000),
    }


deep_research_def = ToolDefinition(
    name="deep_research",
    display_name="Deep research",
    description=(
        "Fan out a research topic across parallel independent sources (You.com web, Wikipedia, "
        "arXiv, GitHub, Hacker News, Stack Overflow), merge cited findings, and return a "
        "structured research brief. Use when the user asks to research a topic deeply or wants "
        "a multi-source, cited overview."
    ),
    parameters={
        "topic": {"type": "string", "description": "The subject to research"},
        "depth": {"type": "number", "description": "Target finding count 4-24; default 20"},
    },
    required_parameters=["topic"],
    requires_confirmation=True,
    cancellable=True,
    voice_aliases=["research this", "deep research", "find everything about", "investigate"],
)

registry.register(deep_research_def, deep_research_handler)
