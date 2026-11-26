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
