"""YouTube playback request tool.

Resolves a search query to a concrete YouTube URL and returns it as a
client-directed ``open_url`` action. If ``yt-dlp`` is installed the first
matching video is resolved server-side; otherwise the tool honestly falls
back to a YouTube search-results URL. The server never opens a browser
itself.
"""

import asyncio
import shutil
import sys
from urllib.parse import quote_plus

from pydantic import BaseModel, Field

from hinaa_api.tools.registry import registry, ToolDefinition


class PlayYoutubeVideoParams(BaseModel):
    query: str = Field(
        ..., description="The name of the song, artist, or video to play on YouTube."
    )


def _yt_dlp_available() -> bool:
    try:
        import yt_dlp  # noqa: F401

        return True
    except ImportError:
        return shutil.which("yt-dlp") is not None


async def _resolve_first_video_id(query: str) -> str | None:
    cmd = [sys.executable, "-m", "yt_dlp", f"ytsearch1:{query}", "--get-id", "--no-warnings"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
    except (OSError, asyncio.TimeoutError):
        return None
    if proc.returncode != 0:
        return None
    video_id = stdout.decode("utf-8").strip().splitlines()
    return video_id[0] if video_id else None


async def play_youtube_video(params: PlayYoutubeVideoParams) -> dict:
    query = params.query.strip()
    if not query:
        return {"status": "error", "error": "Query is required"}

    if _yt_dlp_available():
        video_id = await _resolve_first_video_id(query)
        if video_id:
            return {
                "status": "ok",
                "action": "open_url",
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "resolved": "first_search_result",
                "query": query,
            }

    # Honest fallback: no resolver available — return the search page.
    return {
        "status": "ok",
        "action": "open_url",
        "url": f"https://www.youtube.com/results?search_query={quote_plus(query)}",
        "resolved": "search_results_page",
        "query": query,
    }


youtube_playback_request_def = ToolDefinition(
    name="youtube_playback_request",
    display_name="Play YouTube Video",
    description=(
        "Resolves a YouTube video (or search page) URL for the requested song or "
        "video and returns it for the user's browser to open."
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "The name of the song, artist, or video to play on YouTube.",
        }
    },
    required_parameters=["query"],
    voice_aliases=["play", "listen to", "put on"],
    requires_confirmation=True,
)

registry.register(youtube_playback_request_def, play_youtube_video)
