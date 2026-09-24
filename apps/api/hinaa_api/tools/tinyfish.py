import ipaddress
import urllib.parse
import httpx
from pydantic import BaseModel, Field

from hinaa_api.tools.registry import ToolDefinition, registry

class TinyfishSearchParams(BaseModel):
    query: str = Field(..., description="The web search query.")
    limit: int = Field(5, description="Number of results to return (max 10).")

class TinyfishFetchParams(BaseModel):
    urls: list[str] = Field(..., description="List of public HTTP(S) URLs to fetch (max 5).")

def _is_public_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        if hostname == "localhost":
            return False
        
        # Check if it's an IP address and if it's private
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            pass # Not an IP address, probably a valid domain
            
        return True
    except Exception:
        return False

async def tinyfish_search_handler(params: dict, context: dict) -> dict:
    # Context should provide settings
    settings = context.get("settings")
    if not settings or not settings.tinyfish_api_key:
        return {"error": "TinyFish API key is not configured (TINYFISH_API_KEY)."}
    
    query = params.get("query", "")
    limit = min(params.get("limit", 5), 10)
    
    url = "https://api.tinyfish.ai/v1/search"
    headers = {"X-API-Key": settings.tinyfish_api_key}
    
    timeout = getattr(settings, "tinyfish_search_timeout_seconds", 10.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json={"query": query, "limit": limit}, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": f"TinyFish search failed: {e}"}

async def tinyfish_fetch_handler(params: dict, context: dict) -> dict:
    settings = context.get("settings")
    if not settings or not settings.tinyfish_api_key:
        return {"error": "TinyFish API key is not configured (TINYFISH_API_KEY)."}
    
    urls = params.get("urls", [])
    if len(urls) > 5:
        return {"error": "HINAA deliberately bounds Fetch to a maximum of 5 URLs per request."}
    
    valid_urls = []
    for u in urls:
        if _is_public_url(u):
            valid_urls.append(u)
        else:
            return {"error": f"Rejected internal or invalid URL: {u}"}
            
    url = "https://api.tinyfish.ai/v1/fetch"
    headers = {"X-API-Key": settings.tinyfish_api_key}
    
    timeout = getattr(settings, "tinyfish_fetch_timeout_seconds", 150.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json={"urls": valid_urls}, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": f"TinyFish fetch failed: {e}"}


registry.register(
    ToolDefinition(
        name="tinyfish_search",
        display_name="TinyFish Web Search",
        description="Search the web for current information, news, or research papers.",
        parameters=TinyfishSearchParams.model_json_schema()["properties"],
        required_parameters=["query"],
        requires_confirmation=True,
    ),
    tinyfish_search_handler,
)

registry.register(
    ToolDefinition(
        name="tinyfish_fetch",
        display_name="TinyFish Page Fetch",
        description="Read public web pages and extract clean Markdown content.",
        parameters=TinyfishFetchParams.model_json_schema()["properties"],
        required_parameters=["urls"],
        requires_confirmation=True,
    ),
    tinyfish_fetch_handler,
)

class TinyfishAgentParams(BaseModel):
    task: str = Field(..., description="Natural-language goal for the TinyFish web agent, e.g. 'book a table at ...' or 'fill the contact form and submit'.")
    max_steps: int = Field(50, description="Maximum agent steps (1-200). Defaults to 50.")

async def tinyfish_agent_handler(params: dict, context: dict) -> dict:
    settings = context.get("settings")
    if not settings or not settings.tinyfish_api_key:
        return {"error": "TinyFish API key is not configured (TINYFISH_API_KEY)."}
    task = params.get("task", "").strip()
    if not task:
        return {"error": "A task description is required."}
    max_steps = min(max(int(params.get("max_steps", 50)), 1), 200)
    url = "https://api.tinyfish.ai/v1/agent"
    headers = {"X-API-Key": settings.tinyfish_api_key}
    timeout = getattr(settings, "tinyfish_fetch_timeout_seconds", 150.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url,
                json={"task": task, "max_steps": max_steps},
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": f"TinyFish agent failed: {e}"}


registry.register(
    ToolDefinition(
        name="tinyfish_agent",
        display_name="TinyFish Web Agent",
        description="Execute a goal-based task on the live web (fill forms, navigate sites, extract results). Requires the TINYFISH_API_KEY.",
        parameters=TinyfishAgentParams.model_json_schema()["properties"],
        required_parameters=["task"],
        requires_confirmation=True,
    ),
    tinyfish_agent_handler,
)
