"""Verified, confirmation-gated YouTube playback for HINAA.

This tool deliberately uses HINAA's existing owned Playwright page. Opening a URL
is never considered playback: completion requires an unpaused ready media element
whose playback time advances across two observed samples.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

from pydantic import BaseModel, Field, field_validator
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from hinaa_api.tools.browser_automation import _get_page
from hinaa_api.tools.registry import ToolDefinition, registry


class PlayYoutubeVideoParams(BaseModel):
    query: str = Field(..., description="The song, artist, or video to play on YouTube.", min_length=1, max_length=300)

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("A song, artist, or video query is required.")
        return cleaned


def _watch_url(href: str | None) -> str | None:
    if not href:
        return None
    candidate = urljoin("https://www.youtube.com", href)
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or parsed.hostname not in {"www.youtube.com", "youtube.com"}:
        return None
    if parsed.path != "/watch" or not parse_qs(parsed.query).get("v"):
        return None
    return candidate


def _is_verified_playback(first: dict[str, Any], second: dict[str, Any]) -> bool:
    """Require both a usable media element and actual time progression."""
    try:
        return bool(
            first.get("exists")
            and second.get("exists")
            and first.get("readyState", 0) >= 2
            and second.get("readyState", 0) >= 2
            and not second.get("paused", True)
            and float(second.get("currentTime", 0)) > float(first.get("currentTime", 0)) + 0.12
        )
    except (TypeError, ValueError):
        return False


async def _media_snapshot(page: Page) -> dict[str, Any]:
    result = await page.evaluate(
        """() => {
          const video = document.querySelector('video.html5-main-video, video');
          if (!video) return { exists: false };
          return {
            exists: true,
            paused: Boolean(video.paused),
            ended: Boolean(video.ended),
            readyState: Number(video.readyState || 0),
            currentTime: Number(video.currentTime || 0),
            duration: Number(video.duration || 0),
            muted: Boolean(video.muted),
            errorCode: video.error ? Number(video.error.code) : null,
          };
        }"""
    )
    return result if isinstance(result, dict) else {"exists": False}


async def _keep_single_owned_page(page: Page) -> int:
    """Close any popups that YouTube opened inside HINAA's dedicated context."""
    for candidate in list(page.context.pages):
        if candidate is page or candidate.is_closed():
            continue
        try:
            await candidate.close()
        except PlaywrightError:
            continue
    return sum(1 for candidate in page.context.pages if not candidate.is_closed())


async def _select_first_video(page: Page, query: str) -> tuple[str | None, str | None]:
    await page.goto(
        f"https://www.youtube.com/results?search_query={quote_plus(query)}",
        wait_until="domcontentloaded",
        timeout=20_000,
    )
    await page.bring_to_front()
    results = page.locator("a#video-title[href*='/watch']")
    try:
        await results.first.wait_for(state="attached", timeout=10_000)
    except PlaywrightTimeoutError:
        return None, None

    # Pick one first-party watch result only; no new pages or redirecting ads.
    for index in range(min(await results.count(), 8)):
        candidate = results.nth(index)
        href = _watch_url(await candidate.get_attribute("href"))
        if href:
            title = (await candidate.get_attribute("title")) or (await candidate.text_content()) or query
            return href, " ".join(title.split())[:240]
    return None, None


async def _request_media_playback(page: Page) -> None:
    """Use an explicit player click first, then a media play request as a fallback."""
    play_button = page.locator("button.ytp-large-play-button, button.ytp-play-button").first
    try:
        if await play_button.count():
            await play_button.click(timeout=4_000)
    except (PlaywrightError, PlaywrightTimeoutError):
        # The button can be absent while autoplay has already started. The media
        # verification below determines the truth instead of assuming this worked.
        pass

    try:
        await page.evaluate(
            """async () => {
              const video = document.querySelector('video.html5-main-video, video');
              if (!video) return { attempted: false, reason: 'media-element-missing' };
              try {
                await video.play();
                return { attempted: true, started: true };
              } catch (error) {
                return { attempted: true, started: false, reason: error?.name || 'play-rejected' };
              }
            }"""
        )
    except PlaywrightError:
        # Do not replace this with an optimistic result; the snapshots decide.
        return


async def play_youtube_video(params: PlayYoutubeVideoParams) -> dict[str, Any]:
    """Open and verify one YouTube video inside the existing owned browser page."""
    try:
        page = await _get_page()
        owned_before = await _keep_single_owned_page(page)
        watch_url, title = await _select_first_video(page, params.query)
        if not watch_url:
            return {
                "status": "blocked",
                "data": {
                    "verified": False,
                    "state": "no-result",
                    "query": params.query,
                    "message": "HINAA could not select a playable YouTube result. YouTube may be showing consent, sign-in, or an unavailable search page.",
                    "ownedPageCount": await _keep_single_owned_page(page),
                },
            }

        separator = "&" if "?" in watch_url else "?"
        await page.goto(f"{watch_url}{separator}autoplay=1", wait_until="domcontentloaded", timeout=20_000)
        await page.bring_to_front()
        await page.wait_for_timeout(600)
        await _request_media_playback(page)
        first = await _media_snapshot(page)
        await page.wait_for_timeout(1_100)
        second = await _media_snapshot(page)
        owned_after = await _keep_single_owned_page(page)

        evidence = {
            "query": params.query,
            "title": title or params.query,
            "url": page.url,
            "ownedPageCount": owned_after,
            "media": {
                "readyState": second.get("readyState", 0),
                "currentTimeStart": first.get("currentTime", 0),
                "currentTimeEnd": second.get("currentTime", 0),
                "paused": second.get("paused", True),
                "muted": second.get("muted", False),
            },
        }
        if _is_verified_playback(first, second) and owned_before == 1 and owned_after == 1:
            return {
                "status": "success",
                "data": {
                    "verified": True,
                    "state": "playing",
                    "message": f"Playing {title or params.query} in HINAA's owned YouTube tab.",
                    **evidence,
                },
            }

        return {
            "status": "blocked",
            "data": {
                "verified": False,
                "state": "needs-user-play",
                "message": "YouTube opened in HINAA's owned tab, but playback was not verified. Press Play in that tab; your browser, YouTube consent/sign-in, or autoplay policy may require a direct interaction.",
                **evidence,
            },
        }
    except (PlaywrightTimeoutError, PlaywrightError):
        return {
            "status": "blocked",
            "data": {
                "verified": False,
                "state": "browser-unavailable",
                "query": params.query,
                "message": "HINAA could not reach a usable YouTube player in the owned browser. No playback was claimed.",
            },
        }


youtube_playback_request_def = ToolDefinition(
    name="youtube_playback_request",
    display_name="Play YouTube music",
    description="Open one YouTube result in HINAA's owned browser tab and report success only after verified active playback. HINAA reports when YouTube needs you to press Play.",
    parameters={
        "query": {
            "type": "string",
            "description": "The song, artist, or video to play on YouTube.",
        }
    },
    required_parameters=["query"],
    voice_aliases=["play", "listen to", "put on"],
    requires_confirmation=True,
    cancellable=True,
)

registry.register(youtube_playback_request_def, play_youtube_video)
