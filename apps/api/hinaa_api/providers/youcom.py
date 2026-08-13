"""Private You.com Platform client for HINAA's grounded web capabilities.

The API key remains server-side in ``apps/api/.env.local`` as ``YDC_API_KEY``.
This module normalizes provider payloads into bounded source records so tool results
can be rendered by HINAA without exposing response headers or unbounded page data.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from ..config import Settings

SearchExtraction = Literal["highlights", "full_page"]
ResearchEffort = Literal["lite", "standard", "deep", "exhaustive", "frontier"]
FinanceResearchEffort = Literal["deep", "exhaustive"]


class YouComError(RuntimeError):
    """A safe, user-displayable You.com integration failure."""

    def __init__(self, code: str, message: str, *, status_code: int | None = None) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class YouComImage:
    id: str
    title: str
    image_url: str
    page_url: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "id": self.id,
            "title": self.title,
            "imageUrl": self.image_url,
            "pageUrl": self.page_url,
        }


@dataclass(frozen=True)
class YouComSource:
    id: str
    title: str
    url: str
    snippet: str = ""
    published_date: str | None = None
    kind: str = "web"

    def as_dict(self) -> dict[str, str | None]:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "publishedDate": self.published_date,
            "kind": self.kind,
        }


def _bounded_text(value: object, limit: int = 1_200) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else f"{text[: limit - 1].rstrip()}…"


def _first_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return next((str(item) for item in value if isinstance(item, str) and item.strip()), "")
    return ""


def _extract_snippet(result: dict[str, Any]) -> str:
    contents = result.get("contents")
    if isinstance(contents, dict):
        highlights = _first_text(contents.get("highlights"))
        if highlights:
            return _bounded_text(highlights)
        markdown = _first_text(contents.get("markdown"))
        if markdown:
            return _bounded_text(markdown)
    return _bounded_text(
        _first_text(result.get("snippets"))
        or result.get("description")
        or result.get("snippet")
        or ""
    )


def _sources_from_result_groups(payload: dict[str, Any]) -> list[YouComSource]:
    raw_results = payload.get("results")
    groups = raw_results if isinstance(raw_results, dict) else payload
    if not isinstance(groups, dict):
        return []

    sources: list[YouComSource] = []
    seen: set[str] = set()
    for kind in ("web", "news"):
        items = groups.get(kind, [])
        if not isinstance(items, list):
            continue
        for result in items:
            if not isinstance(result, dict):
                continue
            url = str(result.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            title = _bounded_text(result.get("title") or url, 240)
            sources.append(
                YouComSource(
                    id=f"Y{len(sources) + 1}",
                    title=title or url,
                    url=url,
                    snippet=_extract_snippet(result),
                    published_date=_bounded_text(
                        result.get("published_date") or result.get("page_age") or "", 80
                    )
                    or None,
                    kind=kind,
                )
            )
    return sources


def _images_from_payload(payload: dict[str, Any], *, limit: int) -> list[YouComImage]:
    images = payload.get("images")
    records = images.get("results") if isinstance(images, dict) else []
    if not isinstance(records, list):
        return []
    normalized: list[YouComImage] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        image_url = str(record.get("image_url") or "").strip()
        if not image_url or image_url in seen or not _is_safe_external_url(image_url):
            continue
        seen.add(image_url)
        page_url = str(record.get("page_url") or "").strip()
        normalized.append(
            YouComImage(
                id=f"I{len(normalized) + 1}",
                title=_bounded_text(record.get("title") or "Untitled image", 240) or "Untitled image",
                image_url=image_url,
                page_url=page_url if _is_safe_external_url(page_url) else None,
            )
        )
        if len(normalized) >= limit:
            break
    return normalized


def _sources_from_citations(citations: object) -> list[YouComSource]:
    if not isinstance(citations, list):
        return []
    sources: list[YouComSource] = []
    seen: set[str] = set()
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        url = str(citation.get("source") or citation.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        sources.append(
            YouComSource(
                id=f"Y{len(sources) + 1}",
                title=_bounded_text(citation.get("title") or url, 240) or url,
                url=url,
                snippet=_bounded_text(_first_text(citation.get("excerpts")) or citation.get("snippet") or ""),
                kind="citation",
            )
        )
    return sources


def _sources_from_research_output(output: dict[str, Any]) -> list[YouComSource]:
    raw_sources = output.get("sources")
    if not isinstance(raw_sources, list):
        return []
    sources: list[YouComSource] = []
    seen: set[str] = set()
    for source in raw_sources:
        if not isinstance(source, dict):
            continue
        url = str(source.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        sources.append(
            YouComSource(
                id=f"Y{len(sources) + 1}",
                title=_bounded_text(source.get("title") or url, 240) or url,
                url=url,
                snippet=_bounded_text(_first_text(source.get("snippets")) or source.get("snippet") or ""),
                kind="research",
            )
        )
    return sources


def _is_safe_external_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        host = parsed.hostname.strip().lower().rstrip(".")
        if host == "localhost" or host.endswith(".local") or host.endswith(".internal"):
            return False
        try:
            address = ipaddress.ip_address(host)
            return not (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved)
        except ValueError:
            return True
    except ValueError:
        return False


class YouComClient:
    """Minimal HTTP client for You.com's verified REST endpoints."""

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport

    @property
    def configured(self) -> bool:
        return self.settings.youcom_configured

    def _headers(self) -> dict[str, str]:
        key = self.settings.youcom_api_key
        if not key or not key.get_secret_value():
            raise YouComError("YOUCOM_NOT_CONFIGURED", "You.com is not configured locally. Add YDC_API_KEY to apps/api/.env.local and restart HINAA.")
        return {"X-API-Key": key.get_secret_value(), "Content-Type": "application/json"}

    async def _request(
        self,
        *,
        base_url: str,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{base_url.rstrip('/')}{path}"
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.youcom_timeout_seconds,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = await client.request(method, url, headers=self._headers(), json=json, params=params)
        except httpx.TimeoutException as error:
            raise YouComError("YOUCOM_TIMEOUT", "You.com did not respond before HINAA's local timeout.") from error
        except httpx.HTTPError as error:
            raise YouComError("YOUCOM_UNAVAILABLE", "HINAA could not reach You.com right now.") from error

        if response.status_code >= 400:
            try:
                body = response.json()
            except ValueError:
                body = {}
            detail = _bounded_text(
                body.get("message") if isinstance(body, dict) else "",
                240,
            )
            if response.status_code in {401, 403}:
                message = "You.com rejected the local API key. Check YDC_API_KEY and its account permissions."
            elif response.status_code == 429:
                message = "You.com rate-limited this request. Please wait briefly and try again."
            elif response.status_code == 422:
                message = detail or "You.com rejected the requested search or research parameters."
            elif response.status_code >= 500:
                message = detail or f"You.com is temporarily unavailable (HTTP {response.status_code})."
                raise YouComError("YOUCOM_UPSTREAM_UNAVAILABLE", message, status_code=response.status_code)
            else:
                message = detail or f"You.com returned HTTP {response.status_code}."
            raise YouComError("YOUCOM_REQUEST_FAILED", message, status_code=response.status_code)

        try:
            return response.json()
        except ValueError as error:
            raise YouComError("YOUCOM_INVALID_RESPONSE", "You.com returned an unreadable response.") from error

    async def search(
        self,
        query: str,
        *,
        count: int = 5,
        freshness: str | None = None,
        country: str | None = None,
        language: str | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        boost_domains: list[str] | None = None,
        extraction_mode: SearchExtraction = "highlights",
    ) -> dict[str, Any]:
        cleaned = query.strip()
        if not cleaned:
            raise YouComError("YOUCOM_INVALID_QUERY", "A web-search query is required.")
        if include_domains and (exclude_domains or boost_domains):
            raise YouComError("YOUCOM_INVALID_FILTERS", "Choose include domains or exclude/boost domains, not both.")
        payload: dict[str, Any] = {
            "query": cleaned,
            "count": max(1, min(int(count), 20)),
            "extraction": {"extraction_mode": extraction_mode},
        }
        for key, value in {
            "freshness": freshness,
            "country": country,
            "language": language,
            "include_domains": include_domains,
            "exclude_domains": exclude_domains,
            "boost_domains": boost_domains,
        }.items():
            if value:
                payload[key] = value
        response = await self._request(
            base_url=self.settings.youcom_base_url,
            method="POST",
            path="/v1/search",
            json=payload,
        )
        if not isinstance(response, dict):
            raise YouComError("YOUCOM_INVALID_RESPONSE", "You.com returned an unexpected search response.")
        sources = _sources_from_result_groups(response)
        return {
            "provider": "you.com",
            "mode": "search",
            "query": cleaned,
            "results": [source.as_dict() for source in sources],
            "sources": [source.as_dict() for source in sources],
            "sourceCount": len(sources),
        }

    async def image_search(self, query: str, *, count: int = 6) -> dict[str, Any]:
        """Return public image URLs when the configured key has beta image access."""
        cleaned = query.strip()
        if not cleaned:
            raise YouComError("YOUCOM_INVALID_QUERY", "An image-search query is required.")
        try:
            response = await self._request(
                base_url=self.settings.youcom_base_url,
                method="GET",
                path="/v1/images",
                params={"q": cleaned},
            )
        except YouComError as error:
            if error.status_code == 403:
                raise YouComError(
                    "YOUCOM_IMAGE_ACCESS_REQUIRED",
                    "You.com image search is beta and this API key does not have early-access permission. Request image-search access from You.com or use HINAA's local ComfyUI generation.",
                    status_code=403,
                ) from error
            raise
        if not isinstance(response, dict):
            raise YouComError("YOUCOM_INVALID_RESPONSE", "You.com returned an unexpected image-search response.")
        images = _images_from_payload(response, limit=max(1, min(int(count), 12)))
        return {
            "provider": "you.com",
            "mode": "image-search-beta",
            "query": cleaned,
            "images": [image.as_dict() for image in images],
            "imageCount": len(images),
            "notice": "You.com image search is beta and availability can change. Results are public web image links; open their source pages to verify licensing and use rights.",
        }

    async def answer(self, query: str, **filters: Any) -> dict[str, Any]:
        cleaned = query.strip()
        if not cleaned:
            raise YouComError("YOUCOM_INVALID_QUERY", "A cited-answer query is required.")
        payload = {"query": cleaned, **{key: value for key, value in filters.items() if value}}
        response = await self._request(
            base_url=self.settings.youcom_base_url,
            method="POST",
            path="/v1/answer",
            json=payload,
        )
        if not isinstance(response, dict):
            raise YouComError("YOUCOM_INVALID_RESPONSE", "You.com returned an unexpected cited-answer response.")
        sources = _sources_from_citations(response.get("citations"))
        if not sources:
            sources = _sources_from_result_groups(response)
        return {
            "provider": "you.com",
            "mode": "answer",
            "query": cleaned,
            "content": _bounded_text(response.get("answer"), 20_000),
            "sources": [source.as_dict() for source in sources],
            "sourceCount": len(sources),
        }

    async def contents(self, urls: list[str], *, max_age: int | None = None) -> dict[str, Any]:
        selected = [url.strip() for url in urls if isinstance(url, str) and _is_safe_external_url(url.strip())][:5]
        if not selected:
            raise YouComError("YOUCOM_INVALID_URL", "Provide up to five public HTTP or HTTPS URLs; local and private network URLs are not allowed.")
        payload: dict[str, Any] = {"urls": selected, "formats": ["markdown", "metadata"], "crawl_timeout": 15}
        if max_age is not None:
            payload["max_age"] = max(0, int(max_age))
        response = await self._request(
            base_url=self.settings.youcom_contents_base_url,
            method="POST",
            path="/v1/contents",
            json=payload,
        )
        items = response if isinstance(response, list) else []
        sources: list[YouComSource] = []
        pages: list[dict[str, Any]] = []
        for item in items[:5]:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            title = _bounded_text(item.get("title") or url, 240) or url
            markdown = _bounded_text(item.get("markdown") or "", 8_000)
            source = YouComSource(
                id=f"Y{len(sources) + 1}",
                title=title,
                url=url,
                snippet=_bounded_text(markdown, 1_200),
                kind="contents",
            )
            sources.append(source)
            pages.append({"title": title, "url": url, "markdown": markdown, "metadata": item.get("metadata") or {}})
        return {
            "provider": "you.com",
            "mode": "contents",
            "pages": pages,
            "sources": [source.as_dict() for source in sources],
            "sourceCount": len(sources),
        }

    async def research(
        self,
        query: str,
        *,
        effort: ResearchEffort = "lite",
        background: bool = False,
        source_control: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cleaned = query.strip()
        if not cleaned:
            raise YouComError("YOUCOM_INVALID_QUERY", "A research question is required.")
        if effort not in {"lite", "standard", "deep", "exhaustive", "frontier"}:
            raise YouComError("YOUCOM_INVALID_EFFORT", "Use lite, standard, deep, exhaustive, or frontier research effort.")
        if effort == "frontier" and not background:
            raise YouComError("YOUCOM_BACKGROUND_REQUIRED", "Frontier research requires an explicit background task.")
        payload: dict[str, Any] = {"input": cleaned, "research_effort": effort, "background": background}
        if source_control:
            payload["source_control"] = source_control
        response = await self._request(
            base_url=self.settings.youcom_base_url,
            method="POST",
            path="/v1/research",
            json=payload,
        )
        if not isinstance(response, dict):
            raise YouComError("YOUCOM_INVALID_RESPONSE", "You.com returned an unexpected research response.")
        if background:
            return {
                "provider": "you.com",
                "mode": "research-task",
                "query": cleaned,
                "taskId": response.get("task_id"),
                "status": response.get("status"),
                "streamUrl": response.get("stream_url"),
            }
        output = response.get("output") if isinstance(response.get("output"), dict) else {}
        sources = _sources_from_research_output(output)
        return {
            "provider": "you.com",
            "mode": "research",
            "query": cleaned,
            "effort": effort,
            "content": _bounded_text(output.get("content"), 30_000),
            "sources": [source.as_dict() for source in sources],
            "warnings": [str(w) for w in output.get("warnings", []) if isinstance(w, str)][:10],
            "sourceCount": len(sources),
        }

    async def research_status(self, task_id: str) -> dict[str, Any]:
        cleaned = task_id.strip()
        if not cleaned or len(cleaned) > 200:
            raise YouComError("YOUCOM_INVALID_TASK", "A valid You.com research task ID is required.")
        response = await self._request(
            base_url=self.settings.youcom_base_url,
            method="GET",
            path=f"/v1/research/{cleaned}",
        )
        if not isinstance(response, dict):
            raise YouComError("YOUCOM_INVALID_RESPONSE", "You.com returned an unexpected research-task response.")
        result = response.get("result") if isinstance(response.get("result"), dict) else {}
        output = result.get("output") if isinstance(result.get("output"), dict) else {}
        sources = _sources_from_research_output(output)
        return {
            "provider": "you.com",
            "mode": "research-task",
            "taskId": cleaned,
            "status": response.get("status"),
            "content": _bounded_text(output.get("content"), 30_000),
            "sources": [source.as_dict() for source in sources],
            "sourceCount": len(sources),
            "error": _bounded_text(response.get("error"), 500) or None,
        }

    async def finance_research(self, query: str, *, effort: FinanceResearchEffort = "deep") -> dict[str, Any]:
        cleaned = query.strip()
        if not cleaned:
            raise YouComError("YOUCOM_INVALID_QUERY", "A financial research question is required.")
        if effort not in {"deep", "exhaustive"}:
            raise YouComError("YOUCOM_INVALID_EFFORT", "Finance research supports deep or exhaustive effort.")
        response = await self._request(
            base_url=self.settings.youcom_base_url,
            method="POST",
            path="/v1/finance_research",
            json={"input": cleaned, "research_effort": effort},
        )
        if not isinstance(response, dict):
            raise YouComError("YOUCOM_INVALID_RESPONSE", "You.com returned an unexpected finance-research response.")
        output = response.get("output") if isinstance(response.get("output"), dict) else {}
        sources = _sources_from_research_output(output)
        return {
            "provider": "you.com",
            "mode": "finance-research",
            "query": cleaned,
            "effort": effort,
            "content": _bounded_text(output.get("content"), 30_000),
            "sources": [source.as_dict() for source in sources],
            "sourceCount": len(sources),
            "notice": "Informational cited research only; not personalized investment or trade execution advice.",
        }
