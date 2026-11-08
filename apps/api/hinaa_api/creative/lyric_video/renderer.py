"""Deterministic lyric-video renderer: frame-clocked HTML -> headless Chromium -> ffmpeg."""
# ruff: noqa: E501, S603, S607

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from .spec import LyricVideoSpec, probe_duration, resolve_timeline

_DIR = Path(__file__).parent
ProgressCb = Callable[[float, str], None]


class RenderCancelled(Exception):
    """Raised when the cancel event is set mid-render."""


def _script_json(data: dict) -> str:
    """JSON safe to embed inside <script>: no raw '<', '>', '&' or line separators."""
    return (
        json.dumps(data, ensure_ascii=False)
        .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    )


def build_page_data(spec: LyricVideoSpec, audio_duration: float | None = None) -> dict:
    lines, total = resolve_timeline(spec, audio_duration)
    w, h = (1080, 1920) if spec.aspect == "9:16" else (1920, 1080) if spec.aspect == "16:9" else (1080, 1080)
    data: dict = {
        "title": spec.title, "width": w, "height": h, "fps": spec.fps, "total": total,
        "palette": spec.palette.model_dump(),
        "lines": [line.model_dump() for line in lines],
        "stickers": [s.model_dump() for s in spec.stickers if s.at < total],
        "character_data": None,
    }
    if spec.character_image:
        raw = Path(spec.character_image).read_bytes()
        data["character_data"] = "data:image/png;base64," + base64.b64encode(raw).decode()
    return data


def build_html(data: dict) -> str:
    return (
        (_DIR / "template.html").read_text(encoding="utf-8")
        .replace("__CSS__", (_DIR / "stage.css").read_text(encoding="utf-8"))
        .replace("__JS__", (_DIR / "stage.js").read_text(encoding="utf-8"))
        .replace("__SPEC__", _script_json(data))
    )


def tools_available() -> bool:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        return False
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            return Path(pw.chromium.executable_path).exists()
    except Exception:
        return False


def _ffmpeg_err(path: Path) -> str:
    try:
        return path.read_text(errors="replace")[-600:]
    except Exception:
        return "(no ffmpeg output)"


def render_lyric_video(
    spec: LyricVideoSpec,
    out_path: str | Path,
    progress: ProgressCb | None = None,
    cancel: threading.Event | None = None,
) -> dict:
    """Render ``spec`` to ``out_path`` (MP4). Blocking; run in a worker thread."""
    from playwright.sync_api import sync_playwright

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report = progress or (lambda _p, _l: None)
    audio_dur = probe_duration(spec.audio_path) if spec.audio_path else None
    data = build_page_data(spec, audio_dur)
    total_frames = round(data["total"] * spec.fps)
    out_w, out_h = spec.size
    scale = out_w / data["width"]
    jpeg_q = 88 if spec.draft else 93

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(spec.fps), "-c:v", "mjpeg", "-i", "-"]
    if spec.audio_path:
        cmd += ["-i", spec.audio_path]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += [
        "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "ultrafast" if spec.draft else "veryfast",
        # MJPEG frames decode as full-range yuvj420p; some ffmpeg builds keep that
        # range despite -pix_fmt, so convert to TV-range yuv420p explicitly.
        "-crf", "23" if spec.draft else "20", "-vf", "scale=out_range=tv,format=yuv420p",
        "-pix_fmt", "yuv420p", "-r", str(spec.fps),
        "-c:a", "aac", "-b:a", "192k", "-t", f"{data['total']:.3f}", "-shortest", "-movflags", "+faststart", str(out_path),
    ]

    report(2.0, "Launching renderer")
    with tempfile.TemporaryDirectory(prefix="lyricvid_") as tmp:
        page_file = Path(tmp) / "index.html"
        page_file.write_text(build_html(data), encoding="utf-8")
        log_path = Path(tmp) / "ffmpeg.log"
        err_file = open(log_path, "wb")
        ff = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=err_file)
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(args=["--disable-gpu", "--font-render-hinting=none", "--hide-scrollbars"])
                try:
                    page = browser.new_page(viewport={"width": data["width"], "height": data["height"]})
                    page.goto(page_file.as_uri())
                    page.wait_for_function("window.__ready === true", timeout=30000)
                    cdp = page.context.new_cdp_session(page)
                    clip = {"x": 0, "y": 0, "width": data["width"], "height": data["height"], "scale": scale}
                    for n in range(total_frames):
                        if cancel is not None and cancel.is_set():
                            raise RenderCancelled()
                        page.evaluate("n => window.__setFrame(n)", n)
                        shot = cdp.send(
                            "Page.captureScreenshot",
                            {"format": "jpeg", "quality": jpeg_q, "clip": clip, "optimizeForSpeed": True},
                        )
                        try:
                            ff.stdin.write(base64.b64decode(shot["data"]))
                        except BrokenPipeError as exc:
                            raise RuntimeError("ffmpeg exited early: " + _ffmpeg_err(log_path)) from exc
                        if n % 5 == 0:
                            report(5.0 + 90.0 * n / total_frames, f"Rendering frame {n + 1}/{total_frames}")
                finally:
                    browser.close()
            ff.stdin.close()
            report(96.0, "Encoding final video")
            if ff.wait(timeout=300) != 0:
                raise RuntimeError("ffmpeg failed: " + _ffmpeg_err(log_path))
        except BaseException:
            if ff.poll() is None:
                ff.kill()
                ff.wait()
            out_path.unlink(missing_ok=True)
            raise
        finally:
            err_file.close()
    report(100.0, "Render complete")
    return {
        "path": str(out_path), "duration": data["total"], "width": out_w, "height": out_h,
        "fps": spec.fps, "frames": total_frames, "lines": data["lines"],
    }
