"""Persistent verification matrix tracking build, lint, render, and visual checks."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

DEFAULT_VERIFY_MATRIX_PATH = (
    Path(__file__).resolve().parents[4] / "apps" / "data" / "hina" / "verify_matrix.json"
)
_LOCK = threading.Lock()


class CheckEntry(BaseModel):
    target: str
    check_type: str
    passed: bool
    detail: str = ""
    recorded_at: float = Field(default_factory=time.time)


class VerificationMatrix(BaseModel):
    version: int = 1
    updated_at: float = Field(default_factory=time.time)
    checks: dict[str, dict[str, CheckEntry]] = Field(default_factory=dict)


def resolve_matrix_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    env_override = (os.environ.get("HINAA_VERIFY_MATRIX_PATH") or "").strip()
    if env_override:
        return Path(env_override)
    return DEFAULT_VERIFY_MATRIX_PATH


def load_matrix(path: str | Path | None = None) -> VerificationMatrix:
    p = resolve_matrix_path(path)
    if not p.is_file():
        return VerificationMatrix()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return VerificationMatrix.model_validate(raw)
    except Exception:
        return VerificationMatrix()


def _atomic_save(matrix: VerificationMatrix, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = matrix.model_dump_json(indent=2)
    fd, tmp_name = tempfile.mkstemp(prefix=".verify_matrix_", suffix=".json", dir=str(dest.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_name, dest)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass


def record_check(
    target: str,
    check_type: str,
    passed: bool,
    detail: str = "",
    *,
    path: str | Path | None = None,
) -> VerificationMatrix:
    """Record or update one verification cell atomically on disk."""
    norm_target = str(target or "").strip() or "workspace"
    norm_type = str(check_type or "").strip() or "check"
    dest = resolve_matrix_path(path)
    with _LOCK:
        matrix = load_matrix(dest)
        now = time.time()
        bucket = dict(matrix.checks.get(norm_target) or {})
        bucket[norm_type] = CheckEntry(
            target=norm_target,
            check_type=norm_type,
            passed=bool(passed),
            detail=str(detail or "")[:500],
            recorded_at=now,
        )
        matrix.checks[norm_target] = bucket
        matrix.updated_at = now
        _atomic_save(matrix, dest)
        return matrix


def get_matrix_status(path: str | Path | None = None) -> dict[str, Any]:
    """Return summary counts and all recorded verification cells."""
    matrix = load_matrix(path)
    total = 0
    passed_count = 0
    failed_targets: list[str] = []
    for target, types in matrix.checks.items():
        for ctype, entry in types.items():
            total += 1
            if entry.passed:
                passed_count += 1
            else:
                failed_targets.append(f"{target}:{ctype}")
    return {
        "total": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "allPassed": total > 0 and passed_count == total,
        "failedChecks": failed_targets,
        "updatedAt": matrix.updated_at,
        "targets": {
            t: {ct: e.model_dump() for ct, e in checks.items()}
            for t, checks in matrix.checks.items()
        },
    }


def reset_matrix(path: str | Path | None = None) -> None:
    dest = resolve_matrix_path(path)
    with _LOCK:
        if dest.is_file():
            dest.unlink()


__all__ = [
    "CheckEntry",
    "VerificationMatrix",
    "get_matrix_status",
    "load_matrix",
    "record_check",
    "reset_matrix",
    "resolve_matrix_path",
]
