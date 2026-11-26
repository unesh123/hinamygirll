"""Compile a validated local scene graph to a deterministic, offline Canvas document."""

import base64
import json
from pathlib import Path

from .spec import MotionComposition

MAX_MEDIA_BYTES = 24 * 1024 * 1024
_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}


def confined_path(raw: str, workspace: Path) -> Path:
    """Resolve symlinks before checking the boundary; never allow remote media."""
    root = workspace.resolve()
    path = (root / raw).resolve()
    if path != root and root not in path.parents:
        raise ValueError("Motion media must remain inside the selected workspace")
    if not path.is_file():
        raise ValueError(f"Motion media file does not exist: {raw}")
    return path


def compile_composition(
    spec: MotionComposition, workspace: Path, width: int = 1080, height: int = 1920
) -> str:
    data = spec.model_dump(mode="json")
    used_bytes = 0
    media: dict[str, str] = {}
    for scene in data["scenes"]:
        for layer in scene["layers"]:
            if layer["kind"] not in ("image", "video"):
                continue
            raw = layer["path"]
            path = confined_path(raw, workspace)
            ext = path.suffix.lower()
            allowed = (
                (".mp4", ".webm")
                if layer["kind"] == "video"
                else (".png", ".jpg", ".jpeg", ".webp")
            )
            if ext not in allowed:
                raise ValueError(f"Unsupported {layer['kind']} media type: {ext}")
            key = str(path)
            if key not in media:
                used_bytes += path.stat().st_size
                if used_bytes > MAX_MEDIA_BYTES:
                    raise ValueError(
                        "Embedded motion media exceeds 24 MiB; trim/compress source assets first"
                    )
                with path.open("rb") as source:
                    content = source.read(MAX_MEDIA_BYTES + 1)
                if len(content) > MAX_MEDIA_BYTES:
                    raise ValueError("Motion media exceeds 24 MiB")
                media[key] = f"data:{_MIME[ext]};base64," + base64.b64encode(content).decode(
                    "ascii"
                )
            layer["src"] = media[key]
            del layer["path"]
    data.update(width=width, height=height)
    packed = (
        json.dumps(data, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    script = (Path(__file__).parent / "stage.js").read_text(encoding="utf-8")
    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HINA Motion Studio</title><style>
*{{box-sizing:border-box}}
html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:#0c1019}}
canvas{{display:block;width:100%;height:100%;object-fit:contain}}
</style></head><body><canvas id="motion" width="{width}" height="{height}"></canvas>
<script>const COMPOSITION={packed};\n{script}</script></body></html>'''
