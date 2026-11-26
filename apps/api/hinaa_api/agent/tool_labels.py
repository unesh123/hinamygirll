"""Human-readable tool activity labels, concise targets, and parallel lane mapping."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Maps backend tool IDs -> (human verb/label, primary argument key for target, activity lane)
TOOL_DISPLAY_SPEC: dict[str, tuple[str, str | None, str]] = {
    "workspace_read_file": ("Reading", "path", "files"),
    "workspace_write_file": ("Writing", "path", "files"),
    "workspace_edit_file": ("Editing", "path", "files"),
    "workspace_delete_file": ("Deleting", "path", "files"),
    "workspace_move_file": ("Moving", "destination", "files"),
    "workspace_list_dir": ("Listing", "path", "files"),
    "workspace_glob": ("Finding files", "pattern", "files"),
    "workspace_grep": ("Searching code", "pattern", "files"),
    "workspace_run_command": ("Running", "command", "system"),
    "workspace_verify_html": ("Verifying UI", "path", "files"),
    "workspace_verify_url": ("Verifying URL", "url", "research"),
    "workspace_git_status_diff": ("Checking git status", None, "files"),
    "workspace_checkpoint": ("Checkpoint", "action", "system"),
    "workspace_start_process": ("Starting process", "command", "system"),
    "workspace_process_logs": ("Reading process logs", "process_id", "system"),
    "workspace_stop_process": ("Stopping process", "process_id", "system"),
    "workspace_spawn_subagent": ("Running helper agent", "role", "reasoning"),
    "video_inspect_frames": ("Inspecting video frames", "path", "media"),
    "web_search": ("Searching web", "query", "research"),
    "web_extract": ("Reading webpage", "url", "research"),
    "web_answer": ("Answering from web", "query", "research"),
    "image_search": ("Searching images", "query", "media"),
    "render_code_animation": ("Rendering animation", "title", "media"),
    "create_lyric_video": ("Creating lyric video", "title", "media"),
    "create_motion_video": ("Creating motion video", "title", "media"),
    "mlai_list_routines": ("Listing routines", None, "system"),
    "mlai_run_routine": ("Running routine", "routine_name", "system"),
    "bivia_decide": ("Checking decision policy", "query", "reasoning"),
    "browser_open": ("Opening webpage", "url", "research"),
    "browser_act": ("Interacting on page", "action", "research"),
    "browser_snapshot": ("Inspecting page", None, "research"),
    "pc.screenshot": ("Capturing screen", None, "media"),
    "pc.active_window": ("Checking active window", None, "system"),
    "pc.click": ("Clicking screen target", "label", "system"),
    "pc.type": ("Typing into window", None, "system"),
    "pc.hotkey": ("Pressing shortcut", "keys", "system"),
    "pc.open_app": ("Opening application", "app", "system"),
}


def _concise_target(raw_value: Any, arg_key: str | None) -> str:
    if raw_value is None:
        return ""
    if isinstance(raw_value, (list, tuple)):
        txt = "+".join(str(x) for x in raw_value if x is not None)
    else:
        txt = str(raw_value).strip()
    if not txt:
        return ""
    if arg_key in {"path", "destination", "file_path", "target"}:
        try:
            name = Path(txt.replace("\\", "/")).name
            if name:
                return name[:64]
        except Exception:
            pass
    if len(txt) > 56:
        return txt[:53] + "..."
    return txt


def describe_tool_call(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, str]:
    """Return user-facing `{label, target, lane}` for any backend tool call.

    Never exposes raw snake_case identifiers as the display label.
    """
    args = arguments if isinstance(arguments, dict) else {}
    clean_name = (tool_name or "").strip()
    spec = TOOL_DISPLAY_SPEC.get(clean_name)

    if spec is not None:
        label, target_key, lane = spec
        raw_target = args.get(target_key) if target_key else None
        if raw_target is None and target_key == "destination":
            raw_target = args.get("source") or args.get("path")
        target = _concise_target(raw_target, target_key)
        return {"label": label, "target": target, "lane": lane}

    # Prefix heuristics for dynamically registered tools (pc.*, mcp.*, workspace.*, etc.)
    lower = clean_name.lower()
    if lower.startswith("pc."):
        verb = clean_name[3:].replace("_", " ").capitalize()
        lane = "media" if "screen" in lower else "system"
    elif any(k in lower for k in ("search", "web", "fetch", "browse", "url")):
        verb = clean_name.replace("_", " ").replace(".", " ").title()
        lane = "research"
    elif any(k in lower for k in ("read", "write", "edit", "file", "dir", "glob", "grep", "git")):
        verb = clean_name.replace("workspace_", "").replace("_", " ").capitalize()
        lane = "files"
    elif any(k in lower for k in ("image", "video", "audio", "render", "motion", "avatar")):
        verb = clean_name.replace("_", " ").capitalize()
        lane = "media"
    else:
        verb = (clean_name.replace("_", " ").replace(".", " ").strip() or "Running tool").capitalize()
        lane = "system"

    target = ""
    for candidate_key in ("path", "query", "url", "command", "title", "role", "pattern", "app", "routine_name"):
        if args.get(candidate_key):
            target = _concise_target(args.get(candidate_key), candidate_key)
            break
    return {"label": verb, "target": target, "lane": lane}
