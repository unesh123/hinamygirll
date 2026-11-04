"""Project Scanner: Language detection, test discovery, and bounded symbol search."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

logger = logging.getLogger("hinaa.workspaces.scanner")

_IGNORED_DIRS: Set[str] = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build",
}


class ProjectOverview(BaseModel):
    """Structured inspection overview of a project repository."""

    root_path: str
    primary_language: str
    detected_languages: List[str]
    package_managers: List[str]
    test_frameworks: List[str]
    build_commands: List[str]
    total_files: int
    entry_points: List[str] = Field(default_factory=list)


class WorkspaceScanner:
    """Scans and analyzes project structure without blowing LLM context windows."""

    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path.resolve()

    def scan_project(self) -> ProjectOverview:
        """Performs initial non-destructive discovery of project technologies and commands."""
        languages: Set[str] = set()
        pkg_managers: Set[str] = set()
        test_frameworks: Set[str] = set()
        build_cmds: Set[str] = set()
        entry_points: List[str] = []
        total_files = 0

        # Check Python indicators
        if (self.root_path / "pyproject.toml").exists() or (self.root_path / "requirements.txt").exists():
            languages.add("Python")
            pkg_managers.add("pip/uv")
            test_frameworks.add("pytest")

        # Check Node / TypeScript indicators
        pkg_json_path = self.root_path / "package.json"
        if pkg_json_path.exists():
            languages.add("JavaScript")
            if (self.root_path / "tsconfig.json").exists():
                languages.add("TypeScript")
            pkg_managers.add("npm")

            try:
                with open(pkg_json_path, "r", encoding="utf-8") as f:
                    pkg_data = json.load(f)
                    scripts = pkg_data.get("scripts", {})
                    if "test" in scripts:
                        test_frameworks.add("npm test")
                    if "build" in scripts:
                        build_cmds.add("npm run build")
                    if "main" in pkg_data:
                        entry_points.append(pkg_data["main"])
            except Exception as e:
                logger.debug("Failed parsing package.json: %s", e)

        # Count files (bounded)
        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in _IGNORED_DIRS]
            for f in files:
                total_files += 1
                if f.endswith(".py"):
                    languages.add("Python")
                elif f.endswith(".ts") or f.endswith(".tsx"):
                    languages.add("TypeScript")
                elif f.endswith(".js") or f.endswith(".jsx"):
                    languages.add("JavaScript")

        primary_lang = (
            "Python"
            if "Python" in languages
            else (
                "TypeScript"
                if "TypeScript" in languages
                else ("JavaScript" if "JavaScript" in languages else "Unknown")
            )
        )

        return ProjectOverview(
            root_path=str(self.root_path),
            primary_language=primary_lang,
            detected_languages=sorted(list(languages)),
            package_managers=sorted(list(pkg_managers)),
            test_frameworks=sorted(list(test_frameworks)),
            build_commands=sorted(list(build_cmds)),
            total_files=total_files,
            entry_points=entry_points,
        )

    def search_symbols(self, query: str, max_results: int = 15) -> List[Dict[str, Any]]:
        """Bounded search for function/class definitions matching query."""
        results = []
        regex = re.compile(rf"\b(def|class|function|interface|type)\s+([a-zA-Z0-9_]*{re.escape(query)}[a-zA-Z0-9_]*)", re.IGNORECASE)

        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in _IGNORED_DIRS]
            for file in files:
                if not (file.endswith(".py") or file.endswith(".ts") or file.endswith(".js")):
                    continue
                file_path = Path(root) / file
                rel_path = file_path.relative_to(self.root_path)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        for idx, line in enumerate(f, 1):
                            match = regex.search(line)
                            if match:
                                results.append({
                                    "file": str(rel_path).replace("\\", "/"),
                                    "line": idx,
                                    "symbol": match.group(2),
                                    "kind": match.group(1),
                                    "context": line.strip(),
                                })
                                if len(results) >= max_results:
                                    return results
                except Exception:
                    continue

        return results

    def find_files(self, pattern: str, max_results: int = 30) -> List[str]:
        """Finds relative file paths matching glob/name pattern."""
        matched = []
        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in _IGNORED_DIRS]
            for file in files:
                if pattern.lower() in file.lower():
                    rel = Path(root, file).relative_to(self.root_path)
                    matched.append(str(rel).replace("\\", "/"))
                    if len(matched) >= max_results:
                        return matched
        return matched
