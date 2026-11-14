"""Fail-closed local validation before a video becomes a registered artifact."""
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path


def validate_video(data: bytes, suffix: str) -> dict:
    if len(data) > 128 * 1024 * 1024:
        raise ValueError("Video exceeds the 128 MiB validation limit.")
    probe, decoder = shutil.which("ffprobe"), shutil.which("ffmpeg")
    if not probe or not decoder:
        raise ValueError("Video validation requires ffprobe and ffmpeg; output is not registered.")
    with tempfile.TemporaryDirectory(prefix="hinaa-video-check-") as directory:
        path = Path(directory) / ("input" + suffix)
        path.write_bytes(data)
        try:
            result = subprocess.run([
                probe, "-v", "error", "-protocol_whitelist", "file,pipe",
                "-show_streams", "-show_format", "-of", "json", str(path),
            ], capture_output=True, timeout=15, check=True)
            metadata = json.loads(result.stdout)
            stream = next(s for s in metadata.get("streams", []) if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic"))
            width, height = int(stream.get("width", 0)), int(stream.get("height", 0))
            duration = float(stream.get("duration") or metadata.get("format", {}).get("duration") or 0)
            if width <= 0 or height <= 0 or width * height > 3840 * 2160 or not math.isfinite(duration) or not 0 < duration <= 300:
                raise ValueError("Video dimensions or duration are invalid or exceed validation limits.")
            # Probe alone can accept a truncated payload. Decode all frames before registration.
            subprocess.run([
                decoder, "-nostdin", "-v", "error", "-xerror", "-threads", "2",
                "-protocol_whitelist", "file,pipe", "-i", str(path),
                "-map", "0:v:0", "-an", "-f", "null", "-",
            ], capture_output=True, timeout=45, check=True)
            numerator, denominator = str(stream.get("avg_frame_rate", "0/1")).split("/")
            fps = float(numerator) / float(denominator) if float(denominator) else 0
            return {"width": width, "height": height, "duration_seconds": duration, "fps": fps, "codec": stream.get("codec_name")}
        except (subprocess.SubprocessError, OSError, ValueError, StopIteration, TypeError, KeyError) as exc:
            raise ValueError("Video validation failed: output must contain a complete decodable video stream within supported limits.") from exc
