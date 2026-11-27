"""Self-synthesizing Skill generator producing verified SKILL.md artifacts."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from ..society.metrics import SocietyMetricsStore, get_society_metrics


@dataclass(frozen=True)
class SynthesizedSkill:
    name: str
    path: Path
    validated_commands: list[str]
    warnings: list[str]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", value.strip().lower()).strip("-")
    return slug or "custom-skill"


def validate_skill_commands(commands: list[str]) -> tuple[list[str], list[str]]:
    """Verify command executables mentioned in synthesized procedures exist on PATH or are builtins."""
    verified: list[str] = []
    warnings: list[str] = []
    builtins = {"pytest", "python", "pnpm", "npm", "git", "node", "uvicorn", "vitest"}
    for cmd in commands:
        head = (cmd or "").strip().split(" ", 1)[0]
        if not head:
            continue
        if head in builtins or shutil.which(head) is not None:
            verified.append(cmd.strip())
        else:
            warnings.append(f"Executable '{head}' not found on PATH; command left informational.")
    return verified, warnings


def synthesize_skill(
    *,
    name: str,
    description: str,
    steps: list[str],
    commands: list[str] | None = None,
    pitfalls: list[str] | None = None,
    output_root: str | Path,
    metrics: SocietyMetricsStore | None = None,
) -> SynthesizedSkill:
    """Create a validated SKILL.md bundle from a verified recurring solution."""
    slug = _slugify(name)
    skill_dir = Path(output_root) / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    verified_cmds, warnings = validate_skill_commands(list(commands or []))

    lines = [
        "---",
        f"name: {slug}",
        f"description: {description.strip()}",
        "---",
        "",
        f"# {name.strip()}",
        "",
        description.strip(),
        "",
        "## Procedure",
    ]
    for idx, step in enumerate(steps, 1):
        lines.append(f"{idx}. {step.strip()}")

    if verified_cmds:
        lines.extend(["", "## Verified Commands", "```bash", *verified_cmds, "```"])

    if pitfalls:
        lines.extend(["", "## Guardrails & Pitfalls"])
        for pit in pitfalls:
            lines.append(f"- {pit.strip()}")

    target = skill_dir / "SKILL.md"
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    st = metrics or get_society_metrics()
    st.record_counter(
        "skills_synthesized",
        1,
        event={"kind": "skills.synthesized", "name": slug, "path": str(target)},
    )
    return SynthesizedSkill(
        name=slug,
        path=target,
        validated_commands=verified_cmds,
        warnings=warnings,
    )
