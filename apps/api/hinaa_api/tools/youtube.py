import asyncio
import webbrowser
from pydantic import BaseModel, Field

class PlayYoutubeVideoParams(BaseModel):
    query: str = Field(..., description="The name of the song, artist, or video to play on YouTube.")

async def play_youtube_video(params: PlayYoutubeVideoParams) -> str:
    """
    Searches YouTube for the given query and automatically plays the first result in the default browser.
    """
    try:
        # We use yt-dlp to grab just the video ID of the first search result
        cmd = [
            "python", "-m", "yt_dlp",
            f"ytsearch1:{params.query}",
            "--get-id",
            "--no-warnings"
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            return f"Failed to search YouTube. Error: {stderr.decode('utf-8').strip()}"
            
        video_id = stdout.decode("utf-8").strip()
        
        if not video_id:
            return f"Could not find any YouTube videos for: {params.query}"
            
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Open in default browser (which will auto-play on most desktop setups)
        webbrowser.open(video_url)
        
        return f"Successfully opened and started playing YouTube video: {video_url}"
    except Exception as e:
        return f"Error playing YouTube video: {str(e)}"

from hinaa_api.tools.registry import registry, ToolDefinition

youtube_playback_request_def = ToolDefinition(
    name="youtube_playback_request",
    display_name="Play YouTube Video",
    description="Searches YouTube for the given query and automatically plays the first result in the default browser.",
    parameters={
        "query": {
            "type": "string",
            "description": "The name of the song, artist, or video to play on YouTube."
        }
    },
    required_parameters=["query"],
    voice_aliases=["play", "listen to", "put on"],
    requires_confirmation=True
)

registry.register(youtube_playback_request_def, play_youtube_video)

