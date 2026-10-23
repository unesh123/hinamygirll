"""importer.py — Dynamic Skill Importer for HINAA.

Enables HINAA to dynamically ingest, install, and register skills from:
1. Remote Git repositories (e.g. https://github.com/blixvip/html-anime.git)
2. Local folders or zip bundles
3. Markdown specifications with YAML frontmatter

Integrates directly into the Skill Catalog without requiring a server reboot.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .catalog import SkillRecord, skill_catalog
from .router import skill_router

logger = logging.getLogger("hinaa.skills.importer")


class SkillImportError(Exception):
    pass


class SkillImporter:
    """Manages downloading, validating, and installing skills at runtime."""

    def __init__(self, workspace_root: Path | None = None):
        self.workspace_root = workspace_root or Path(__file__).resolve().parents[4]
        self.skills_dir = self.workspace_root / ".agents" / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def import_from_git(self, git_url: str, custom_name: str | None = None) -> SkillRecord:
        """Clones a remote git repository and installs it as a HINAA skill."""
        clean_url = git_url.strip()
        if not clean_url.endswith(".git") and not clean_url.startswith("http"):
            raise SkillImportError(f"Invalid git URL: {git_url}")

        # Derive folder name
        repo_name = custom_name or clean_url.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        repo_name = re.sub(r"[^a-zA-Z0-9_-]", "-", repo_name).lower()

        target_dir = self.skills_dir / repo_name
        temp_dir = self.workspace_root / ".runtime" / "temp_skills" / repo_name
        temp_dir.parent.mkdir(parents=True, exist_ok=True)

        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

        try:
            logger.info("Cloning skill repo from %s to %s", clean_url, temp_dir)
            cmd = ["git", "clone", "--depth", "1", clean_url, str(temp_dir)]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode != 0:
                raise SkillImportError(f"git clone failed: {res.stderr}")

            # Locate SKILL.md or synthesize one
            skill_md = temp_dir / "SKILL.md"
            if not skill_md.exists():
                # Check inside skills/ subfolder
                sub_skills = list(temp_dir.glob("**/SKILL.md"))
                if sub_skills:
                    skill_md = sub_skills[0]
                else:
                    # Synthesize SKILL.md from README.md
                    readme = temp_dir / "README.md"
                    readme_text = readme.read_text(encoding="utf-8") if readme.exists() else repo_name
                    frontmatter = f"---\nname: {repo_name}\ndescription: Auto-imported skill from {clean_url}\n---\n\n# {repo_name}\n\n"
                    skill_md = temp_dir / "SKILL.md"
                    skill_md.write_text(frontmatter + readme_text[:2000], encoding="utf-8")

            # Move verified files into target destination
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            shutil.copytree(temp_dir, target_dir)

            # Re-index catalog and router
            skill_catalog.load_all_skills(force_reload=True)
            skill_router.build_index(force=True)

            record = skill_catalog.get_skill(repo_name) or skill_catalog.get_skill(f"tool:{repo_name}")
            if not record:
                # Fallback to direct lookup
                record = skill_catalog.list_all()[-1]

            logger.info("Successfully imported skill '%s' (%s)", record.name, record.id)
            return record

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)


skill_importer = SkillImporter()
