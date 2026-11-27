"""Failure normalization and stable structural error fingerprinting."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def normalize_error(err: dict[str, Any]) -> dict[str, str]:
    """Strip volatile indices and numbers so identical structural failures hash identically."""
    loc = err.get("loc") or err.get("path") or []
    if isinstance(loc, str):
        path = [p for p in loc.split(".") if p and not p.isdigit()]
    else:
        path = [str(p) for p in loc if not isinstance(p, int) and not str(p).isdigit()]
    msg = str(err.get("msg") or err.get("error") or "")
    msg = re.sub(r"input_value=.*", "input_value=<redacted>", msg)
    msg = re.sub(r"\d+\.\d+", "<num>", msg)
    return {"path": ".".join(path), "type": str(err.get("type") or ""), "msg": msg}


def fingerprint(errors: list[dict[str, Any]] | dict[str, Any] | str) -> str:
    """Return a stable 16-char SHA256 fingerprint across structured errors."""
    if isinstance(errors, str):
        err_list: list[dict[str, Any]] = [{"type": "error", "msg": errors, "loc": []}]
    elif isinstance(errors, dict):
        err_list = [errors]
    else:
        err_list = [
            e if isinstance(e, dict) else {"type": "error", "msg": str(e), "loc": []}
            for e in (errors or [])
        ]
    norm = sorted(
        (normalize_error(e) for e in err_list),
        key=lambda d: (d["path"], d["type"], d["msg"]),
    )
    return hashlib.sha256(
        json.dumps(norm, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]


def errors_from_exception(exc: Exception) -> list[dict[str, Any]]:
    """Convert Pydantic ValidationError or runtime exceptions into normalizable error dicts."""
    errs_fn = getattr(exc, "errors", None)
    if callable(errs_fn):
        try:
            raw = errs_fn()
            if isinstance(raw, list) and raw:
                return [
                    {
                        "type": str(e.get("type") or "value_error"),
                        "msg": str(e.get("msg") or str(exc)),
                        "loc": list(e.get("loc") or []),
                    }
                    for e in raw
                    if isinstance(e, dict)
                ]
        except Exception as err_extract_exc:
            _ = str(err_extract_exc)
    return [{"type": type(exc).__name__, "msg": str(exc)[:300], "loc": []}]
