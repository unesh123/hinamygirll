"""Server-side effect policy for tool execution.

Two facts make this file necessary. First, the API runs on Unesh's laptop, so a
tool that touches the local machine is executing on that laptop, not in a
container. Second, the only public entry point is a Cloudflare tunnel that
connects to 127.0.0.1, so every remote caller arrives over the same loopback
connection as a local one and no client IP, cookie or token tells them apart.
The one signal that survives is the Host header: cloudflared forwards the
public hostname it was asked to serve, while a call made on the machine itself
names 127.0.0.1.

Previously `requires_confirmation` was the boundary, and /api/v1/tools/execute
satisfied it with `body.confirmed and body.approvalSource == "user"` — two
fields the caller writes. So `POST {"toolName":"clipboard_get","confirmed":true,
"approvalSource":"user"}` from anywhere on the internet read the clipboard, and
`app_launch`, which asked for no confirmation at all, started a process.

Effect classes live here rather than in `ToolDefinition.risk_level` because the
registry's own labels were not usable: `app_launch`, `clipboard_get`,
`send_email` and `github_write_file` were all "medium", and the single "high"
entry was `video_generate`.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..errors import HinaaError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..config import Settings

LOCAL_EFFECT_TOOLS: frozenset[str] = frozenset(
    {
        "file_read",
        "file_write",
        "clipboard_get",
        "clipboard_set",
        "screenshot",
        "app_launch",
        "browser_navigate",
        "browser_click",
        "browser_type",
        "browser_extract",
        "browser_execute_task",
        "browser_navigation_request",
        "youtube_playback_request",
        "system_info",
    }
)

# Acts off-machine but cannot be unsaid: mail sent and branches opened are gone.
IRREVERSIBLE_EXTERNAL_TOOLS: frozenset[str] = frozenset(
    {
        "send_email",
        "github_write_file",
        "github_create_branch",
        "github_create_pull_request",
        "github_create_issue",
        "user_preference_update",
    }
)

_LOOPBACK_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1", "ip6-localhost", "ip6-loopback"})


@dataclass(frozen=True, slots=True)
class Verdict:
    permitted: bool
    code: str = ""
    message: str = ""


def is_loopback_host(host: str | None) -> bool:
    """True for a request aimed at the machine itself, not through the tunnel."""
    if not host:
        return False
    name = host.strip().lower()
    if name.startswith("["):  # IPv6 literal, with or without :port
        name = name[1:].split("]", 1)[0]
    else:
        name = name.rsplit(":", 1)[0] if name.count(":") == 1 else name
    if name in _LOOPBACK_HOSTS:
        return True
    return name.startswith("127.")


def local_effects_permitted(settings: "Settings", host_header: str | None) -> bool:
    """Whether machine-touching tools may run for a request with this Host."""
    return bool(settings.allow_remote_local_tools) or is_loopback_host(host_header)


def decide(tool_name: str, settings: "Settings", host_header: str | None) -> Verdict:
    """Gate a tool on its real effect, before any caller-supplied approval is read."""
    if tool_name in LOCAL_EFFECT_TOOLS and not local_effects_permitted(settings, host_header):
        return Verdict(
            False,
            "LOCAL_TOOL_NOT_PERMITTED",
            f"{tool_name} runs on the computer hosting HINAA, so it is limited to requests "
            "made on that machine. Set HINAA_ALLOW_REMOTE_LOCAL_TOOLS=true to allow it over "
            "the public URL again.",
        )
    if tool_name in IRREVERSIBLE_EXTERNAL_TOOLS and not is_loopback_host(host_header):
        return Verdict(
            False,
            "IRREVERSIBLE_TOOL_NOT_PERMITTED",
            f"{tool_name} cannot be undone and HINAA cannot verify who is asking over the "
            "public URL yet, so it must be run on the host machine. Sign-in will replace this gate.",
        )
    return Verdict(True)


_request_host: ContextVar[str | None] = ContextVar("hinaa_request_host", default=None)


def set_request_host(host: str | None) -> Token[str | None]:
    """Bind the Host of the request being served, for tool dispatch further down."""
    return _request_host.set(host)


def reset_request_host(token: Token[str | None]) -> None:
    _request_host.reset(token)


def enforce(tool_name: str, settings: "Settings") -> None:
    """Raise when the tool in flight is denied for whoever is asking.

    Used by dispatch sites holding no Request, notably the agent runtime: a
    planned `clipboard_get` step reached from a chat turn must meet the same
    rule as the same tool reached from POST /api/v1/tools/execute.
    """
    verdict = decide(tool_name, settings, _request_host.get())
    if not verdict.permitted:
        raise HinaaError(verdict.code, verdict.message, 403, False, True)
