"""HINAA OS — Typed tool registry for the loop agent.

Each tool declares:
- a pydantic args schema (validated before execution),
- whether it has side effects,
- an approval policy: read-only tools run auto-approved; side-effecting
  tools are refused unless the action payload carries ``confirm: true``.

The executor lives with the step (it owns workspace/shell state); this module
owns schemas, validation and the approval decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, Field


class WriteFileArgs(BaseModel):
    path: str = Field(min_length=1, description="Workspace-relative file path")
    content: str = Field(default="", description="Full file content")


class DeleteFileArgs(BaseModel):
    path: str = Field(min_length=1, description="Workspace-relative file path")


class RunCommandArgs(BaseModel):
    command: str = Field(min_length=1, pattern=r"\S", description="Shell command to run in the workspace")


class ReadFileArgs(BaseModel):
    path: str = Field(min_length=1, description="Workspace-relative file path")
    max_bytes: int = Field(default=16_000, ge=1, le=64_000)


class ListFilesArgs(BaseModel):
    pattern: str = Field(default="**/*", description="Glob pattern, workspace-relative")


class SearchFilesArgs(BaseModel):
    query: str = Field(min_length=2, description="Literal text to find (plain text, not regex)")
    glob: str = Field(default="**/*", description="Glob pattern limiting which files are searched")
    max_results: int = Field(default=40, ge=1, le=200)


class FetchUrlArgs(BaseModel):
    url: str = Field(min_length=8, description="Absolute https:// (or http://) URL to fetch")
    max_chars: int = Field(default=12_000, ge=200, le=40_000)


class BrowserCheckArgs(BaseModel):
    url: str = Field(min_length=8, description="Absolute URL of the page to render and inspect")
    viewport_width: int = Field(default=1280, ge=320, le=1920)
    viewport_height: int = Field(default=800, ge=400, le=1200)


class RunDevServerArgs(BaseModel):
    command: str = Field(min_length=1, pattern=r"\S", description="Bounded local dev server command (e.g. 'pnpm dev --port 3005')")
    subdir: str = Field(default=".", description="Workspace-relative working directory")
    port: int = Field(default=3005, ge=3000, le=3010, description="Loopback port in 3000..3010")


class ScreenshotPageArgs(BaseModel):
    url: str = Field(min_length=8, description="Absolute URL to capture screenshots for at 1280x800 and 390x844")
    label: str = Field(default="page", description="Short filename prefix for docs/evidence/<task_id>/")


class BuildWebsiteArgs(BaseModel):
    brief: str = Field(min_length=3, description="Brand, purpose, and styling brief for HINAA Foundry")
    palette: Optional[str] = Field(default=None, description="Optional Foundry palette name")
    logos: list[str] = Field(default_factory=list, description="Explicit client logos (only user-supplied)")


class ListMediaArgs(BaseModel):
    kind: Optional[str] = Field(default=None, description="Optional filter: image | video | audio | document")


class DescribeMediaArgs(BaseModel):
    media_id: str = Field(min_length=2, description="Media ID returned by upload or list_media")


class DigestDocumentArgs(BaseModel):
    path: str = Field(min_length=1, description="Workspace-relative file path to digest in bounded chunks")
    query: str = Field(default="", description="Optional focus query to extract relevant excerpts")
    max_chunks: int = Field(default=6, ge=1, le=20)


class ReviewDiffArgs(BaseModel):
    focus: str = Field(default="", description="Optional area to scrutinize in workspace changes")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    args_model: Type[BaseModel]
    side_effect: bool
    description: str

    def approval(self, action: Dict[str, Any]) -> str:
        """Return "approved", "auto" or the reason the action is refused."""
        if not self.side_effect:
            return "auto"
        if action.get("confirm") is True:
            return "approved"
        return "blocked: side-effecting tool requires confirm: true"


TOOL_REGISTRY: Dict[str, ToolSpec] = {
    spec.name: spec
    for spec in (
        ToolSpec("write_file", WriteFileArgs, True, "Create or overwrite a file (requires confirm: true)"),
        ToolSpec("delete_file", DeleteFileArgs, True, "Delete a file (requires confirm: true)"),
        ToolSpec("run_command", RunCommandArgs, True, "Run a shell command (requires confirm: true; gated by env)"),
        ToolSpec("read_file", ReadFileArgs, False, "Read a file's contents (auto-approved)"),
        ToolSpec("list_files", ListFilesArgs, False, "List files matching a glob (auto-approved)"),
        ToolSpec(
            "search_files",
            SearchFilesArgs,
            False,
            "Search file contents for literal text; returns file:line matches (auto-approved)",
        ),
        ToolSpec(
            "fetch_url",
            FetchUrlArgs,
            False,
            "Fetch a public https URL and return its text (docs, APIs) (auto-approved)",
        ),
        ToolSpec(
            "browser_check",
            BrowserCheckArgs,
            False,
            "Render a URL headless (Playwright) and report title, text and console/page errors (auto-approved)",
        ),
        ToolSpec(
            "run_dev_server",
            RunDevServerArgs,
            True,
            "Start a bounded dev server on port 3000-3010 inside workspace and emit preview_ready (requires confirm: true + HINAA_LOOP_ALLOW_COMMANDS=1)",
        ),
        ToolSpec(
            "screenshot_page",
            ScreenshotPageArgs,
            False,
            "Capture desktop (1280x800) and mobile (390x844) screenshots into docs/evidence/<task_id>/ for vision review (auto-approved)",
        ),
        ToolSpec(
            "build_website",
            BuildWebsiteArgs,
            True,
            "Generate a verified accessible multi-file site via HINAA Foundry and expose previewUrl (requires confirm: true)",
        ),
        ToolSpec(
            "list_media",
            ListMediaArgs,
            False,
            "List derived insights for attached images, videos, audio, and docs without raw binary payloads (auto-approved)",
        ),
        ToolSpec(
            "describe_media",
            DescribeMediaArgs,
            False,
            "Inspect full MediaInsight metadata, dimensions, palette, storyboard, or headings for a media_id (auto-approved)",
        ),
        ToolSpec(
            "digest_document",
            DigestDocumentArgs,
            False,
            "Chunk-digest large workspace files (100k+ words) into headings and targeted excerpts without flooding context (auto-approved)",
        ),
        ToolSpec(
            "review_diff",
            ReviewDiffArgs,
            False,
            "Inspect current workspace git status and diff summary for self-review before finishing (auto-approved)",
        ),
    )
}


def describe_tools() -> str:
    return "\n".join(f"- {name}: {spec.description}" for name, spec in TOOL_REGISTRY.items())


def validate_action(action: Any) -> tuple[Optional[ToolSpec], Optional[BaseModel], Optional[str]]:
    """Validate a raw model action against the registry.

    Returns (spec, parsed_args, error). Exactly one of parsed_args/error is set.
    """
    if not isinstance(action, dict):
        return None, None, "action is not an object"
    kind = action.get("type")
    spec = TOOL_REGISTRY.get(kind) if isinstance(kind, str) else None
    if spec is None:
        return None, None, f"unknown action type: {kind!r}"
    approval = spec.approval(action)
    if approval != "auto" and approval != "approved":
        return spec, None, approval
    try:
        args = spec.args_model.model_validate({k: v for k, v in action.items() if k != "type"})
    except Exception as exc:
        return spec, None, f"invalid arguments: {str(exc)[:300]}"
    return spec, args, None
