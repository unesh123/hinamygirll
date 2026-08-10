import webbrowser
from pydantic import BaseModel, Field

class OpenBrowserUrlParams(BaseModel):
    url: str = Field(..., description="The full URL to open in the browser (must include http:// or https://).")

async def open_browser_url(params: OpenBrowserUrlParams) -> str:
    """
    Opens a specific URL in the user's default system browser.
    Useful for navigating to social media sites, web tools, or opening search results.
    """
    try:
        if not params.url.startswith("http"):
            params.url = "https://" + params.url
            
        success = webbrowser.open(params.url)
        if success:
            return f"Successfully opened {params.url} in the browser."
        else:
            return f"Attempted to open {params.url}, but the system browser might not have launched."
    except Exception as e:
        return f"Error opening URL: {str(e)}"

from hinaa_api.tools.registry import registry, ToolDefinition

browser_navigation_request_def = ToolDefinition(
    name="browser_navigation_request",
    display_name="Open Browser URL",
    description="Opens a specific URL in the user's default system browser. Useful for navigating to social media sites, web tools, or opening search results directly on the user's screen.",
    parameters={
        "url": {
            "type": "string",
            "description": "The full URL to open in the browser (must include http:// or https://)."
        }
    },
    required_parameters=["url"],
    voice_aliases=["open", "go to", "show me"],
    requires_confirmation=True
)

registry.register(browser_navigation_request_def, open_browser_url)

