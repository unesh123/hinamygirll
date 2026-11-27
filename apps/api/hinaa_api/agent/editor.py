"""Exact-match str_replace file editor with read-back verification."""
from __future__ import annotations

from pathlib import Path
from typing import Any


class EditError(Exception):
    """Raised when an exact edit anchor is missing, ambiguous, or fails write verification."""


def str_replace(path: str | Path, old: str, new: str, count: int = 1) -> dict[str, Any]:
    """Replace an exact unambiguous text span in path and verify written contents on disk."""
    target = str(path)
    with open(target, encoding="utf-8") as f:
        src = f.read()

    occurrences = src.count(old)
    if occurrences == 0:
        raise EditError(f"anchor not found in {target}: {old[:80]!r}")
    if occurrences > count:
        raise EditError(f"anchor ambiguous in {target}: {occurrences} matches")

    updated = src.replace(old, new, count)
    with open(target, "w", encoding="utf-8") as f:
        f.write(updated)

    with open(target, encoding="utf-8") as f:
        if new not in f.read():
            raise EditError(f"write verification failed for {target}")

    return {"path": target, "replaced": count, "delta": len(updated) - len(src)}
