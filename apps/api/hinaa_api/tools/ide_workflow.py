"""build_with_ide — hand a build brief to the owner's AI IDE (Antigravity, Cursor, VS Code).

Workflow: create project folder -> write PROMPT.md -> launch the IDE on it ->
wait for/focus its window -> paste the brief into the IDE's agent chat. Every
step runs through ActionGuard and returns an ActionReceipt. Honors the computer
operator's dry-run switch (HINAA_COMPUTER_DRY_RUN): a dry run returns the plan
and touches nothing. Launches use argv lists, never a shell.

Generic app launching already exists as `app_launch`; this module does not add
a second one.
"""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import shutil
import subprocess
import sys
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..errors import HinaaError
from .action_guard import ActionReceipt, RetryPolicy, VerificationSpec, run_guarded_action
from .registry import ToolDefinition, registry

DEFAULT_IDE_COMMANDS: tuple[str, ...] = ("antigravity", "cursor", "code")
DEFAULT_AGENT_SHORTCUT = "ctrl+l"
MAX_BRIEF_CHARS = 60_000

# Windows per-user install locations, relative to %LOCALAPPDATA%.
_WINDOWS_INSTALL_PATHS: dict[str, tuple[str, ...]] = {
    "antigravity": (
        r"Programs\Antigravity\Antigravity.exe",
        r"Programs\Antigravity\bin\antigravity.cmd",
    ),
    "cursor": (r"Programs\cursor\Cursor.exe", r"Programs\cursor\resources\app\bin\cursor.cmd"),
    "code": (r"Programs\Microsoft VS Code\Code.exe", r"Programs\Microsoft VS Code\bin\code.cmd"),
}


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def slugify_project_name(name: str) -> str:
    """Safe single path segment, or raise. Separators and '..' are rejected, not stripped."""
    raw = unicodedata.normalize("NFKC", str(name or "")).strip()
    if not raw:
        raise HinaaError("IDE_PROJECT_NAME_INVALID", "A project name is required.", 422)
    if re.search(r"[\\/\x00]|(^|\s)\.\.($|\s)|^\.+$|:", raw):
        raise HinaaError(
            "IDE_PROJECT_NAME_INVALID", "Project name may not contain path separators or '..'.", 422
        )
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")[:48].strip("-")
    if not slug:
        raise HinaaError("IDE_PROJECT_NAME_INVALID", "Project name has no usable characters.", 422)
    return slug


def projects_root(env: dict[str, str] | None = None) -> Path:
    source = os.environ if env is None else env
    configured = source.get("HINAA_PROJECTS_ROOT", "").strip()
    return Path(configured).expanduser() if configured else Path.home() / "HinaProjects"


def resolve_ide_command(
    env: dict[str, str] | None = None,
    *,
    which: Callable[[str], str | None] = shutil.which,
    windows: bool | None = None,
    exists: Callable[[str], bool] = os.path.exists,
) -> tuple[list[str], str]:
    """Return (argv prefix, ide name). A configured HINAA_IDE_COMMAND is used alone."""
    source = os.environ if env is None else env
    windows = _is_windows() if windows is None else windows
    configured = source.get("HINAA_IDE_COMMAND", "").strip()
    candidates = [configured] if configured else list(DEFAULT_IDE_COMMANDS)
    local_app = source.get("LOCALAPPDATA", "")
    for candidate in candidates:
        parts = shlex.split(candidate, posix=not windows)
        if not parts:
            continue
        head = parts[0].strip('"')
        found = which(head)
        if found:
            return [found, *parts[1:]], Path(head).stem.lower()
        if windows and local_app:
            for rel in _WINDOWS_INSTALL_PATHS.get(Path(head).stem.lower(), ()):
                path = f"{local_app}\\{rel}"
                if exists(path):
                    return [path, *parts[1:]], Path(head).stem.lower()
    tried = ", ".join(candidates)
    raise HinaaError(
        "IDE_NOT_FOUND", f"No IDE launcher found (tried: {tried}). Set HINAA_IDE_COMMAND.", 422
    )


@dataclass
class IdePorts:
    """Side-effect boundary; tests substitute fakes."""

    launch: Callable[[list[str]], Any] = field(default=None)  # returns object with .poll()
    list_windows: Callable[[], Awaitable[list[dict[str, Any]]]] = field(default=None)
    active_title: Callable[[], str] = field(default=None)
    focus: Callable[[str], Awaitable[bool]] = field(default=None)
    hotkey: Callable[[str], Awaitable[bool]] = field(default=None)
    set_clipboard: Callable[[str], Awaitable[bool]] = field(default=None)
    get_clipboard: Callable[[], str | None] = field(default=None)
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    dry_run: Callable[[], bool] = field(default=None)
    which: Callable[[str], str | None] = shutil.which
    windows: bool | None = None
    exists: Callable[[str], bool] = os.path.exists


def _launch_process(argv: list[str]) -> Any:
    kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if _is_windows():
        kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(argv, shell=False, **kwargs)  # noqa: S603 - argv list, no shell


async def _set_clipboard(text: str) -> bool:
    try:
        import pyperclip

        pyperclip.copy(text)
        return True
    except Exception:  # noqa: BLE001, S110
        pass
    if not _is_windows():
        return False
    # Path/text travel via environment, never interpolated into the command.
    env = {**os.environ, "HINAA_CLIP_TEXT": text}
    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "Set-Clipboard -Value $env:HINAA_CLIP_TEXT",
            ],
            env=env,
            capture_output=True,
            timeout=10,
        )
        return proc.returncode == 0
    except Exception:  # noqa: BLE001, S110
        return False


def _get_clipboard() -> str | None:
    try:
        import pyperclip

        return pyperclip.paste()
    except Exception:  # noqa: BLE001, S110
        return None


def default_ports() -> IdePorts:
    from .computer_operator import NativeComputerOperator as Op

    return IdePorts(
        launch=_launch_process,
        list_windows=Op.list_windows,
        active_title=lambda: Op.observe().active_window_title,
        focus=Op.focus_window,
        hotkey=Op.press_hotkey,
        set_clipboard=_set_clipboard,
        get_clipboard=_get_clipboard,
        dry_run=Op._dry_run,
    )


class BuildWithIdeParams(BaseModel):
    project_name: str = Field(
        ..., description="Short name for the project; becomes the folder slug."
    )
    brief: str = Field(
        ..., description="The full build brief to give the IDE's agent (written to PROMPT.md)."
    )
    submit: bool = Field(
        True, description="Press Enter after pasting so the IDE agent starts working."
    )


def _receipt_dict(receipt: ActionReceipt) -> dict[str, Any]:
    return receipt.as_metadata()


def _unique_dir(root: Path, slug: str) -> Path:
    candidate = root / slug
    n = 2
    while candidate.exists():
        candidate = root / f"{slug}-{n}"
        n += 1
    return candidate


def plan_steps(folder: Path, argv: list[str], shortcut: str, submit: bool) -> list[str]:
    steps = [
        f"create folder {folder}",
        f"write {folder / 'PROMPT.md'}",
        f"launch IDE: {argv[0]} {folder}",
        f"wait for a window titled with '{folder.name}'",
        f"focus the '{folder.name}' window",
        "copy the brief to the clipboard",
        f"press {shortcut} to focus the agent chat",
        "press ctrl+v to paste the brief",
    ]
    if submit:
        steps.append("press enter to submit")
    return steps


async def build_with_ide(
    params: BuildWithIdeParams,
    *,
    ports: IdePorts | None = None,
    env: dict[str, str] | None = None,
    ledger: Any = None,
) -> dict[str, Any]:
    ports = ports or default_ports()
    source = os.environ if env is None else env
    brief = params.brief
    if not brief.strip():
        raise HinaaError("IDE_BRIEF_EMPTY", "The build brief is empty.", 422)
    if len(brief) > MAX_BRIEF_CHARS:
        raise HinaaError("IDE_BRIEF_TOO_LONG", f"Brief exceeds {MAX_BRIEF_CHARS} characters.", 422)

    slug = slugify_project_name(params.project_name)
    root = projects_root(source).resolve()
    folder = _unique_dir(root, slug)
    if not folder.resolve().is_relative_to(root):
        raise HinaaError("IDE_PROJECT_NAME_INVALID", "Project path escapes the projects root.", 422)
    argv_prefix, ide_name = resolve_ide_command(
        source, which=ports.which, windows=ports.windows, exists=ports.exists
    )
    shortcut = source.get("HINAA_IDE_AGENT_SHORTCUT", "").strip() or DEFAULT_AGENT_SHORTCUT
    argv = [*argv_prefix, str(folder)]
    steps = plan_steps(folder, argv_prefix, shortcut, params.submit)

    if ports.dry_run():
        return {
            "success": True,
            "dry_run": True,
            "ide": ide_name,
            "folder": str(folder),
            "planned_steps": steps,
            "receipts": [],
        }

    receipts: list[ActionReceipt] = []
    result: dict[str, Any] = {
        "success": False,
        "dry_run": False,
        "ide": ide_name,
        "folder": str(folder),
        "planned_steps": steps,
    }
    title_key = folder.name.lower()

    def finish(note: str | None = None) -> dict[str, Any]:
        result["receipts"] = [_receipt_dict(r) for r in receipts]
        result["success"] = bool(receipts) and all(r.verified for r in receipts) and note is None
        if note:
            result["stopped_reason"] = note
        return result

    async def guarded(
        name: str,
        action,
        observe,
        description: str,
        predicate,
        policy: RetryPolicy | None = None,
        recover=None,
    ):
        receipt = await run_guarded_action(
            action_name=name,
            action=action,
            observe=observe,
            spec=VerificationSpec(
                description=description, predicate=predicate, observe_before=False
            ),
            policy=policy or RetryPolicy(max_attempts=1, backoff_seconds=0),
            recover=recover,
            ledger=ledger,
            turn_id="build_with_ide",
        )
        receipts.append(receipt)
        return receipt

    # 1. folder
    async def make_folder() -> None:
        folder.mkdir(parents=True, exist_ok=False)

    async def observe_folder() -> bool:
        return folder.is_dir()

    if not (
        await guarded(
            "ide.create_folder", make_folder, observe_folder, "project folder exists", bool
        )
    ).verified:
        return finish("create_folder_failed")

    # 2. PROMPT.md
    prompt_path = folder / "PROMPT.md"

    async def write_prompt() -> None:
        prompt_path.write_text(brief, encoding="utf-8", newline="")

    async def observe_prompt() -> str | None:
        return prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else None

    if not (
        await guarded(
            "ide.write_prompt",
            write_prompt,
            observe_prompt,
            "PROMPT.md holds the brief",
            lambda s: s == brief,
        )
    ).verified:
        return finish("write_prompt_failed")

    # 3. launch (never retried: a second launch would open a second window)
    proc_holder: dict[str, Any] = {}

    async def launch() -> None:
        proc_holder["proc"] = ports.launch(argv)

    async def observe_launch() -> dict[str, Any]:
        await ports.sleep(0.5)
        proc = proc_holder.get("proc")
        return {
            "launched": proc is not None,
            "returncode": proc.poll() if proc is not None else None,
        }

    # CLI launchers (code/cursor .cmd) may exit 0 after handing off to the app.
    if not (
        await guarded(
            "ide.launch",
            launch,
            observe_launch,
            "IDE process started",
            lambda o: o["launched"] and o["returncode"] in (None, 0),
        )
    ).verified:
        return finish("launch_failed")

    # 4. window
    async def noop() -> None:
        return None

    async def observe_windows() -> dict[str, Any]:
        windows = await ports.list_windows()
        titles = [str(w.get("title", "")).lower() for w in windows]
        return {"observable": bool(windows), "match": any(title_key in t for t in titles)}

    window_receipt = await guarded(
        "ide.window_open",
        noop,
        observe_windows,
        f"a window title contains '{folder.name}'",
        lambda o: o["observable"] and o["match"],
        RetryPolicy(max_attempts=12, backoff_seconds=0.5, backoff_multiplier=1.0),
    )
    if not window_receipt.verified:
        return finish("ide_window_not_observed")

    # 5. focus
    async def focus() -> None:
        await ports.focus(folder.name)

    async def observe_active() -> str:
        return ports.active_title().lower()

    focus_receipt = await guarded(
        "ide.focus_window",
        focus,
        observe_active,
        "IDE window is in the foreground",
        lambda t: title_key in t,
        RetryPolicy(max_attempts=3, backoff_seconds=0.3, backoff_multiplier=1.0),
    )
    if not focus_receipt.verified:
        return finish("ide_not_focused")

    # 6. clipboard
    async def copy_brief() -> None:
        if not await ports.set_clipboard(brief):
            raise RuntimeError("clipboard unavailable")

    async def observe_clip() -> dict[str, Any]:
        got = ports.get_clipboard()
        return {"readable": got is not None, "equal": got == brief}

    if not (
        await guarded(
            "ide.copy_brief",
            copy_brief,
            observe_clip,
            "clipboard holds the brief",
            lambda o: (not o["readable"]) or o["equal"],
        )
    ).verified:
        return finish("clipboard_failed")

    # 7-9. keystrokes; each must leave the IDE window in front. The pasted text
    # itself is not observable from outside the IDE, so this verifies delivery
    # to the right window, not the chat contents.
    keys = [("ide.focus_agent_chat", shortcut), ("ide.paste_brief", "ctrl+v")]
    if params.submit:
        keys.append(("ide.submit", "enter"))
    for name, combo in keys:

        async def press(combo: str = combo) -> None:
            if not await ports.hotkey(combo):
                raise RuntimeError(f"hotkey {combo} failed")
            await ports.sleep(0.4)

        if not (
            await guarded(
                name,
                press,
                observe_active,
                "keystroke delivered with the IDE in front",
                lambda t: title_key in t,
            )
        ).verified:
            return finish(f"{name}_failed")

    return finish()


async def _tool_handler(params: BuildWithIdeParams) -> dict[str, Any]:
    from ..run_ledger import get_run_ledger

    return await build_with_ide(params, ledger=get_run_ledger())


build_with_ide_def = ToolDefinition(
    name="build_with_ide",
    display_name="IDE: Build With Antigravity/Cursor/VS Code",
    description=(
        "Create a project folder, save the full build brief as PROMPT.md, open it in the owner's AI IDE "
        "(Antigravity by default), and paste the brief into the IDE's agent chat."
    ),
    parameters={
        "project_name": {"type": "string", "description": "Short project name (folder slug)."},
        "brief": {"type": "string", "description": "The complete build brief for the IDE agent."},
        "submit": {"type": "boolean", "description": "Press Enter after pasting. Default true."},
    },
    required_parameters=["project_name", "brief"],
    requires_confirmation=True,
    risk_level="high",
    is_concurrency_safe=False,
    is_long_running=True,
    timeout_seconds=120.0,
)
registry.register(build_with_ide_def, _tool_handler)
