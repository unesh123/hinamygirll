"""Frame-by-frame video inspection utility and agentic tool (`video_inspect_frames`)."""

from __future__ import annotations

import base64
import io
import logging
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw
from pydantic import BaseModel, Field

from ..tools.registry import RiskTier, ToolDefinition, ToolEffect, registry
from .asset_store import AssetSource, get_asset_store
from .extractors import _get_ffmpeg_bin

logger = logging.getLogger("hinaa.media.video_inspector")

MAX_VIDEO_INSPECT_BYTES = 100 * 1024 * 1024  # 100 MB
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".mpeg", ".mpg"})


def _fmt_timecode(sec: float) -> str:
    s = max(0.0, float(sec))
    mins = int(s // 60)
    rem = s - mins * 60
    return f"{mins:02d}:{rem:05.2f}"


def _probe_video_metadata(video_path: str, ffmpeg_bin: str) -> dict[str, Any]:
    proc = subprocess.run(
        [ffmpeg_bin, "-i", video_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        timeout=20,
    )
    probe = proc.stderr or ""
    duration_sec = 0.0
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", probe)
    if dur_match:
        h, m, s = dur_match.groups()
        duration_sec = int(h) * 3600 + int(m) * 60 + float(s)

    res_match = re.search(r"Video:[^\n]*?,\s*(\d{2,5})x(\d{2,5})", probe)
    width = int(res_match.group(1)) if res_match else 0
    height = int(res_match.group(2)) if res_match else 0

    fps_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:fps|tbr)", probe)
    fps = float(fps_match.group(1)) if fps_match else 30.0
    if fps <= 0:
        fps = 30.0

    codec_match = re.search(r"Video:\s*([a-zA-Z0-9_\-]+)", probe)
    video_codec = codec_match.group(1) if codec_match else "unknown"

    audio_match = re.search(r"Audio:\s*([a-zA-Z0-9_\-]+)", probe)
    audio_codec = audio_match.group(1) if audio_match else None

    return {
        "duration_seconds": round(duration_sec, 3),
        "fps": round(fps, 3),
        "total_frames_est": max(1, int(round(duration_sec * fps))) if duration_sec > 0 else 1,
        "width": width,
        "height": height,
        "resolution": f"{width}x{height}" if width and height else "unknown",
        "video_codec": video_codec,
        "audio_codec": audio_codec,
        "has_audio": audio_codec is not None,
    }


def _make_contact_sheet(
    tiles: list[tuple[int, float, int, bytes]],
    *,
    cols: int = 3,
    tile_w: int = 384,
    tile_h: int = 216,
) -> bytes:
    if not tiles:
        return b""
    cols = min(cols, len(tiles))
    rows = int(math.ceil(len(tiles) / cols))
    pad = 8
    sheet_w = cols * tile_w + (cols + 1) * pad
    sheet_h = rows * tile_h + (rows + 1) * pad
    canvas = Image.new("RGB", (sheet_w, sheet_h), (12, 16, 28))
    draw = ImageDraw.Draw(canvas)

    for idx, (frame_idx, ts, frame_no, raw_jpg) in enumerate(tiles):
        r = idx // cols
        c = idx % cols
        x0 = pad + c * (tile_w + pad)
        y0 = pad + r * (tile_h + pad)
        try:
            with Image.open(io.BytesIO(raw_jpg)) as im:
                rgb = im.convert("RGB")
                rgb.thumbnail((tile_w, tile_h), Image.Resampling.LANCZOS)
                px = x0 + (tile_w - rgb.width) // 2
                py = y0 + (tile_h - rgb.height) // 2
                canvas.paste(rgb, (px, py))
        except Exception:
            pass
        draw.rectangle([x0, y0, x0 + tile_w - 1, y0 + tile_h - 1], outline=(51, 65, 85), width=1)
        label = f"F{frame_idx} | {_fmt_timecode(ts)} (#{frame_no})"
        badge_w = min(tile_w - 8, max(124, len(label) * 7 + 14))
        draw.rectangle([x0 + 4, y0 + 4, x0 + 4 + badge_w, y0 + 24], fill=(15, 23, 42))
        draw.text((x0 + 9, y0 + 8), label, fill=(248, 250, 252))

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=84)
    return buf.getvalue()


def inspect_video_frames(
    video_path: str | Path,
    *,
    start_sec: float = 0.0,
    end_sec: float | None = None,
    num_frames: int = 6,
    store_frames: bool = False,
) -> dict[str, Any]:
    """Extract timestamped JPEG frames + labeled contact sheet from a video file."""
    path_str = str(video_path)
    ffmpeg_bin = _get_ffmpeg_bin()
    meta = _probe_video_metadata(path_str, ffmpeg_bin)
    dur = float(meta["duration_seconds"] or 0.0)
    fps = float(meta["fps"] or 30.0)

    s_sec = max(0.0, float(start_sec or 0.0))
    if dur > 0 and s_sec >= dur:
        s_sec = max(0.0, dur - 0.5)
    e_sec = float(end_sec) if (end_sec is not None and end_sec > s_sec) else dur
    if dur > 0:
        e_sec = min(dur, max(s_sec, e_sec))

    count = max(1, min(int(num_frames or 6), 12))
    span = max(0.0, e_sec - s_sec)
    if span <= 0.05 or count == 1:
        timestamps = [round(s_sec, 3)]
    else:
        step = span / max(count - 1, 1)
        timestamps = [round(min(max(0.0, e_sec - 0.04), s_sec + i * step), 3) for i in range(count)]

    store = get_asset_store() if store_frames else None
    extracted_frames: list[dict[str, Any]] = []
    sheet_tiles: list[tuple[int, float, int, bytes]] = []

    with tempfile.TemporaryDirectory(prefix="hinaa_vframes_") as tmp_dir:
        for idx, ts in enumerate(timestamps, start=1):
            out_jpg = Path(tmp_dir) / f"frame_{idx:02d}.jpg"
            cmd = [
                ffmpeg_bin,
                "-y",
                "-ss",
                f"{ts:.3f}",
                "-i",
                path_str,
                "-vframes",
                "1",
                "-vf",
                "scale='min(960,iw)':-2",
                "-q:v",
                "3",
                str(out_jpg),
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            if not out_jpg.is_file() or out_jpg.stat().st_size == 0:
                continue
            raw_jpg = out_jpg.read_bytes()
            frame_no = max(0, int(round(ts * fps)))
            tc = _fmt_timecode(ts)
            b64 = base64.b64encode(raw_jpg).decode("ascii")
            data_url = f"data:image/jpeg;base64,{b64}"

            frame_asset_id = None
            frame_url = None
            if store is not None:
                ref = store.store_bytes(
                    raw_jpg,
                    filename=f"frame_{idx:02d}_{ts:.2f}s.jpg",
                    mime_type="image/jpeg",
                    source=AssetSource.GENERATED,
                )
                frame_asset_id = ref.id
                frame_url = ref.public_url

            sheet_tiles.append((idx, ts, frame_no, raw_jpg))
            extracted_frames.append(
                {
                    "index": idx,
                    "frame_number": frame_no,
                    "timestamp_sec": ts,
                    "timestamp_label": tc,
                    "size_bytes": len(raw_jpg),
                    "data_url": data_url,
                    "asset_id": frame_asset_id,
                    "asset_url": frame_url,
                }
            )

    contact_bytes = _make_contact_sheet(sheet_tiles)
    contact_data_url = (
        f"data:image/jpeg;base64,{base64.b64encode(contact_bytes).decode('ascii')}"
        if contact_bytes
        else None
    )
    contact_asset_id = None
    contact_url = None
    if contact_bytes and store is not None:
        cref = store.store_bytes(
            contact_bytes,
            filename="video_contact_sheet.jpg",
            mime_type="image/jpeg",
            source=AssetSource.GENERATED,
        )
        contact_asset_id = cref.id
        contact_url = cref.public_url

    frame_lines = [
        f"  - Frame #{f['index']} @ {f['timestamp_label']} (approx frame #{f['frame_number']})"
        for f in extracted_frames
    ]
    summary_text = "\n".join(
        [
            f"Video Frame-by-Frame Inspection ({meta['resolution']}, {meta['video_codec']}, {meta['fps']} FPS, duration {dur:.2f}s):",
            f"- Audio stream: {meta['audio_codec'] or 'none'}",
            f"- Window inspected: {_fmt_timecode(s_sec)} -> {_fmt_timecode(e_sec)} ({len(extracted_frames)} frames extracted)",
            *frame_lines,
        ]
    )

    return {
        "status": "success" if extracted_frames else "error",
        "metadata": meta,
        "window": {"start_sec": s_sec, "end_sec": e_sec},
        "frames": extracted_frames,
        "contact_sheet_bytes": contact_bytes,
        "contact_sheet_data_url": contact_data_url,
        "contact_sheet_asset_id": contact_asset_id,
        "contact_sheet_url": contact_url,
        "summary_text": summary_text,
    }


class VideoInspectFramesParams(BaseModel):
    asset_id: str | None = Field(None, description="Uploaded video asset_id (from /api/v1/assets or /api/v1/media/inspect-video).")
    file_path: str | None = Field(None, description="Optional relative workspace video file path (.mp4, .mov, .webm, etc.).")
    start_sec: float = Field(0.0, ge=0.0, description="Start time in seconds to inspect.")
    end_sec: float | None = Field(None, ge=0.0, description="Optional end time in seconds.")
    num_frames: int = Field(6, ge=1, le=12, description="Number of timestamped frames to extract (1-12).")
    workspace_root: str | None = Field(None, description="Optional workspace root override.")


async def video_inspect_frames_handler(params: VideoInspectFramesParams) -> dict[str, Any]:
    import asyncio
    from ..tools.workspace_coding_tools import _resolve_inside_workspace, _resolve_workspace_root

    target_path: Path | None = None
    if params.asset_id:
        aid = str(params.asset_id).strip()
        target_path = get_asset_store().get_file_path(aid)
        if target_path is None or not target_path.is_file():
            return {"status": "error", "code": "ASSET_NOT_FOUND", "error": f"Video asset not found: {aid}"}
    elif params.file_path:
        try:
            root = _resolve_workspace_root(params.workspace_root)
            target_path = _resolve_inside_workspace(root, params.file_path)
        except ValueError as err:
            return {"status": "error", "code": "WORKSPACE_ESCAPE", "error": str(err)}
        if not target_path.is_file():
            return {"status": "error", "code": "FILE_NOT_FOUND", "error": f"Video file not found: {params.file_path}"}
    else:
        return {"status": "error", "code": "MISSING_VIDEO_SOURCE", "error": "Provide either asset_id or file_path."}

    res = await asyncio.to_thread(
        inspect_video_frames,
        target_path,
        start_sec=params.start_sec,
        end_sec=params.end_sec,
        num_frames=params.num_frames,
        store_frames=True,
    )
    if res["status"] != "success":
        return {"status": "error", "code": "VIDEO_INSPECT_FAILED", "error": "Could not extract video frames."}

    preview_path = None
    if res.get("contact_sheet_bytes"):
        tmp_sheet = tempfile.NamedTemporaryFile(suffix=".jpg", prefix="hinaa_vsheet_", delete=False)
        tmp_sheet.write(res["contact_sheet_bytes"])
        tmp_sheet.close()
        preview_path = tmp_sheet.name

    return {
        "status": "success",
        "metadata": res["metadata"],
        "window": res["window"],
        "summary": res["summary_text"],
        "contactSheetUrl": res.get("contact_sheet_url"),
        "frames": [
            {
                "index": f["index"],
                "frameNumber": f["frame_number"],
                "timestampSec": f["timestamp_sec"],
                "timestampLabel": f["timestamp_label"],
                "assetId": f.get("asset_id"),
                "assetUrl": f.get("asset_url"),
            }
            for f in res["frames"]
        ],
        "_vision_preview_path": preview_path,
    }


registry.register(
    ToolDefinition(
        name="video_inspect_frames",
        display_name="Media: Inspect Video Frame-by-Frame",
        description=(
            "Inspect an uploaded video (by asset_id) or workspace video file (by file_path) frame-by-frame "
            "over any [start_sec, end_sec] time window. Extracts timestamped frames and renders a labeled "
            "contact sheet visual preview for detailed motion, UI, and scene critique."
        ),
        parameters={
            "asset_id": {"type": "string", "description": "Uploaded video asset ID."},
            "file_path": {"type": "string", "description": "Workspace relative path to video file."},
            "start_sec": {"type": "number", "description": "Start timestamp in seconds (default 0.0)."},
            "end_sec": {"type": "number", "description": "Optional end timestamp in seconds."},
            "num_frames": {"type": "integer", "description": "Number of frames to extract across window (1-12, default 6)."},
            "workspace_root": {"type": "string", "description": "Optional workspace root override."},
        },
        required_parameters=[],
        is_read_only=True,
        is_concurrency_safe=True,
        requires_confirmation=False,
        risk_tier=RiskTier.TIER_0_READ_ONLY,
        risk_level="low",
        tool_effect=ToolEffect.READ,
        timeout_seconds=45,
    ),
    video_inspect_frames_handler,
)
