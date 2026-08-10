"""Client-directed navigation tool.

The API runs on a server, so it must never call ``webbrowser.open`` — that
would open a browser on the *server*, not for the user. Instead this tool
validates the URL and returns a structured ``open_url`` action that the web
client executes (after the confirmation step, because
``requires_confirmation`` is set).
"""

from urllib.parse import urlparse

from pydantic import BaseModel, Field

from hinaa_api.tools.registry import registry, ToolDefinition

_ALLOWED_SCHEMES = {"http", "https"}


class OpenBrowserUrlParams(BaseModel):
    url: str = Field(
        ...,
        description="The full URL to open in the browser (must include http:// or https://).",
    )


async def open_browser_url(params: OpenBrowserUrlParams) -> dict:
    """Validate a URL and hand it to the client as an explicit open action."""
    url = params.url.strip()
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
        return {
            "status": "error",
            "error": f"Refusing to open non-web URL: {params.url!r}",
        }
    return {
        "status": "ok",
        "action": "open_url",
        "url": url,
        "note": "Client should open this URL in a new tab after user confirmation.",
    }


browser_navigation_request_def = ToolDefinition(
    name="browser_navigation_request",
    display_name="Open Browser URL",
    description=(
        "Returns a validated URL for the user's browser to open in a new tab. "
        "Useful for navigating to websites the user asked for."
    ),
    parameters={
        "url": {
            "type": "string",
            "description": "The full URL to open in the browser (must include http:// or https://).",
        }
    },
    required_parameters=["url"],
    voice_aliases=["open", "go to", "show me"],
    requires_confirmation=True,
)

registry.register(browser_navigation_request_def, open_browser_url)
