"""Motion-graphics lyric-video generator."""

from .renderer import (
    RenderCancelled,
    build_html,
    build_page_data,
    render_lyric_video,
    tools_available,
)
from .spec import SCENE_PRESETS, LyricVideoSpec, pick_scene, resolve_timeline

__all__ = [
    "SCENE_PRESETS", "LyricVideoSpec", "RenderCancelled", "build_html", "build_page_data",
    "pick_scene", "render_lyric_video", "resolve_timeline", "tools_available",
]
