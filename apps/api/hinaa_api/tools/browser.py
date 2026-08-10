import httpx
import re
from typing import Any
from .registry import ToolDefinition, registry

# DuckDuckGo HTML Search
async def search_web(params: dict[str, Any]) -> dict[str, Any]:
    query = params.get("query", "")
    if not query:
        return {"error": "Query is required"}
    
    url = f"https://html.duckduckgo.com/html/?q={httpx.urls.URL(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except Exception as e:
            return {"error": str(e)}
            
    html = resp.text
    # Simple regex to extract search results
    pattern = r'<a class="result__url" href="([^"]+)".*?>(.*?)</a>.*?<a class="result__snippet[^>]*>(.*?)</a>'
    matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
    
    results = []
    for url, title, snippet in matches[:5]: # top 5
        # Clean HTML tags
        title = re.sub(r'<[^>]+>', '', title).strip()
        snippet = re.sub(r'<[^>]+>', '', snippet).strip()
        results.append({
            "title": title,
            "url": url,
            "snippet": snippet
        })
        
    return {
        "query": query,
        "results": results
    }

web_search_def = ToolDefinition(
    name="web_search",
    display_name="Search the Web",
    description="Search the web for real-time information.",
    parameters={
        "query": {"type": "string", "description": "The search query to execute"}
    },
    required_parameters=["query"],
    cancellable=True,
    voice_aliases=["search for", "look up", "find"]
)

registry.register(web_search_def, search_web)
