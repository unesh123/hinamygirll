"""UI target location from accessible elements or OCR bounding tokens."""

from __future__ import annotations

from typing import Iterable

from .base import ScreenPoint


def locate_target(
    query: str,
    *,
    ocr_tokens: Iterable[dict] | None = None,
) -> ScreenPoint | None:
    """Resolve a spoken element label ('Send', 'Close') against OCR/UI bounding boxes."""
    clean = str(query or "").strip().lower()
    if not clean or not ocr_tokens:
        return None

    best: tuple[float, ScreenPoint] | None = None
    for tok in ocr_tokens:
        label = str(tok.get("text") or tok.get("label") or "").strip()
        if not label:
            continue
        low = label.lower()
        score = 1.0 if low == clean else (0.85 if clean in low else 0.0)
        if score <= 0.0:
            continue
        cx = int(tok.get("x", 0) + tok.get("width", 0) / 2)
        cy = int(tok.get("y", 0) + tok.get("height", 0) / 2)
        pt = ScreenPoint(x=cx, y=cy, confidence=score, label=label)
        if best is None or score > best[0]:
            best = (score, pt)
    return best[1] if best is not None else None
