"""Git-backed repository snapshots per tool batch."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def snapshot(repo: str | Path, label: str) -> str:
    """Stage working tree state, create a labeled checkpoint commit, and return its SHA."""
    git_bin = shutil.which("git") or "git"
    repo_str = str(repo)
    subprocess.run([git_bin, "-C", repo_str, "add", "-A"], check=True)  # noqa: S603
    subprocess.run(  # noqa: S603
        [git_bin, "-C", repo_str, "commit", "-m", f"checkpoint: {label}", "--allow-empty"],
        check=True,
        capture_output=True,
    )
    return subprocess.run(  # noqa: S603
        [git_bin, "-C", repo_str, "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def revert(repo: str | Path, sha: str) -> None:
    """Hard-reset repo to a previously captured snapshot SHA."""
    git_bin = shutil.which("git") or "git"
    subprocess.run([git_bin, "-C", str(repo), "reset", "--hard", sha], check=True)  # noqa: S603
