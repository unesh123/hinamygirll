"""Runtime-state locations that work from a source checkout and from the container.

Several modules used to derive ``.runtime`` from a fixed ``parents[N]`` index.
That index only exists in a Windows checkout; inside the Linux image the source
is ``/app/hinaa_api`` and the index raised ``IndexError`` at import time.
"""
from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent


def project_root() -> Path:
    """Repository root for a source checkout, or the app root in the container.

    ``HINAA_PROJECT_ROOT`` overrides the walk. Otherwise the root is the first
    ancestor that contains ``apps/api``; if there is none (the container), the
    package's parent directory is used.
    """
    override = os.environ.get("HINAA_PROJECT_ROOT", "").strip()
    if override:
        return Path(override).resolve()
    for candidate in PACKAGE_DIR.parents:
        if (candidate / "apps" / "api").is_dir():
            return candidate
    return PACKAGE_DIR.parent


def runtime_dir(*parts: str) -> Path:
    """A path under ``<project root>/.runtime``, created on demand by callers."""
    return project_root().joinpath(".runtime", *parts)
