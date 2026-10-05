"""Exa API integration — semantic web retrieval and content extraction for HINAA.

Built following the official 'build-with-exa' skill guidance:
- Canonical endpoints:
  - POST /search: Semantic search with token-efficient bare highlights: {"highlights": True}.
  - POST /contents: Clean known-URL content extraction with top-level fields.
- SDK: Uses official exa-py SDK (snake_case keyword arguments) with non-blocking async execution.
- Coding Agent: Tailored semantic retrieval for documentation, APIs, and stack trace investigation.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from exa_py import Exa

from ..config import get_settings
from .registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.exa")


def _extract_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc or "Web"
    except Exception:
        return "Web"


class ExaClient:
    """Thread-safe, non-blocking client for the Exa API."""

    def __init__(self, api_key: str | None = None, base_url: str = "https://api.exa.ai"):
        settings = get_settings()
        self.api_key = (
            api_key
            if api_key is not None
            else (settings.exa_api_key.get_secret_value() if settings.exa_api_key else "")
        )
        self.base_url = base_url.rstrip("/")
        self.timeout = settings.exa_timeout_seconds
        self._sdk: Exa | None = None
        if self.api_key:
            try:
                self._sdk = Exa(api_key=self.api_key)
            except Exception as exc:
                logger.warning("Failed to initialize exa-py SDK: %s", exc)

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def search(
        self,
        query: str,
        *,
        search_type: str = "auto",
        num_results: int = 10,
        highlights: bool = True,
        text: bool = False,
    ) -> dict[str, Any]:
        """Execute a semantic search query on Exa following build-with-exa canonical rules.

        - Default search type is 'auto'.
        - Content extraction defaults to bare highlights: True for token efficiency.
        - Keyword arguments to exa-py use strict snake_case.
        """
        if not self.is_configured:
            return {
                "error": "EXA_API_KEY is not configured",
                "provider": "exa",
                "results": [],
                "sources": [],
                "sourceCount": 0,
            }

        cleaned_query = (query or "").strip()
        if not cleaned_query:
            return {
                "error": "Query is required",
                "provider": "exa",
                "results": [],
                "sources": [],
                "sourceCount": 0,
            }

        # Build contents payload per canonical skill rules
        contents_kwargs: dict[str, Any] = {}
        if highlights and not text:
            contents_kwargs["highlights"] = True
        elif text:
            contents_kwargs["text"] = True

        # Use exa-py SDK in threadpool to keep asyncio event loop unblocked
        if self._sdk:
            try:
                def _do_sdk_search():
                    kwargs: dict[str, Any] = {
                        "type": search_type,
                        "num_results": min(max(num_results, 1), 50),
                    }
                    if contents_kwargs:
                        kwargs["contents"] = contents_kwargs
                    return self._sdk.search(cleaned_query, **kwargs)

                response = await asyncio.to_thread(_do_sdk_search)
                return self._format_sdk_results(cleaned_query, response)
            except Exception as exc:
                logger.warning("exa-py SDK search failed, falling back to HTTP: %s", exc)

        # Direct HTTP fallback
        return await self._http_search(
            cleaned_query,
            search_type=search_type,
            num_results=num_results,
            contents=contents_kwargs,
        )

    def _format_sdk_results(self, query: str, response: Any) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []

        items = getattr(response, "results", []) or []
        for index, item in enumerate(items, start=1):
            url = getattr(item, "url", "")
            title = getattr(item, "title", "") or url
            author = getattr(item, "author", None)
            published_date = getattr(item, "published_date", None)

            # Extract snippet from highlights or text
            hl = getattr(item, "highlights", None)
            txt = getattr(item, "text", None)
            snippet = ""
            if isinstance(hl, list) and hl:
                snippet = " ... ".join(str(h) for h in hl if h)
            elif txt:
                snippet = str(txt)[:400].strip()

            domain = _extract_domain(url)
            res_dict = {
                "id": f"S{index}",
                "title": title,
                "url": url,
                "domain": domain,
                "snippet": snippet,
                "author": author,
                "published_date": published_date,
                "highlights": hl if isinstance(hl, list) else [],
            }
            results.append(res_dict)
            sources.append(res_dict)

        return {
            "provider": "exa",
            "mode": "search",
            "query": query,
            "results": results,
            "sources": sources,
            "sourceCount": len(sources),
        }

    async def _http_search(
        self,
        query: str,
        *,
        search_type: str = "auto",
        num_results: int = 10,
        contents: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/search"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }
        body: dict[str, Any] = {
            "query": query,
            "type": search_type,
            "numResults": min(max(num_results, 1), 50),
        }
        if contents:
            body["contents"] = contents

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, headers=headers, json=body)
                res.raise_for_status()
                data = res.json()

            results: list[dict[str, Any]] = []
            sources: list[dict[str, Any]] = []
            for index, item in enumerate(data.get("results", []), start=1):
                item_url = item.get("url", "")
                title = item.get("title") or item_url
                hl = item.get("highlights", [])
                txt = item.get("text", "")
                snippet = " ... ".join(hl) if hl else (txt[:400] if txt else "")
                domain = _extract_domain(item_url)
                entry = {
                    "id": f"S{index}",
                    "title": title,
                    "url": item_url,
                    "domain": domain,
                    "snippet": snippet,
                    "author": item.get("author"),
                    "published_date": item.get("publishedDate"),
                    "highlights": hl,
                }
                results.append(entry)
                sources.append(entry)

            return {
                "provider": "exa",
                "mode": "search",
                "query": query,
                "results": results,
                "sources": sources,
                "sourceCount": len(sources),
            }
        except Exception as exc:
            logger.error("Exa HTTP search failed: %s", exc)
            return {
                "error": str(exc),
                "provider": "exa",
                "query": query,
                "results": [],
                "sources": [],
                "sourceCount": 0,
            }

    async def get_contents(
        self,
        urls: list[str],
        *,
        text: bool = True,
        highlights: bool = False,
    ) -> dict[str, Any]:
        """Extract clean content from known URLs via Exa /contents endpoint.

        Per build-with-exa spec:
        On the contents endpoint, text and highlights are top-level fields (not nested in contents).
        """
        if not self.is_configured:
            return {"error": "EXA_API_KEY is not configured", "results": []}

        if not urls:
            return {"error": "urls list is required", "results": []}

        # SDK execution
        if self._sdk:
            try:
                def _do_sdk_contents():
                    return self._sdk.get_contents(urls, text=text, highlights=highlights)

                response = await asyncio.to_thread(_do_sdk_contents)
                items = getattr(response, "results", []) or []
                extracted = []
                for item in items:
                    extracted.append({
                        "url": getattr(item, "url", ""),
                        "title": getattr(item, "title", ""),
                        "text": getattr(item, "text", ""),
                        "highlights": getattr(item, "highlights", []),
                    })
                return {"provider": "exa", "mode": "contents", "results": extracted}
            except Exception as exc:
                logger.warning("exa-py get_contents failed, falling back to HTTP: %s", exc)

        # Direct HTTP
        url = f"{self.base_url}/contents"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }
        body: dict[str, Any] = {"urls": urls}
        if text:
            body["text"] = True
        if highlights:
            body["highlights"] = True

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, headers=headers, json=body)
                res.raise_for_status()
                data = res.json()
                return {"provider": "exa", "mode": "contents", "results": data.get("results", [])}
        except Exception as exc:
            logger.error("Exa HTTP contents failed: %s", exc)
            return {"error": str(exc), "provider": "exa", "results": []}

    async def run_agent(
        self,
        query: str,
        *,
        effort: str = "auto",
        output_schema: dict[str, Any] | None = None,
        system_prompt: str | None = None,
        input_data: list[dict[str, Any]] | None = None,
        input_exclusion: list[dict[str, Any]] | None = None,
        previous_run_id: str | None = None,
        budget_max_cost: float | None = None,
        data_sources: list[dict[str, Any]] | None = None,
        poll_interval_seconds: float = 3.0,
        timeout_seconds: float = 120.0,
    ) -> dict[str, Any]:
        """Run deep multi-step research, list-building, or entity enrichment via Exa Agent.

        Follows canonical build-with-exa and Exa Agent guide:
        - POST /agent/runs: starts an async run.
        - GET /agent/runs/{id}: polls until status is 'completed', 'failed', or 'cancelled'.
        - Effort: minimal, low, medium, high, xhigh, auto, or ultra.
        - Output: output.text, output.structured, output.grounding citations.
        """
        if not self.is_configured:
            return {"error": "EXA_API_KEY is not configured", "status": "failed"}

        cleaned_query = (query or "").strip()
        if not cleaned_query:
            return {"error": "Query is required for Exa Agent run", "status": "failed"}

        # Attempt with exa-py SDK
        if self._sdk and hasattr(self._sdk, "agent") and hasattr(self._sdk.agent, "runs"):
            try:
                def _do_sdk_agent():
                    create_kwargs: dict[str, Any] = {
                        "query": cleaned_query,
                        "effort": effort,
                    }
                    if output_schema:
                        create_kwargs["output_schema"] = output_schema
                    if system_prompt:
                        create_kwargs["system_prompt"] = system_prompt
                    inp: dict[str, Any] = {}
                    if input_data:
                        inp["data"] = input_data
                    if input_exclusion:
                        inp["exclusion"] = input_exclusion
                    if inp:
                        create_kwargs["input"] = inp
                    if previous_run_id:
                        create_kwargs["previous_run_id"] = previous_run_id
                    if budget_max_cost is not None and effort in {"auto", "ultra"}:
                        create_kwargs["budget"] = {"max_cost_dollars": budget_max_cost}
                    if data_sources:
                        create_kwargs["data_sources"] = data_sources

                    run = self._sdk.agent.runs.create(**create_kwargs)
                    run_id = getattr(run, "id", None) or (run.get("id") if isinstance(run, dict) else None)
                    if not run_id:
                        raise ValueError("No run ID returned from Exa Agent create")

                    finished = self._sdk.agent.runs.poll_until_finished(
                        run_id,
                        poll_interval=int(poll_interval_seconds * 1000),
                    )
                    return finished

                res = await asyncio.to_thread(_do_sdk_agent)
                return self._format_agent_results(res)
            except Exception as exc:
                logger.warning("exa-py agent run via SDK failed, falling back to HTTP: %s", exc)

        # Direct HTTP fallback
        return await self._http_agent_run(
            query=cleaned_query,
            effort=effort,
            output_schema=output_schema,
            system_prompt=system_prompt,
            input_data=input_data,
            input_exclusion=input_exclusion,
            previous_run_id=previous_run_id,
            budget_max_cost=budget_max_cost,
            data_sources=data_sources,
            poll_interval_seconds=poll_interval_seconds,
            timeout_seconds=timeout_seconds,
        )

    def _format_agent_results(self, run: Any) -> dict[str, Any]:
        if isinstance(run, dict):
            run_id = run.get("id", "")
            status = run.get("status", "unknown")
            output = run.get("output") or {}
            cost = run.get("costDollars") or run.get("cost_dollars")
            error = run.get("error")
        else:
            run_id = getattr(run, "id", "")
            status = getattr(run, "status", "unknown")
            output_obj = getattr(run, "output", None)
            cost = getattr(run, "cost_dollars", None) or getattr(run, "costDollars", None)
            error = getattr(run, "error", None)
            if isinstance(output_obj, dict):
                output = output_obj
            elif hasattr(output_obj, "model_dump") and callable(getattr(output_obj, "model_dump")):
                try:
                    dumped = output_obj.model_dump()
                    output = dumped if isinstance(dumped, dict) else {
                        "text": getattr(output_obj, "text", ""),
                        "structured": getattr(output_obj, "structured", None),
                        "grounding": getattr(output_obj, "grounding", None),
                    }
                except Exception:
                    output = {
                        "text": getattr(output_obj, "text", ""),
                        "structured": getattr(output_obj, "structured", None),
                        "grounding": getattr(output_obj, "grounding", None),
                    }
            else:
                output = {
                    "text": getattr(output_obj, "text", "") if output_obj else "",
                    "structured": getattr(output_obj, "structured", None) if output_obj else None,
                    "grounding": getattr(output_obj, "grounding", None) if output_obj else None,
                }

        text = output.get("text", "") if isinstance(output, dict) else str(output or "")
        structured = output.get("structured") if isinstance(output, dict) else None
        grounding = output.get("grounding") if isinstance(output, dict) else None

        return {
            "provider": "exa-agent",
            "runId": run_id,
            "status": status,
            "text": text,
            "structured": structured,
            "grounding": grounding,
            "costDollars": cost,
            "error": error if status != "completed" else None,
        }

    async def _http_agent_run(
        self,
        query: str,
        effort: str = "auto",
        output_schema: dict[str, Any] | None = None,
        system_prompt: str | None = None,
        input_data: list[dict[str, Any]] | None = None,
        input_exclusion: list[dict[str, Any]] | None = None,
        previous_run_id: str | None = None,
        budget_max_cost: float | None = None,
        data_sources: list[dict[str, Any]] | None = None,
        poll_interval_seconds: float = 3.0,
        timeout_seconds: float = 120.0,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/agent/runs"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }
        body: dict[str, Any] = {
            "query": query,
            "effort": effort,
        }
        if output_schema:
            body["outputSchema"] = output_schema
        if system_prompt:
            body["systemPrompt"] = system_prompt
        inp: dict[str, Any] = {}
        if input_data:
            inp["data"] = input_data
        if input_exclusion:
            inp["exclusion"] = input_exclusion
        if inp:
            body["input"] = inp
        if previous_run_id:
            body["previousRunId"] = previous_run_id
        if budget_max_cost is not None and effort in {"auto", "ultra"}:
            body["budget"] = {"maxCostDollars": budget_max_cost}
        if data_sources:
            body["dataSources"] = data_sources

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            create_data = resp.json()
            run_id = create_data.get("id")
            if not run_id:
                return {"error": "Failed to create Exa Agent run: no run ID returned", "status": "failed"}

            poll_url = f"{self.base_url}/agent/runs/{run_id}"
            elapsed = 0.0
            while elapsed < timeout_seconds:
                await asyncio.sleep(poll_interval_seconds)
                elapsed += poll_interval_seconds
                poll_resp = await client.get(poll_url, headers=headers)
                if poll_resp.status_code == 200:
                    poll_data = poll_resp.json()
                    status = poll_data.get("status")
                    if status in {"completed", "failed", "cancelled"}:
                        return self._format_agent_results(poll_data)

            return {
                "error": f"Exa Agent run timed out after {timeout_seconds}s",
                "runId": run_id,
                "status": "timeout",
            }



# Global client instance
exa_client = ExaClient()


# Tool Handlers for ToolRegistry
async def exa_search_tool(params: dict[str, Any] | str) -> dict[str, Any]:
    """Execute an Exa web search for live facts, documentation, or code libraries."""
    if isinstance(params, str):
        params = {"query": params}
    query = str(params.get("query") or params.get("q") or "").strip()
    num_results = int(params.get("count") or params.get("numResults") or 10)
    search_type = str(params.get("type", "auto")).strip()
    return await exa_client.search(
        query,
        search_type=search_type,
        num_results=num_results,
        highlights=True,
    )


async def exa_get_contents_tool(params: dict[str, Any]) -> dict[str, Any]:
    """Extract clean content from known URLs using Exa."""
    urls = params.get("urls") or []
    if isinstance(urls, str):
        urls = [urls]
    return await exa_client.get_contents(urls, text=True)


# Register tools
exa_search_def = ToolDefinition(
    name="exa_search",
    display_name="Search the live web with Exa",
    description="Search the live web and developer documentation for up-to-date information, libraries, APIs, and fixes using Exa's semantic retrieval.",
    parameters={
        "query": {"type": "string", "description": "The search query to execute"},
        "count": {"type": "number", "description": "Optional result count (default 10)"},
    },
    required_parameters=["query"],
    requires_confirmation=False,
    cancellable=True,
    voice_aliases=["search web with exa", "look up with exa", "exa search"],
)

exa_get_contents_def = ToolDefinition(
    name="exa_get_contents",
    display_name="Read web pages with Exa",
    description="Extract clean text and documentation from public URLs using Exa's content extraction.",
    parameters={
        "urls": {"type": "array", "description": "List of public HTTP/HTTPS URLs to extract"},
    },
    required_parameters=["urls"],
    requires_confirmation=False,
    cancellable=True,
    voice_aliases=["read pages with exa", "extract url with exa"],
)

registry.register(exa_search_def, exa_search_tool)
registry.register(exa_get_contents_def, exa_get_contents_tool)


async def exa_agent_run_tool(params: dict[str, Any] | str) -> dict[str, Any]:
    """Execute an Exa Agent run for deep multi-step research, list building, or entity enrichment."""
    if isinstance(params, str):
        params = {"query": params}
    query = str(params.get("query") or params.get("q") or "").strip()
    effort = str(params.get("effort", "auto")).strip()
    output_schema = params.get("output_schema") or params.get("outputSchema")
    system_prompt = params.get("system_prompt") or params.get("systemPrompt")
    input_data = params.get("input_data") or params.get("data")
    input_exclusion = params.get("input_exclusion") or params.get("exclusion")
    previous_run_id = params.get("previous_run_id") or params.get("previousRunId")
    budget_max_cost = params.get("budget_max_cost") or params.get("budget")
    if isinstance(budget_max_cost, dict):
        budget_max_cost = budget_max_cost.get("maxCostDollars") or budget_max_cost.get("max_cost_dollars")
    data_sources = params.get("data_sources") or params.get("dataSources")

    return await exa_client.run_agent(
        query,
        effort=effort,
        output_schema=output_schema,
        system_prompt=system_prompt,
        input_data=input_data,
        input_exclusion=input_exclusion,
        previous_run_id=previous_run_id,
        budget_max_cost=float(budget_max_cost) if budget_max_cost is not None else None,
        data_sources=data_sources,
    )


exa_agent_run_def = ToolDefinition(
    name="exa_agent_run",
    display_name="Exa Agent Deep Research & List Builder",
    description="Run deep asynchronous multi-step web research, entity verification, list-building, and structured enrichment using Exa Agent.",
    parameters={
        "query": {"type": "string", "description": "The research task, list-building prompt, or entity inspection query"},
        "effort": {"type": "string", "description": "Reasoning effort: minimal, low, medium, high, xhigh, auto, or ultra (default 'auto')"},
        "output_schema": {"type": "object", "description": "Optional JSON Schema for structured output"},
        "system_prompt": {"type": "string", "description": "Optional behavioral or verification guidance for the agent"},
    },
    required_parameters=["query"],
    requires_confirmation=False,
    cancellable=True,
    voice_aliases=["deep research with exa", "exa agent run", "research with exa agent"],
)

registry.register(exa_agent_run_def, exa_agent_run_tool)

