"""YouTube Data API v3 client: OAuth 2.0 web flow helpers, resumable upload, channel uploads.

Request shapes follow Google's docs:
  https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol
  https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps
  https://developers.google.com/youtube/v3/docs/videos/insert
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from ..errors import HinaaError

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
API_BASE = "https://www.googleapis.com/youtube/v3"
SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
)
PRIVACY_VALUES = ("private", "unlisted", "public")
CHUNK = 1024 * 1024
MAX_RESUMES = 3


def resolve_privacy(requested: str | None) -> str:
    """Publishing is irreversible, so anything not explicitly asked for stays private."""
    value = (requested or "").strip().lower()
    if not value:
        return "private"
    if value not in PRIVACY_VALUES:
        raise HinaaError(
            "SOCIAL_BAD_PRIVACY",
            f"privacyStatus must be one of {', '.join(PRIVACY_VALUES)}.",
            422,
            False,
            True,
        )
    return value


def normalize_publish_at(value: str | datetime | None, now: datetime | None = None) -> str | None:
    """ISO 8601 UTC string for status.publishAt; must be in the future."""
    if value is None or value == "":
        return None
    try:
        moment = (
            value
            if isinstance(value, datetime)
            else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        )
    except ValueError as error:
        raise HinaaError(
            "SOCIAL_BAD_PUBLISH_AT", "publishAt must be an ISO 8601 date-time.", 422, False, True
        ) from error
    if moment.tzinfo is None:
        raise HinaaError(
            "SOCIAL_BAD_PUBLISH_AT",
            "publishAt needs a timezone offset (for example +05:45).",
            422,
            False,
            True,
        )
    moment = moment.astimezone(UTC)
    if moment <= (now or datetime.now(UTC)):
        raise HinaaError(
            "SOCIAL_BAD_PUBLISH_AT", "publishAt must be in the future.", 422, False, True
        )
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def build_video_body(
    title: str,
    description: str,
    tags: list[str],
    privacy: str,
    publish_at: str | None,
    category_id: str = "22",
) -> dict[str, Any]:
    if publish_at and privacy != "private":
        raise HinaaError(
            "SOCIAL_PUBLISH_AT_REQUIRES_PRIVATE",
            "A scheduled publish time requires privacyStatus=private; YouTube makes it public at that time.",
            422,
            False,
            True,
        )
    status: dict[str, Any] = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    if publish_at:
        status["publishAt"] = publish_at
    return {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:30],
            "categoryId": category_id,
        },
        "status": status,
    }


def authorization_url(client_id: str, redirect_uri: str, state: str) -> str:
    query = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(query)}"


async def exchange_code(
    http: httpx.AsyncClient, client_id: str, client_secret: str, redirect_uri: str, code: str
) -> dict[str, Any]:
    response = await http.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
    )
    return _token_payload(response)


async def refresh_access_token(
    http: httpx.AsyncClient, client_id: str, client_secret: str, refresh_token: str
) -> dict[str, Any]:
    response = await http.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    return _token_payload(response)


def _token_payload(response: httpx.Response) -> dict[str, Any]:
    if response.status_code >= 400:
        raise HinaaError(
            "YOUTUBE_OAUTH_FAILED",
            "Google rejected the OAuth request. Reconnect YouTube.",
            502,
            True,
            True,
            developer_message=response.text[:300],
        )
    return response.json()


async def _file_chunks(path: Path) -> AsyncIterator[bytes]:
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            yield chunk


class YouTubeClient:
    def __init__(self, access_token: str, http: httpx.AsyncClient) -> None:
        self._auth = {"Authorization": f"Bearer {access_token}"}
        self._http = http

    async def upload_video(self, path: Path, body: dict[str, Any]) -> dict[str, Any]:
        """Resumable upload: POST to open a session, then PUT the bytes (resuming after a break)."""
        size = (await asyncio.to_thread(path.stat)).st_size
        mime = mimetypes.guess_type(path.name)[0] or "video/*"
        init = await self._http.post(
            UPLOAD_URL,
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                **self._auth,
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Length": str(size),
                "X-Upload-Content-Type": mime,
            },
            content=json.dumps(body).encode(),
        )
        if init.status_code != 200 or not init.headers.get("Location"):
            raise _api_error("YouTube refused to start the upload", init)
        session_url = init.headers["Location"]

        offset = 0
        for attempt in range(MAX_RESUMES + 1):
            try:
                response = await self._http.put(
                    session_url,
                    headers={
                        **self._auth,
                        "Content-Type": mime,
                        **self._range_headers(offset, size),
                    },
                    content=_file_chunks(path) if offset == 0 else _file_chunks_from(path, offset),
                    timeout=None,
                )
            except httpx.TransportError:
                response = None
            if response is not None and response.status_code in (200, 201):
                return response.json()
            if response is not None and response.status_code < 500 and response.status_code != 308:
                raise _api_error("YouTube rejected the video upload", response)
            if attempt == MAX_RESUMES:
                raise HinaaError(
                    "YOUTUBE_UPLOAD_INTERRUPTED",
                    "The upload kept failing; try again later.",
                    502,
                    True,
                )
            offset = await self._received_bytes(session_url, size)
        raise HinaaError("YOUTUBE_UPLOAD_INTERRUPTED", "The upload did not complete.", 502, True)

    @staticmethod
    def _range_headers(offset: int, size: int) -> dict[str, str]:
        if offset == 0:
            return {"Content-Length": str(size)}
        return {
            "Content-Length": str(size - offset),
            "Content-Range": f"bytes {offset}-{size - 1}/{size}",
        }

    async def _received_bytes(self, session_url: str, size: int) -> int:
        probe = await self._http.put(
            session_url,
            headers={**self._auth, "Content-Length": "0", "Content-Range": f"bytes */{size}"},
        )
        if probe.status_code in (200, 201):
            return size
        received = probe.headers.get("Range", "")
        return int(received.rsplit("-", 1)[-1]) + 1 if received.startswith("bytes=") else 0

    async def channel(self) -> dict[str, Any]:
        response = await self._http.get(
            f"{API_BASE}/channels",
            params={"part": "snippet,contentDetails", "mine": "true"},
            headers=self._auth,
        )
        if response.status_code != 200:
            raise _api_error("Could not read the YouTube channel", response)
        items = response.json().get("items") or []
        if not items:
            raise HinaaError(
                "YOUTUBE_NO_CHANNEL",
                "This Google account has no YouTube channel.",
                409,
                False,
                True,
            )
        return items[0]

    async def list_uploads(self, max_results: int = 10) -> list[dict[str, Any]]:
        channel = await self.channel()
        playlist = channel["contentDetails"]["relatedPlaylists"]["uploads"]
        response = await self._http.get(
            f"{API_BASE}/playlistItems",
            params={
                "part": "snippet,status",
                "playlistId": playlist,
                "maxResults": max(1, min(max_results, 50)),
            },
            headers=self._auth,
        )
        if response.status_code != 200:
            raise _api_error("Could not list uploads", response)
        out = []
        for item in response.json().get("items", []):
            snippet = item.get("snippet", {})
            video_id = (snippet.get("resourceId") or {}).get("videoId", "")
            out.append(
                {
                    "videoId": video_id,
                    "title": snippet.get("title", ""),
                    "publishedAt": snippet.get("publishedAt"),
                    "privacyStatus": (item.get("status") or {}).get("privacyStatus"),
                    "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
                }
            )
        return out


async def _file_chunks_from(path: Path, offset: int) -> AsyncIterator[bytes]:
    with path.open("rb") as handle:
        handle.seek(offset)
        while chunk := handle.read(CHUNK):
            yield chunk


def _api_error(message: str, response: httpx.Response) -> HinaaError:
    status = 401 if response.status_code in (401, 403) else 502
    return HinaaError(
        "YOUTUBE_API_ERROR",
        f"{message} (HTTP {response.status_code}).",
        status,
        response.status_code >= 500,
        status == 401,
        developer_message=response.text[:500],
    )

# ruff: noqa: E501
