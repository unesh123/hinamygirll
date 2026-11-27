"""Post-action file verifiers per output modality."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any


def verify_video(
    path: str,
    expected_duration: float | None = None,
    tolerance: float = 0.15,
) -> dict[str, Any]:
    """Verify rendered video exists, passes ffprobe inspection, and matches duration."""
    ffprobe_bin = shutil.which("ffprobe") or "ffprobe"
    out = subprocess.run(  # noqa: S603
        [
            ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration,size",
            "-of",
            "json",
            path,
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    meta = json.loads(out)["format"]
    dur = float(meta["duration"])
    size = int(meta.get("size") or os.path.getsize(path))

    assert size > 100_000, f"file too small: {size} bytes"
    if expected_duration is not None:
        assert abs(dur - expected_duration) <= tolerance, (
            f"duration mismatch: got {dur:.2f}s, expected {expected_duration:.2f}s"
        )
    return {"duration": dur, "size": size, "ok": True}


def verify_image(path: str) -> dict[str, Any]:
    """Verify generated image decodes cleanly via Pillow and meets minimum pixel size."""
    from PIL import Image

    with Image.open(path) as im:
        im.verify()
    with Image.open(path) as im:
        w, h = im.size
    assert w >= 512 and h >= 512, f"undersized: {w}x{h}"
    return {"width": w, "height": h, "ok": True}


def verify_pdf(path: str) -> dict[str, Any]:
    """Verify generated PDF header and minimum size."""
    with open(path, "rb") as f:
        head = f.read(5)
    assert head == b"%PDF-", "not a valid PDF"
    assert os.path.getsize(path) > 5_000, "PDF suspiciously small"
    return {"ok": True}
