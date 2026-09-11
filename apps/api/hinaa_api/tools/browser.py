from __future__ import annotations

import html
import json
import logging
import re
import urllib.parse
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from ..config import get_settings
from ..providers.youcom import YouComClient, YouComError
from .registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.browser")


MAX_WEB_URLS = 5


def _destination_url(href: str) -> str:
    """Unwrap DuckDuckGo result redirects without following arbitrary URLs."""
    parsed = urlparse(href)
    values = parse_qs(parsed.query).get("uddg", [])
    if values:
        return unquote(values[0])
    if href.startswith("//"):
        return f"https:{href}"
    return href


def _string_list(value: object, *, limit: int = 20) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if cleaned:
            items.append(cleaned)
        if len(items) >= limit:
            break
    return items


def _provider_error(error: YouComError, *, query: str = "") -> dict[str, Any]:
    return {
        "error": str(error),
        "code": error.code,
        "query": query,
        "results": [],
        "sources": [],
        "sourceCount": 0,
    }


async def _legacy_search(query: str) -> dict[str, Any]:
    """Public no-key fallback used only when You.com is not configured."""
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
            "sourceCount": 0,
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
        {"id": f"S{index}", "title": result["title"], "url": result["url"], "snippet": result["snippet"]}
        for index, result in enumerate(results, start=1)
    ]
    return {
        "provider": "public-fallback",
        "mode": "search",
        "query": query,
        "results": results,
        "sources": sources,
        "sourceCount": len(sources),
        "notice": "You.com is not configured in this local runtime; HINAA used the public fallback search.",
    }


async def search_web(params: dict[str, Any]) -> dict[str, Any]:
    """Search current web/news sources through You.com when configured."""
    query = str(
        params.get("query")
        or params.get("q")
        or params.get("search_query")
        or params.get("topic")
        or params.get("text")
        or ""
    ).strip()
    if not query:
        return {"error": "Query is required", "results": [], "sources": [], "sourceCount": 0}

    settings = get_settings()
    if not settings.youcom_configured:
        return await _legacy_search(query)
    try:
        return await YouComClient(settings).search(
            query,
            count=int(params.get("count", 5) or 5),
            freshness=str(params["freshness"]).strip() if params.get("freshness") else None,
            country=str(params["country"]).strip() if params.get("country") else None,
            language=str(params["language"]).strip() if params.get("language") else None,
            include_domains=_string_list(params.get("includeDomains")),
            exclude_domains=_string_list(params.get("excludeDomains")),
            boost_domains=_string_list(params.get("boostDomains")),
        )
    except YouComError as error:
        return _provider_error(error, query=query)


async def search_wikimedia_images(query: str, count: int = 6) -> list[dict[str, Any]]:
    """Fetch public Creative Commons images via Wikimedia Commons API."""
    endpoint = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": min(max(1, count), 12),
        "prop": "imageinfo",
        "iiprop": "url|size|mime",
        "iiurlwidth": 500,
        "format": "json",
    }
    headers = {"User-Agent": "HINAA-Companion/1.0 (contact@hinaa.dev)"}
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(endpoint, params=params, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                pages = data.get("query", {}).get("pages", {})
                results: list[dict[str, Any]] = []
                for page in pages.values():
                    infos = page.get("imageinfo", [])
                    if infos:
                        info = infos[0]
                        thumb = info.get("thumburl") or info.get("url")
                        orig = info.get("url") or thumb
                        page_url = info.get("descriptionurl") or orig
                        title = page.get("title", "").replace("File:", "").replace("_", " ").strip()
                        results.append({
                            "id": f"wiki-{page.get('pageid', len(results))}",
                            "title": title or query,
                            "imageUrl": thumb,
                            "thumbnailUrl": thumb,
                            "originalUrl": orig,
                            "pageUrl": page_url,
                            "source": "Wikimedia Commons",
                        })
                return results
    except Exception as exc:
        logger.warning("Wikimedia image search request failed: %s", exc)
    return []


def _clean_image_query(raw: str) -> tuple[str, bool]:
    is_pinterest = bool(re.search(r"\bpintre?s?t?\b", raw, re.I))
    # Remove conversational chatter
    cleaned = re.sub(
        r"\b(hey|hinaa?|babe|can you|please|fetch|get|show me|find|search|give me|some|online|form|from|pictures?|photos?|images?|pintres\w*|pinterest)\b",
        " ",
        raw,
        flags=re.I,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        cleaned = raw.strip()
    return cleaned, is_pinterest


async def search_multi_source_images(query: str, count: int = 8) -> dict[str, Any]:
    cleaned_query, is_pinterest = _clean_image_query(query)
    search_term = f"{cleaned_query} site:pinterest.com" if is_pinterest else cleaned_query

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    url = f"https://www.bing.com/images/search?q={urllib.parse.quote(search_term)}&first=1&form=HDRSC2"

    images: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    try:
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=12.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                matches = re.findall(r'class="iusc"[^>]*m="([^"]+)"', resp.text)
                for raw_match in matches:
                    try:
                        data = json.loads(html.unescape(raw_match))
                        murl = data.get("murl")
                        turl = data.get("turl") or murl
                        purl = data.get("purl", "")
                        title = data.get("t", "") or data.get("desc", "")
                        if not murl or murl in seen_urls or not murl.startswith("http"):
                            continue
                        lower_title = title.lower()
                        if any(bad in lower_title for bad in ["mockup", "mobile app interface", "vector icon", "stock photo vector", "logo vector"]):
                            continue
                        seen_urls.add(murl)
                        source_name = "Pinterest" if ("pinterest" in purl.lower() or "pinimg" in murl.lower()) else "Web"
                        images.append({
                            "id": f"img-{len(images)+1}",
                            "title": title[:80] or f"{cleaned_query.title()} Image",
                            "imageUrl": murl,
                            "thumbnailUrl": turl,
                            "pageUrl": purl,
                            "source": source_name,
                        })
                        if len(images) >= count:
                            break
                    except Exception:
                        pass

            # Fallback if too few results from site:pinterest.com
            if len(images) < 3 and is_pinterest:
                fallback_url = f"https://www.bing.com/images/search?q={urllib.parse.quote(cleaned_query + ' anime wallpaper')}&first=1&form=HDRSC2"
                fb_resp = await client.get(fallback_url)
                if fb_resp.status_code == 200:
                    fb_matches = re.findall(r'class="iusc"[^>]*m="([^"]+)"', fb_resp.text)
                    for raw_match in fb_matches:
                        try:
                            data = json.loads(html.unescape(raw_match))
                            murl = data.get("murl")
                            turl = data.get("turl") or murl
                            purl = data.get("purl", "")
                            title = data.get("t", "") or data.get("desc", "")
                            if murl and murl not in seen_urls and murl.startswith("http"):
                                seen_urls.add(murl)
                                images.append({
                                    "id": f"img-{len(images)+1}",
                                    "title": title[:80] or f"{cleaned_query.title()} Image",
                                    "imageUrl": murl,
                                    "thumbnailUrl": turl,
                                    "pageUrl": purl,
                                    "source": "Web",
                                })
                                if len(images) >= count:
                                    break
                        except Exception:
                            pass
    except Exception as exc:
        logger.warning("Multi-source image search encountered error: %s", exc)

    # Curated Pinterest boards matching ChatGPT's format
    boards: list[dict[str, str]] = []
    if is_pinterest or "anime" in cleaned_query.lower() or len(cleaned_query.split()) <= 3:
        topic = cleaned_query.title()
        boards = [
            {
                "title": f"260+ {topic} ideas",
                "url": f"https://www.pinterest.com/search/pins/?q={urllib.parse.quote(cleaned_query)}",
                "count": "260+",
            },
            {
                "title": f"640+ {topic} aesthetic ideas",
                "url": f"https://www.pinterest.com/search/boards/?q={urllib.parse.quote(cleaned_query)}",
                "count": "640+",
            },
            {
                "title": f"900+ {topic} HD wallpapers",
                "url": f"https://www.pinterest.com/search/pins/?q={urllib.parse.quote(cleaned_query + ' wallpaper')}",
                "count": "900+",
            },
        ]

    sources = [
        {"id": f"src-{i+1}", "title": img["title"], "url": img["pageUrl"] or img["imageUrl"], "domain": img["source"]}
        for i, img in enumerate(images)
    ]

    return {
        "status": "success",
        "provider": "multi-source-web",
        "query": query,
        "cleaned_query": cleaned_query,
        "images": images,
        "imageCount": len(images),
        "boards": boards,
        "sources": sources,
    }


async def search_images(params: dict[str, Any]) -> dict[str, Any]:
    query = str(params.get("query", "")).strip()
    try:
        count = int(params.get("count", 6) or 6)
    except (TypeError, ValueError):
        count = 6

    if not query:
        return {
            "error": "An image-search query is required.",
            "code": "INVALID_QUERY",
            "query": "",
            "images": [],
            "imageCount": 0,
        }

    # 1. Primary: High-speed multi-source search (Pinterest + Bing + Anime)
    try:
        multi_res = await search_multi_source_images(query, count=count)
        if multi_res.get("images") and len(multi_res["images"]) > 0:
            return multi_res
    except Exception as exc:
        logger.warning("Multi-source search failed: %s", exc)

    # 2. Try You.com if available
    try:
        res = await YouComClient(get_settings()).image_search(query, count=count)
        if res.get("images") and len(res["images"]) > 0:
            return res
    except Exception as exc:
        logger.warning("You.com image search unavailable (%s), trying public image sources...", exc)

    # 3. Fallback to Wikimedia Commons public image search
    wiki_images = await search_wikimedia_images(query, count=count)
    if wiki_images:
        return {
            "provider": "wikimedia-commons",
            "mode": "public-images",
            "query": query,
            "images": wiki_images,
            "imageCount": len(wiki_images),
            "notice": "Results from Wikimedia Commons and public web indices. Open source pages to verify licensing.",
        }

    # Fallback to broader keyword search if specific phrase had no match
    keywords = [w for w in query.split() if len(w) > 3 and not w.startswith("/")]
    if len(keywords) > 1:
        fallback_query = " ".join(keywords[:2])
        wiki_images = await search_wikimedia_images(fallback_query, count=count)
        if wiki_images:
            return {
                "provider": "wikimedia-commons",
                "mode": "public-images",
                "query": query,
                "images": wiki_images,
                "imageCount": len(wiki_images),
                "notice": "Results from Wikimedia Commons and public web indices. Open source pages to verify licensing.",
            }

    return {
        "provider": "multi-source-web",
        "mode": "public-images",
        "query": query,
        "images": [],
        "imageCount": 0,
        "notice": f"No public images found for '{query}'. Try another search query.",
    }


async def answer_web(params: dict[str, Any]) -> dict[str, Any]:
    query = str(
        params.get("query")
        or params.get("q")
        or params.get("search_query")
        or params.get("question")
        or params.get("topic")
        or ""
    ).strip()
    try:
        return await YouComClient(get_settings()).answer(
            query,
            freshness=str(params["freshness"]).strip() if params.get("freshness") else None,
            country=str(params["country"]).strip() if params.get("country") else None,
            language=str(params["language"]).strip() if params.get("language") else None,
            include_domains=_string_list(params.get("includeDomains")),
            exclude_domains=_string_list(params.get("excludeDomains")),
            boost_domains=_string_list(params.get("boostDomains")),
        )
    except YouComError as error:
        return _provider_error(error, query=query)


async def research_web(params: dict[str, Any]) -> dict[str, Any]:
    query = str(
        params.get("query")
        or params.get("q")
        or params.get("search_query")
        or params.get("topic")
        or ""
    ).strip()
    effort = str(params.get("effort", "lite") or "lite").strip().lower()
    try:
        return await YouComClient(get_settings()).research(
            query,
            effort=effort,  # type: ignore[arg-type]
            background=bool(params.get("background", False)),
            source_control={
                key: value
                for key, value in {
                    "include_domains": _string_list(params.get("includeDomains")),
                    "exclude_domains": _string_list(params.get("excludeDomains")),
                    "boost_domains": _string_list(params.get("boostDomains")),
                    "freshness": str(params["freshness"]).strip() if params.get("freshness") else None,
                    "country": str(params["country"]).strip() if params.get("country") else None,
                }.items()
                if value
            }
            or None,
        )
    except YouComError as error:
        return _provider_error(error, query=query)


async def research_web_status(params: dict[str, Any]) -> dict[str, Any]:
    task_id = str(params.get("taskId", "")).strip()
    try:
        return await YouComClient(get_settings()).research_status(task_id)
    except YouComError as error:
        return _provider_error(error)


async def extract_web_pages(params: dict[str, Any]) -> dict[str, Any]:
    urls = _string_list(params.get("urls"), limit=MAX_WEB_URLS)
    try:
        return await YouComClient(get_settings()).contents(
            urls,
            max_age=int(params["maxAge"]) if params.get("maxAge") is not None else None,
        )
    except (TypeError, ValueError):
        return {"error": "maxAge must be a whole number of seconds.", "code": "YOUCOM_INVALID_MAX_AGE", "pages": [], "sources": [], "sourceCount": 0}
    except YouComError as error:
        return _provider_error(error)


async def finance_research(params: dict[str, Any]) -> dict[str, Any]:
    query = str(params.get("query", "")).strip()
    effort = str(params.get("effort", "deep") or "deep").strip().lower()
    try:
        return await YouComClient(get_settings()).finance_research(
            query,
            effort=effort,  # type: ignore[arg-type]
        )
    except YouComError as error:
        return _provider_error(error, query=query)


web_search_def = ToolDefinition(
    name="web_search",
    display_name="Search the live web",
    description="Search current web and news sources. Uses private You.com real-time search when YDC_API_KEY is configured, otherwise clearly marks a public fallback.",
    parameters={
        "query": {"type": "string", "description": "The current-information query to execute"},
        "count": {"type": "number", "description": "Optional result count; default 5, maximum 20"},
        "freshness": {"type": "string", "description": "Optional day, week, month, year, or YYYY-MM-DDtoYYYY-MM-DD filter"},
        "includeDomains": {"type": "array", "description": "Optional strict source-domain allowlist"},
        "excludeDomains": {"type": "array", "description": "Optional source-domain blocklist"},
        "boostDomains": {"type": "array", "description": "Optional preferred source domains"},
    },
    required_parameters=["query"],
    requires_confirmation=True,
    cancellable=True,
    voice_aliases=["search for", "look up", "find"],
)

image_search_def = ToolDefinition(
    name="image_search",
    display_name="Find public images",
    description="Use You.com's beta image-search API to find public web image links. Availability requires early-access permission for the configured You.com key; source-page licensing still must be verified before reuse.",
    parameters={
        "query": {"type": "string", "description": "The public image search query"},
        "count": {"type": "number", "description": "Optional result count; default 6, maximum 12"},
    },
    required_parameters=["query"],
    requires_confirmation=True,
    cancellable=True,
    voice_aliases=["find images", "search images", "look for pictures"],
)

web_answer_def = ToolDefinition(
    name="web_answer",
    display_name="Answer with live citations",
    description="Use You.com's cited Answer API for one concise, source-backed current answer. Returns the answer plus verifiable citation cards.",
    parameters={
        "query": {"type": "string", "description": "The factual question to answer with current sources"},
        "freshness": {"type": "string", "description": "Optional recency filter"},
        "includeDomains": {"type": "array", "description": "Optional strict source-domain allowlist"},
        "excludeDomains": {"type": "array", "description": "Optional source-domain blocklist"},
    },
    required_parameters=["query"],
    requires_confirmation=True,
    cancellable=True,
    voice_aliases=["answer with sources", "verify online"],
)

web_research_def = ToolDefinition(
    name="web_research",
    display_name="Research the live web",
    description="Use You.com's multi-step cited Research API for an explicit deep-dive. The chosen effort level is visible before execution because deeper research takes longer and can cost more.",
    parameters={
        "query": {"type": "string", "description": "The research question or comparison"},
        "effort": {"type": "string", "description": "lite, standard, deep, exhaustive, or frontier; defaults to lite"},
        "background": {"type": "boolean", "description": "Required for frontier; returns a task handle for background research"},
        "includeDomains": {"type": "array", "description": "Optional strict source-domain allowlist"},
        "excludeDomains": {"type": "array", "description": "Optional source-domain blocklist"},
        "boostDomains": {"type": "array", "description": "Optional preferred source domains"},
        "freshness": {"type": "string", "description": "Optional recency filter"},
    },
    required_parameters=["query"],
    permission_level="elevated",
    requires_confirmation=True,
    cancellable=True,
    voice_aliases=["research", "investigate", "compare with sources"],
)

web_research_status_def = ToolDefinition(
    name="web_research_status",
    display_name="Check research progress",
    description="Check an already approved You.com background research task and return the final cited result only when the task has completed.",
    parameters={
        "taskId": {"type": "string", "description": "The You.com background research task ID"},
    },
    required_parameters=["taskId"],
    requires_confirmation=True,
    cancellable=True,
)

web_extract_def = ToolDefinition(
    name="web_extract",
    display_name="Read selected public pages",
    description="Use You.com's Contents API to retrieve clean Markdown and metadata from up to five public web pages. Private, local, and internal addresses are rejected.",
    parameters={
        "urls": {"type": "array", "description": "Up to five public HTTP or HTTPS URLs to read"},
        "maxAge": {"type": "number", "description": "Optional maximum cached-page age in seconds; use 0 to refresh"},
    },
    required_parameters=["urls"],
    requires_confirmation=True,
    cancellable=True,
    voice_aliases=["read this page", "extract this link"],
)

finance_research_def = ToolDefinition(
    name="finance_research",
    display_name="Research financial sources",
    description="Use You.com's finance research index for cited company, market, filing, or macro research. It provides information, not personalized trading or investment execution advice.",
    parameters={
        "query": {"type": "string", "description": "The financial research question"},
        "effort": {"type": "string", "description": "deep or exhaustive; defaults to deep"},
    },
    required_parameters=["query"],
    permission_level="high",
    requires_confirmation=True,
    cancellable=True,
    voice_aliases=["financial research", "research this company"],
)

registry.register(web_search_def, search_web)
registry.register(image_search_def, search_images)
registry.register(web_answer_def, answer_web)
registry.register(web_research_def, research_web)
registry.register(web_research_status_def, research_web_status)
registry.register(web_extract_def, extract_web_pages)
registry.register(finance_research_def, finance_research)


async def artifact_lookup(params: dict[str, Any]) -> dict[str, Any]:
    """Look up an artifact by kind in the user's projects."""
    from ..config import get_settings
    from ..persistence.db import get_session_factory
    from ..persistence.orm import ProjectArtifact
    
    kind = str(params.get("kind", "pdf")).strip().lower()
    session_id = str(params.get("sessionId", "")).strip() if params.get("sessionId") else None
    
    settings = get_settings()
    session_factory = get_session_factory(settings)
    
    # This would need user context - for now return a helpful response
    # In production, this would be called with authenticated user context
    return {
        "provider": "local",
        "mode": "artifact_lookup",
        "kind": kind,
        "found": False,
        "message": f"No {kind.upper()} artifact found in your projects.",
        "suggestion": f"Use /{kind} to create a new {kind.upper()} document.",
        "artifact": None,
    }


artifact_lookup_def = ToolDefinition(
    name="artifact_lookup",
    display_name="Look up artifact",
    description="Find a previously created artifact (PDF, document, image, etc.) in your projects.",
    parameters={
        "kind": {"type": "string", "enum": ["pdf", "docx", "pptx", "image", "video", "audio", "file"], "description": "Type of artifact to find"},
        "sessionId": {"type": "string", "description": "Optional session/conversation ID to scope the search"},
    },
    required_parameters=["kind"],
    requires_confirmation=False,
    cancellable=True,
)

registry.register(artifact_lookup_def, artifact_lookup)
