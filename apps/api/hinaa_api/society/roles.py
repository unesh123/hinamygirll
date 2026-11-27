"""Role specifications for Maker / Reviewer / Verifier society."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@dataclass(frozen=True)
class AgentSpec:
    role: str
    system_prompt: str
    read_only: bool = True
    max_steps: int = 8


@dataclass(frozen=True)
class ReviewVerdict:
    verdict: str  # "PASS" | "CHANGES_REQUESTED"
    findings: list[str] = field(default_factory=list)
    reviewer: str = "reviewer"


@dataclass(frozen=True)
class VerificationVerdict:
    verified: bool
    checks_run: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def load_role_prompt(role_name: str) -> str:
    fp = PROMPTS_DIR / f"{role_name}.md"
    if fp.is_file():
        return fp.read_text(encoding="utf-8").strip()
    return f"Act independently as {role_name} and verify against ground truth."


def default_society_specs() -> dict[str, AgentSpec]:
    return {
        "maker": AgentSpec(
            role="maker",
            system_prompt="Plan minimally, edit workspace files carefully, and hand off clean diffs.",
            read_only=False,
            max_steps=12,
        ),
        "reviewer": AgentSpec(
            role="reviewer",
            system_prompt=load_role_prompt("reviewer"),
            read_only=True,
            max_steps=6,
        ),
        "verifier": AgentSpec(
            role="verifier",
            system_prompt=load_role_prompt("verifier"),
            read_only=True,
            max_steps=6,
        ),
    }
