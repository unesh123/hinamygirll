"""catalog.py — Centralized, High-Scale Skill Catalog for HINAA.

Enables HINAA to discover, index, organize, and manage hundreds or thousands of skills
across:
1. Workspace Agent Skills (.agents/skills/*)
2. Global Ecosystem Skills (~/.gemini/config/plugins/.../skills/*)
3. Executable Python Runtime Tools (hinaa_api.tools.registry)
4. Dynamic Community Plugins / Custom Skills

Provides fast indexing, categorization, keyword extraction, and hot-reload capabilities.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("hinaa.skills.catalog")

SkillKind = Literal["agent_skill", "executable_tool", "hybrid_skill"]

CATEGORY_RULES: list[tuple[str, list[str]]] = [
    (
        "Creative & Animation",
        ["anime", "animation", "image", "draw", "render", "cel", "art", "music", "youtube", "freepik", "audio"],
    ),
    (
        "Coding & Engineering",
        ["code", "coding", "python", "typescript", "react", "vue", "astro", "clerk", "git", "terminal", "debugger"],
    ),
    (
        "Web & Browser Automation",
        ["browser", "web", "crawl", "scrape", "search", "navigate", "website", "design_website"],
    ),
    (
        "Research & Intelligence",
        ["research", "investigation", "exa", "arxiv", "paper", "literature", "sales", "deep_research", "customgpt"],
    ),
    (
        "Science & Genomics",
        ["protein", "alphafold", "uniprot", "gene", "variant", "chembl", "clinvar", "pdb", "dna", "conservation"],
    ),
    (
        "Computer Operation & Systems",
        ["operator", "computer_operator", "ui_control", "mouse", "keyboard", "desktop", "os", "edge"],
    ),
    (
        "Documents & Productivity",
        ["pdf", "document", "docx", "report", "slides", "gamma", "email", "reminder", "outlook"],
    ),
]


@dataclass
class SkillRecord:
    id: str
    name: str
    description: str
    kind: SkillKind
    category: str
    triggers: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "kind": self.kind,
            "category": self.category,
            "triggers": self.triggers,
            "parameters": self.parameters,
            "sourcePath": self.source_path,
            "isActive": self.is_active,
            "metadata": self.metadata,
        }


def _infer_category(name: str, description: str) -> str:
    combined = f"{name} {description}".lower()
    for cat_name, keywords in CATEGORY_RULES:
        if any(kw in combined for kw in keywords):
            return cat_name
    return "General & Utility"


def _extract_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parses YAML frontmatter using standard library string processing."""
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) >= 3:
        meta: dict[str, Any] = {}
        for line in parts[1].splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip().strip("\"'")
                if v.startswith("[") and v.endswith("]"):
                    v = [item.strip().strip("\"'") for item in v[1:-1].split(",") if item.strip()]
                meta[k] = v
        return meta, parts[2].strip()
    return {}, content


class SkillCatalog:
    """Manages the full universe of HINAA skills with hot indexing and categorization."""

    def __init__(self, workspace_root: Path | None = None):
        self.workspace_root = workspace_root or Path(__file__).resolve().parents[4]
        self._skills: dict[str, SkillRecord] = {}
        self._categories: dict[str, list[str]] = {}
        self._initialized = False

    def load_all_skills(self, force_reload: bool = False) -> None:
        """Discovers and indexes all available skills."""
        if self._initialized and not force_reload:
            return

        self._skills.clear()
        self._categories.clear()

        # 1. Index Executable Python Tools from ToolRegistry
        self._index_runtime_tools()

        # 2. Index Workspace Agent Skills (.agents/skills/*)
        workspace_skills_dir = self.workspace_root / ".agents" / "skills"
        if workspace_skills_dir.is_dir():
            self._index_skills_directory(workspace_skills_dir, kind="agent_skill")

        # 3. Index Global Plugins Skills (~/.gemini/config/plugins/*)
        user_home = Path.home()
        global_plugins_dir = user_home / ".gemini" / "config" / "plugins"
        if global_plugins_dir.is_dir():
            for skill_dir in global_plugins_dir.glob("**/skills/*"):
                if skill_dir.is_dir():
                    self._index_skill_path(skill_dir, kind="agent_skill")

        # Compile category mapping
        for skill in self._skills.values():
            self._categories.setdefault(skill.category, []).append(skill.id)

        self._initialized = True
        logger.info(
            "Skill Catalog indexed %d total skills across %d categories",
            len(self._skills),
            len(self._categories),
        )

    def _index_runtime_tools(self) -> None:
        try:
            from hinaa_api.tools.registry import registry

            for tool_def in registry.get_all_tools():
                cat = _infer_category(tool_def.name, tool_def.description)
                triggers = list(tool_def.voice_aliases)
                triggers.append(tool_def.name)

                record = SkillRecord(
                    id=f"tool:{tool_def.name}",
                    name=tool_def.display_name or tool_def.name,
                    description=tool_def.description,
                    kind="executable_tool",
                    category=cat,
                    triggers=triggers,
                    parameters=tool_def.parameters,
                    source_path="hinaa_api.tools",
                    is_active=True,
                    metadata={
                        "riskLevel": tool_def.risk_level,
                        "permissionLevel": tool_def.permission_level,
                        "timeoutSeconds": tool_def.timeout_seconds,
                    },
                )
                self._skills[record.id] = record
        except Exception as exc:
            logger.warning("Failed indexing runtime tools into catalog: %s", exc)

    def _index_skills_directory(self, base_dir: Path, kind: SkillKind) -> None:
        for child in base_dir.iterdir():
            if child.is_dir():
                self._index_skill_path(child, kind)

    def _index_skill_path(self, skill_dir: Path, kind: SkillKind) -> None:
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            return

        try:
            content = skill_file.read_text(encoding="utf-8")
            meta, body = _extract_frontmatter(content)
            skill_id = meta.get("name") or skill_dir.name
            display_name = meta.get("title") or skill_id.replace("-", " ").title()
            description = meta.get("description") or (body[:250].strip() if body else "")

            # Check if this agent skill has an underlying executable tool
            final_kind = kind
            if f"tool:{skill_id}" in self._skills:
                final_kind = "hybrid_skill"

            category = _infer_category(skill_id, description)
            triggers = meta.get("triggers") or [skill_id]
            if isinstance(triggers, str):
                triggers = [triggers]

            record = SkillRecord(
                id=skill_id,
                name=display_name,
                description=description,
                kind=final_kind,
                category=category,
                triggers=triggers,
                parameters={},
                source_path=str(skill_file),
                is_active=True,
                metadata=meta,
            )
            self._skills[record.id] = record
        except Exception as exc:
            logger.debug("Failed reading skill at %s: %s", skill_file, exc)

    def get_skill(self, skill_id: str) -> SkillRecord | None:
        self.load_all_skills()
        return self._skills.get(skill_id)

    def list_all(self) -> list[SkillRecord]:
        self.load_all_skills()
        return list(self._skills.values())

    def get_categories(self) -> dict[str, int]:
        self.load_all_skills()
        return {cat: len(skills) for cat, skills in self._categories.items()}

    def count(self) -> int:
        self.load_all_skills()
        return len(self._skills)


# Global singleton instance
skill_catalog = SkillCatalog()
