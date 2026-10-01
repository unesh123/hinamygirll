"""
HINAA Repository-as-Memory Subsystem.

Implements the OpenAI harness-engineering principle:
"Codebases work best when the repository itself acts as the structured,
versioned system of record. Critical knowledge must be local, legible,
and mechanically validated."

Manages:
- .hina/architecture.md
- .hina/project.md
- .hina/conventions.md
- .hina/quality.md
- .hina/security.md
- .hina/active-plan.md
- .hina/decisions/
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


STANDARD_HINA_FILES = {
    "architecture.md": (
        "# Architecture Overview\n\n"
        "## Core Principles\n"
        "- Separation of Cognition and Environment\n"
        "- Capability-scoped permissions with strict boundary validation\n"
        "- Event-sourced persistent threads and context compaction\n"
        "- Autonomous multi-agent coordination with recursion limits\n\n"
        "## Key Systems\n"
        "- App Server: JSON-RPC & SSE event streams\n"
        "- Agent Harness: Session lifecycle, tool dispatch, and verification\n"
        "- Environment: Kali Linux WSL & sandboxed shell runtimes\n"
    ),
    "project.md": (
        "# Project Definition\n\n"
        "## Product Identity\n"
        "HINAA: High-performance Autonomous Companion & Frontier Engineering Workspace.\n\n"
        "## Key Objectives\n"
        "1. Realtime multi-modal interaction (voice, vision, 3D avatar).\n"
        "2. Autonomous engineering and cybersecurity capabilities.\n"
        "3. Zero leakage of internal prompt reflections or meta-reasoning.\n"
    ),
    "conventions.md": (
        "# Engineering Conventions\n\n"
        "## Code Standards\n"
        "- Python 3.12+ with strict typing and Pydantic models.\n"
        "- TypeScript with strict type-safety and Tailwind styling.\n"
        "- Never log, expose, or commit raw credentials or API keys.\n"
        "- Canonicalize paths before execution; never trust raw model cwd.\n"
    ),
    "quality.md": (
        "# Quality & Verification Invariants\n\n"
        "## Invariants\n"
        "- Every new feature must be accompanied by automated tests.\n"
        "- Conversational speech chunks (TTS) must never contain thinking tags.\n"
        "- Subagent recursion depth is strictly capped at 4.\n"
    ),
    "security.md": (
        "# Security Policy & Threat Model\n\n"
        "## Mitigations (GHSA-w5fx-fh39-j5rw)\n"
        "- Model-generated paths never establish security boundaries.\n"
        "- Filesystem writes outside designated workspace roots are blocked.\n"
        "- DNS, TCP, and network egress are governed by allowlists.\n"
        "- Environment secrets are scrubbed before child process execution.\n"
    ),
    "active-plan.md": (
        "# Active Execution Plan\n\n"
        "Status: In Progress\n"
        "Goal: Establish Frontier Codex Harness and Cognitive Operating System.\n"
    ),
}


class RepositoryMemoryManager:
    """
    Manages `.hina/` repository-level memory files and compiles them into context prompts.
    """

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.hina_dir = self.workspace_root / ".hina"

    def scaffold_if_missing(self) -> List[str]:
        """Creates .hina/ folder and initial structural markdown documents."""
        created = []
        self.hina_dir.mkdir(parents=True, exist_ok=True)
        (self.hina_dir / "decisions").mkdir(parents=True, exist_ok=True)

        for filename, content in STANDARD_HINA_FILES.items():
            fpath = self.hina_dir / filename
            if not fpath.exists():
                fpath.write_text(content, encoding="utf-8")
                created.append(str(fpath.relative_to(self.workspace_root)))

        return created

    def load_memory_context(self) -> Dict[str, str]:
        """Reads all .hina markdown documents into a dictionary."""
        if not self.hina_dir.exists():
            return {}

        memory: Dict[str, str] = {}
        for md_file in self.hina_dir.glob("*.md"):
            try:
                memory[md_file.stem] = md_file.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning("Failed to read %s: %s", md_file, e)

        return memory

    def compile_prompt_block(self, max_chars_per_section: int = 1500) -> str:
        """
        Compiles repository memory into a stable, cache-friendly prompt prefix.
        """
        memory = self.load_memory_context()
        if not memory:
            return ""

        parts = ["<repository_memory>"]
        for key in ["architecture", "project", "conventions", "security", "quality", "active-plan"]:
            if key in memory:
                text = memory[key][:max_chars_per_section].strip()
                parts.append(f"<{key}>\n{text}\n</{key}>")
        parts.append("</repository_memory>")
        return "\n".join(parts)

    def update_active_plan(self, new_plan_markdown: str) -> None:
        """Updates .hina/active-plan.md with current goals and steps."""
        self.hina_dir.mkdir(parents=True, exist_ok=True)
        plan_file = self.hina_dir / "active-plan.md"
        plan_file.write_text(new_plan_markdown, encoding="utf-8")

    def record_decision(self, title: str, decision_text: str) -> str:
        """Records an Architecture Decision Record (ADR) under .hina/decisions/."""
        dec_dir = self.hina_dir / "decisions"
        dec_dir.mkdir(parents=True, exist_ok=True)
        
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        slug = "".join(c if c.isalnum() else "_" for c in title.lower())[:40]
        fname = f"{now_str}_{slug}.md"
        
        fpath = dec_dir / fname
        content = f"# Decision: {title}\n\nDate: {datetime.now(timezone.utc).isoformat()}\n\n{decision_text}"
        fpath.write_text(content, encoding="utf-8")
        return str(fpath.relative_to(self.workspace_root))
