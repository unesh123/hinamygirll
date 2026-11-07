"""Connector registry: what HINAA can connect to and whether it is configured.

Only key *presence* is reported; secret values never leave this module.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

AuthType = Literal["api_key", "oauth", "token", "none", "mcp"]


@dataclass(frozen=True)
class Connector:
    id: str
    name: str
    category: str
    auth_type: AuthType
    # Each entry is one required credential: any alias in the tuple satisfies it.
    required_env: tuple[tuple[str, ...], ...] = ()
    # Settings attribute that can also satisfy the first requirement (values from .env files).
    settings_attrs: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    description: str = ""
    optional_env: tuple[str, ...] = ()
    health: str | None = None  # name of a lightweight health probe, if any


CONNECTORS: tuple[Connector, ...] = (
    Connector("github", "GitHub", "developer", "token", (("GITHUB_TOKEN",),), ("github_token",),
              ("github_mcp",), "Repositories, issues and pull requests via REST and the GitHub MCP server.",
              ("HINAA_GITHUB_DEFAULT_REPO",), health="github"),
    Connector("exa", "Exa", "research", "api_key", (("EXA_API_KEY",),), ("exa_api_key",),
              ("exa_search", "exa_get_contents", "exa_agent_run"), "Semantic web search and content extraction."),
    Connector("notion", "Notion", "productivity", "token", (("NOTION_API_KEY",),), (),
              (), "Notion workspace status (no dedicated tools yet)."),
    Connector("spotify", "Spotify", "media", "oauth", (("SPOTIFY_CLIENT_ID",),), (),
              ("youtube_playback_request",), "Music playback status."),
    Connector("outlook", "Microsoft Outlook", "communication", "oauth", (("OUTLOOK_ACCESS_TOKEN",),), (),
              ("read_outlook", "send_email"), "Mail through Microsoft Graph."),
    Connector("gamma", "Gamma", "documents", "api_key", (("GAMMA_AI_API_KEY",),), ("gamma_ai_api_key",),
              ("create_gamma_presentation",), "AI-generated presentations."),
    Connector("freepik", "Freepik / Magnific", "creative", "api_key", (("MAGNIFIC_API_KEY", "FREEPIK_API_KEY"),),
              ("magnific_api_key", "freepik_api_key"),
              ("magnific_image_generate", "freepik_image_generate", "magnific_upscale", "freepik_stock_search",
               "image_upscale", "image_relight"), "Image generation, upscaling and stock search."),
    Connector("browser_use", "Browser Use", "browser", "api_key",
              (("BROWSER_USE_API_KEY", "BROWSER_USE_API_KEY1", "BROWSER_USE_API_KEY2", "BROWSER_USE_API_KEY3"),),
              ("browser_use_api_key",), ("browser_cloud_agent",), "Cloud browser agent."),
    Connector("tinyfish", "TinyFish", "research", "api_key", (("TINYFISH_API_KEY",),), ("tinyfish_api_key",),
              ("tinyfish_search", "tinyfish_fetch", "tinyfish_agent"), "Web search, fetch and agent runs."),
    Connector("customgpt", "CustomGPT", "research", "api_key",
              (("APP_CUSTOMGPT_AI_API_KEY", "APP_COUSTOMGPT_AI_API_KEY", "CUSTOMGPT_API_KEY"),),
              ("customgpt_api_key",), ("customgpt_query",), "Knowledge-base question answering."),
    Connector("capsolver", "CapSolver", "captcha", "api_key", (("CAPSOLVER_API_KEY",),), ("capsolver_api_key",),
              (), "Captcha solving."),
    Connector("ez_captcha", "EZ-Captcha", "captcha", "api_key", (("EZ_CAPTCHA_API_KEY",),), ("ez_captcha_api_key",),
              (), "Captcha solving."),
    Connector("treg", "TREG", "developer", "token", (("HINAA_TREG_TOKEN",),), (), ("treg_call",),
              "TREG bridge calls."),
    Connector("elevenlabs", "ElevenLabs", "voice", "api_key", (("ELEVENLABS_API_KEY",),), ("elevenlabs_api_key",),
              (), "Text-to-speech and speech-to-text."),
    Connector("deepgram", "Deepgram", "voice", "api_key", (("DEEPGRAM_API_KEY",),), ("deepgram_api_key",),
              (), "Speech-to-text and text-to-speech."),
    Connector("openai", "OpenAI", "llm", "api_key", (("OPENAI_API_KEY",),), ("openai_api_key",), (), "LLM provider."),
    Connector("anthropic", "Anthropic", "llm", "api_key", (("HINAA_CLAUDE_API_KEY", "ANTHROPIC_API_KEY"),),
              ("claude_api_key",), (), "LLM provider."),
    Connector("groq", "Groq", "llm", "api_key", (("GROQ_API_KEY",),), ("groq_api_key",), (), "LLM provider."),
)

_BY_ID = {c.id: c for c in CONNECTORS}


def _settings() -> Any:
    try:
        from ..config import get_settings

        return get_settings()
    except Exception:
        return None


def _settings_has(settings: Any, attr: str) -> bool:
    value = getattr(settings, attr, None) if settings is not None else None
    if value is None:
        return False
    getter = getattr(value, "get_secret_value", None)
    return bool((getter() if getter else str(value)).strip())


def _env_has(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def missing_keys(connector: Connector, settings: Any = None) -> list[str]:
    """Env names still needed (first alias of each unmet requirement)."""
    if settings is None:
        settings = _settings()
    if connector.settings_attrs and any(_settings_has(settings, a) for a in connector.settings_attrs):
        return []
    return [aliases[0] for aliases in connector.required_env if not any(_env_has(a) for a in aliases)]


def is_configured(connector: Connector, settings: Any = None) -> bool:
    return not connector.required_env or not missing_keys(connector, settings)


def describe(connector: Connector, *, registered_tools: set[str] | None = None) -> dict[str, Any]:
    if registered_tools is None:
        registered_tools = _registered_tool_names()
    missing = missing_keys(connector)
    return {
        "id": connector.id,
        "name": connector.name,
        "category": connector.category,
        "authType": connector.auth_type,
        "description": connector.description,
        "requiredEnv": [aliases[0] for aliases in connector.required_env],
        "optionalEnv": list(connector.optional_env),
        "missingEnv": missing,
        "configured": not missing,
        "tools": [t for t in connector.tools if t in registered_tools],
        "healthCheck": connector.health is not None,
    }


def _registered_tool_names() -> set[str]:
    try:
        from ..tools.registry import registry

        return {t.name for t in registry.get_all_tools()}
    except Exception:
        return set()


def list_connectors(category: str | None = None) -> list[dict[str, Any]]:
    tools = _registered_tool_names()
    return [
        describe(c, registered_tools=tools)
        for c in CONNECTORS
        if not category or c.category == category.lower()
    ]


def get_connector(connector_id: str) -> Connector | None:
    return _BY_ID.get(connector_id.lower())


def mcp_summary() -> dict[str, Any]:
    from .mcp_store import get_store

    servers = get_store().list_servers()
    return {"servers": len(servers), "enabled": sum(1 for s in servers if s.enabled)}
