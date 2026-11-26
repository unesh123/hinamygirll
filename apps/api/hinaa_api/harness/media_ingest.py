"""Phase 7 Media References at Scale: streaming ingest, SHA-256 dedupe, ffprobe/Pillow/audio insight extraction."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

MAX_IMAGE_FILES = 50
MAX_SINGLE_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB streaming cap


class MediaInsight(BaseModel):
    media_id: str
    filename: str
    kind: str  # image | video | audio | document
    mime_type: str
    size_bytes: int
    sha256: str
    stored_path: str
    storyboard_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    aspect: Optional[str] = None
    duration_sec: Optional[float] = None
    fps: Optional[float] = None
    has_audio: Optional[bool] = None
    sample_rate: Optional[int] = None
    palette: List[str] = Field(default_factory=list)
    summary: str = ""
    headings: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _safe_filename(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name or "attachment.bin").name)
    return clean[:120] or "attachment.bin"


def _classify_kind(mime_type: str, ext: str) -> str:
    low_m = (mime_type or "").lower()
    low_e = (ext or "").lower()
    if low_m.startswith("image/") or low_e in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
        return "image"
    if low_m.startswith("video/") or low_e in {".mp4", ".mov", ".webm", ".mkv", ".avi"}:
        return "video"
    if low_m.startswith("audio/") or low_e in {".mp3", ".wav", ".ogg", ".m4a", ".flac"}:
        return "audio"
    return "document"


def _analyze_image(path: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {"width": None, "height": None, "aspect": None, "palette": [], "summary": ""}
    try:
        from PIL import Image

        with Image.open(path) as img:
            w, h = img.size
            out["width"] = w
            out["height"] = h
            from math import gcd

            g = gcd(w, h) if w > 0 and h > 0 else 1
            out["aspect"] = f"{w // g}:{h // g}" if g else None
            thumb = img.convert("RGB").resize((24, 24))
            quant = thumb.quantize(colors=4).convert("RGB")
            colors = quant.getcolors(maxcolors=64) or []
            colors.sort(key=lambda item: item[0], reverse=True)
            out["palette"] = [f"#{r:02x}{g2:02x}{b:02x}" for _, (r, g2, b) in colors[:4]]
            out["summary"] = f"Image {w}x{h} ({out['aspect']}), dominant colors {', '.join(out['palette'][:3])}."
    except Exception as exc:
        out["summary"] = f"Image asset ({path.name}); pillow metadata unavailable: {exc}"
    return out


def _analyze_video(path: Path, media_dir: Path, media_id: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "width": None,
        "height": None,
        "duration_sec": None,
        "fps": None,
        "has_audio": False,
        "sample_rate": None,
        "storyboard_path": None,
        "summary": "",
    }
    ffprobe_bin = shutil.which("ffprobe")
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffprobe_bin:
        try:
            proc = subprocess.run(
                [
                    ffprobe_bin,
                    "-v",
                    "error",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                meta = json.loads(proc.stdout)
                fmt = meta.get("format") or {}
                if fmt.get("duration"):
                    out["duration_sec"] = round(float(fmt["duration"]), 2)
                for st in meta.get("streams") or []:
                    if st.get("codec_type") == "video" and out["width"] is None:
                        out["width"] = int(st.get("width") or 0) or None
                        out["height"] = int(st.get("height") or 0) or None
                        rfr = str(st.get("r_frame_rate") or "0/1")
                        if "/" in rfr:
                            num, den = rfr.split("/", 1)
                            d = float(den or 1)
                            if d > 0:
                                out["fps"] = round(float(num or 0) / d, 2)
                    elif st.get("codec_type") == "audio":
                        out["has_audio"] = True
                        if st.get("sample_rate"):
                            out["sample_rate"] = int(st["sample_rate"])
        except Exception:
            pass

    if ffmpeg_bin:
        sb_file = media_dir / f"{media_id}_storyboard.png"
        try:
            proc = subprocess.run(
                [
                    ffmpeg_bin,
                    "-y",
                    "-i",
                    str(path),
                    "-vf",
                    "fps=1,scale=160:-1,tile=4x2",
                    "-frames:v",
                    "1",
                    str(sb_file),
                ],
                capture_output=True,
                timeout=25,
            )
            if proc.returncode == 0 and sb_file.is_file():
                out["storyboard_path"] = str(sb_file)
        except Exception:
            pass

    out["summary"] = (
        f"Video {out['width']}x{out['height']} @ {out['fps']}fps, "
        f"duration={out['duration_sec']}s, audio={out['has_audio']}."
    )
    return out


def _analyze_document(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    words = len(text.split())
    headings = [ln.strip()[:120] for ln in lines if ln.lstrip().startswith("#")][:30]
    return {
        "headings": headings,
        "summary": f"Document {path.name}: {len(lines)} lines, {words} words, {len(headings)} headings.",
    }


def _index_path(state_dir: Path, task_id: str) -> Path:
    d = state_dir / f"{task_id}_media"
    d.mkdir(parents=True, exist_ok=True)
    return d / "insights.json"


def load_media_insights(state_dir: Path, task_id: str) -> List[MediaInsight]:
    idx = _index_path(state_dir, task_id)
    if not idx.is_file():
        return []
    try:
        raw = json.loads(idx.read_text(encoding="utf-8"))
        return [MediaInsight.model_validate(item) for item in raw if isinstance(item, dict)]
    except Exception:
        return []


def save_media_insights(state_dir: Path, task_id: str, items: List[MediaInsight]) -> None:
    idx = _index_path(state_dir, task_id)
    idx.write_text(json.dumps([i.model_dump() for i in items], indent=2), encoding="utf-8")


async def ingest_streamed_attachment(
    *,
    state_dir: Path,
    task_id: str,
    upload_file: Any,
) -> MediaInsight:
    """Stream an UploadFile to disk without full buffering, deduplicate by SHA-256, and index derived MediaInsight."""
    media_dir = state_dir / f"{task_id}_media"
    media_dir.mkdir(parents=True, exist_ok=True)
    existing = load_media_insights(state_dir, task_id)

    orig_name = _safe_filename(getattr(upload_file, "filename", "upload.bin"))
    ext = Path(orig_name).suffix.lower()
    mime = (getattr(upload_file, "content_type", None) or mimetypes.guess_type(orig_name)[0] or "application/octet-stream").strip()
    kind = _classify_kind(mime, ext)

    if kind == "image" and sum(1 for item in existing if item.kind == "image") >= MAX_IMAGE_FILES:
        raise ValueError(f"Image attachment limit reached ({MAX_IMAGE_FILES} max per task)")

    temp_path = media_dir / f".tmp_{orig_name}"
    hasher = hashlib.sha256()
    total = 0
    with temp_path.open("wb") as out_fp:
        while True:
            chunk = await upload_file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_SINGLE_UPLOAD_BYTES:
                out_fp.close()
                temp_path.unlink(missing_ok=True)
                raise ValueError(f"Attachment exceeds {MAX_SINGLE_UPLOAD_BYTES // (1024 * 1024)} MB cap")
            hasher.update(chunk)
            out_fp.write(chunk)

    digest = hasher.hexdigest()
    for prev in existing:
        if prev.sha256 == digest:
            temp_path.unlink(missing_ok=True)
            return prev

    media_id = f"med_{digest[:10]}"
    final_path = media_dir / f"{media_id}_{orig_name}"
    temp_path.replace(final_path)

    details: Dict[str, Any] = {}
    if kind == "image":
        details = _analyze_image(final_path)
    elif kind == "video":
        details = _analyze_video(final_path, media_dir, media_id)
    elif kind == "audio":
        details = {"has_audio": True, "summary": f"Audio asset {orig_name} ({total} bytes)."}
    else:
        details = _analyze_document(final_path)

    insight = MediaInsight(
        media_id=media_id,
        filename=orig_name,
        kind=kind,
        mime_type=mime,
        size_bytes=total,
        sha256=digest,
        stored_path=str(final_path),
        **details,
    )
    existing.append(insight)
    save_media_insights(state_dir, task_id, existing)
    return insight
