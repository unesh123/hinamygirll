"""Social connections and publishing. Publishing is irreversible: it needs explicit confirmation,
defaults to private, only reads media from an allowed folder, and every attempt is logged."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..errors import HinaaError
from ..persistence.db import get_session_factory
from ..persistence.orm import ContentPost, SocialPublishLog, SocialToken
from ..runtime_paths import runtime_dir
from . import youtube
from .crypto import decrypt_json, encrypt_json, signing_key

logger = logging.getLogger("hinaa.social")

STATE_TTL_SECONDS = 600
VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv", ".mpeg", ".mpg"})

# Platforms we cannot publish to yet. Statuses are honest: nothing here uploads anything.
UNSUPPORTED: dict[str, dict[str, Any]] = {
    "instagram": {
        "name": "Instagram",
        "requirements": "Instagram Graph API needs a Business or Creator account linked to a Facebook Page and a Meta app "
        "approved (App Review) for instagram_content_publish.",
    },
    "facebook": {
        "name": "Facebook Pages",
        "requirements": "Needs a Facebook Page, a Meta app, and App Review for pages_manage_posts / pages_read_engagement.",
    },
    "tiktok": {
        "name": "TikTok",
        "requirements": "TikTok Content Posting API needs a registered developer app audited by TikTok; unaudited apps "
        "can only post private drafts.",
    },
    "x": {
        "name": "X (Twitter)",
        "requirements": "Needs an X developer project with write access (paid API tier) and OAuth 2.0 user-context tokens.",
    },
}


def _session(settings: Settings | None) -> Callable[[], Session]:
    return get_session_factory(settings or get_settings())


def youtube_configured(settings: Settings) -> bool:
    return bool(
        settings.google_oauth_client_id
        and settings.google_oauth_redirect_uri
        and settings.google_oauth_client_secret
        and settings.google_oauth_client_secret.get_secret_value().strip()
    )


def _need_config(settings: Settings) -> tuple[str, str, str]:
    if not youtube_configured(settings):
        raise HinaaError(
            "YOUTUBE_NOT_CONFIGURED",
            "YouTube needs GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET and GOOGLE_OAUTH_REDIRECT_URI "
            "(an OAuth web client with the YouTube Data API v3 enabled).",
            409,
            False,
            True,
        )
    return (
        str(settings.google_oauth_client_id),
        settings.google_oauth_client_secret.get_secret_value(),  # type: ignore[union-attr]
        str(settings.google_oauth_redirect_uri),
    )


# ---- OAuth state ------------------------------------------------------------


def make_state(settings: Settings | None, user_id: str, now: float | None = None) -> str:
    body = f"{user_id}|{secrets.token_hex(8)}|{int((now or time.time()) + STATE_TTL_SECONDS)}"
    sig = hmac.new(signing_key(settings), body.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{body}|{sig}".encode()).decode()


def verify_state(settings: Settings | None, state: str, now: float | None = None) -> str:
    try:
        body, sig = base64.urlsafe_b64decode(state.encode()).decode().rsplit("|", 1)
        user_id, _nonce, expires = body.split("|")
        valid = hmac.compare_digest(
            sig, hmac.new(signing_key(settings), body.encode(), hashlib.sha256).hexdigest()
        )
        if valid and int(expires) >= (now or time.time()):
            return user_id
    except (ValueError, UnicodeDecodeError):
        pass
    raise HinaaError(
        "OAUTH_STATE_INVALID",
        "The YouTube sign-in link expired or was tampered with. Start again.",
        400,
        False,
        True,
    )


def start_youtube_connect(settings: Settings | None, user_id: str) -> dict[str, str]:
    active = settings or get_settings()
    client_id, _secret, redirect = _need_config(active)
    return {"authUrl": youtube.authorization_url(client_id, redirect, make_state(active, user_id))}


# ---- token storage ----------------------------------------------------------


def _store_token(
    settings: Settings | None, user_id: str, provider: str, payload: dict[str, Any], label: str = ""
) -> None:
    expires = datetime.now(UTC) + timedelta(seconds=int(payload.get("expires_in", 3600)))
    secret = {k: payload[k] for k in ("access_token", "refresh_token") if payload.get(k)}
    with _session(settings)() as session:
        row = session.scalar(
            select(SocialToken).where(
                SocialToken.user_id == user_id, SocialToken.provider == provider
            )
        )
        if row is None:
            row = SocialToken(user_id=user_id, provider=provider, ciphertext="")
            session.add(row)
        else:  # Google omits refresh_token on re-consent refreshes; keep the one we hold.
            secret.setdefault(
                "refresh_token", decrypt_json(settings, row.ciphertext).get("refresh_token", "")
            )
        row.ciphertext = encrypt_json(settings, secret)
        row.scopes = str(payload.get("scope", ""))
        row.expires_at = expires
        if label:
            row.account_label = label
        session.commit()


def _load_token(
    settings: Settings | None, user_id: str, provider: str
) -> tuple[dict[str, Any], SocialToken] | None:
    with _session(settings)() as session:
        row = session.scalar(
            select(SocialToken).where(
                SocialToken.user_id == user_id, SocialToken.provider == provider
            )
        )
        if row is None:
            return None
        session.expunge(row)
        return decrypt_json(settings, row.ciphertext), row


def disconnect(settings: Settings | None, user_id: str, provider: str = "youtube") -> bool:
    with _session(settings)() as session:
        row = session.scalar(
            select(SocialToken).where(
                SocialToken.user_id == user_id, SocialToken.provider == provider
            )
        )
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True


async def complete_youtube_connect(
    settings: Settings | None, state: str, code: str, http: httpx.AsyncClient | None = None
) -> str:
    active = settings or get_settings()
    user_id = verify_state(active, state)
    client_id, secret, redirect = _need_config(active)
    async with _client(http) as client:
        payload = await youtube.exchange_code(client, client_id, secret, redirect, code)
        label = ""
        try:
            label = (await youtube.YouTubeClient(payload["access_token"], client).channel())[
                "snippet"
            ]["title"]
        except Exception:  # connecting still works without the label
            logger.info("YouTube channel lookup after connect failed", exc_info=True)
    _store_token(active, user_id, "youtube", payload, label)
    return user_id


class _client:  # noqa: N801 - tiny context manager: use the injected client without closing it
    def __init__(self, http: httpx.AsyncClient | None) -> None:
        self._http, self._own = http or httpx.AsyncClient(timeout=30.0), http is None

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._http

    async def __aexit__(self, *_exc: object) -> None:
        if self._own:
            await self._http.aclose()


async def _access_token(settings: Settings, user_id: str, http: httpx.AsyncClient) -> str:
    loaded = _load_token(settings, user_id, "youtube")
    if loaded is None:
        raise HinaaError(
            "YOUTUBE_NOT_CONNECTED",
            "Connect YouTube first (Connect YouTube on the News page).",
            409,
            False,
            True,
        )
    secret, row = loaded
    expires = (
        row.expires_at.replace(tzinfo=UTC)
        if row.expires_at and row.expires_at.tzinfo is None
        else row.expires_at
    )
    if (
        secret.get("access_token")
        and expires
        and expires - datetime.now(UTC) > timedelta(seconds=60)
    ):
        return secret["access_token"]
    if not secret.get("refresh_token"):
        raise HinaaError(
            "YOUTUBE_NOT_CONNECTED",
            "The YouTube login expired. Reconnect YouTube.",
            409,
            False,
            True,
        )
    client_id, client_secret, _ = _need_config(settings)
    fresh = await youtube.refresh_access_token(
        http, client_id, client_secret, secret["refresh_token"]
    )
    _store_token(settings, user_id, "youtube", fresh)
    return fresh["access_token"]


# ---- status -----------------------------------------------------------------


def connections(settings: Settings | None, user_id: str) -> list[dict[str, Any]]:
    active = settings or get_settings()
    loaded = _load_token(active, user_id, "youtube")
    items: list[dict[str, Any]] = [
        {
            "id": "youtube",
            "name": "YouTube",
            "status": "connected"
            if loaded
            else ("ready" if youtube_configured(active) else "requires_setup"),
            "connected": loaded is not None,
            "account": loaded[1].account_label if loaded else "",
            "requirements": "Set GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET and GOOGLE_OAUTH_REDIRECT_URI, "
            "then press Connect YouTube. Videos upload as private unless you say otherwise."
            if not youtube_configured(active)
            else "",
        }
    ]
    for pid, info in UNSUPPORTED.items():
        items.append(
            {
                "id": pid,
                "name": info["name"],
                "status": "requires_setup",
                "connected": False,
                "account": "",
                "requirements": info["requirements"],
            }
        )
    return items


# ---- publishing -------------------------------------------------------------


def media_roots(settings: Settings) -> list[Path]:
    root = (
        Path(settings.social_media_root).expanduser()
        if settings.social_media_root
        else runtime_dir("social", "media")
    )
    return [root.resolve()]


def resolve_media(settings: Settings, media_path: str) -> Path:
    """Only video files inside the media folder may be uploaded, so a prompt cannot exfiltrate other files."""
    path = Path(media_path).expanduser()
    roots = media_roots(settings)
    if not path.is_absolute():
        path = roots[0] / path
    path = path.resolve()
    if not any(path.is_relative_to(r) for r in roots):
        raise HinaaError(
            "SOCIAL_MEDIA_OUTSIDE_ROOT", f"Media must live inside {roots[0]}.", 422, False, True
        )
    if path.suffix.lower() not in VIDEO_SUFFIXES or not path.is_file() or path.stat().st_size == 0:
        raise HinaaError(
            "SOCIAL_MEDIA_INVALID",
            "Media must be an existing, non-empty video file.",
            422,
            False,
            True,
        )
    return path


def _log(settings: Settings | None, user_id: str, **fields: Any) -> None:
    with _session(settings)() as session:
        session.add(SocialPublishLog(user_id=user_id, **fields))
        session.commit()
    logger.info(
        "social_publish user=%s %s", user_id, {k: v for k, v in fields.items() if k != "error"}
    )


async def publish(
    settings: Settings | None,
    user_id: str,
    *,
    confirm: bool,
    platform: str = "youtube",
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    privacy: str | None = None,
    publish_at: str | datetime | None = None,
    media_path: str | None = None,
    post_id: str | None = None,
    http: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    active = settings or get_settings()
    if confirm is not True:
        raise HinaaError(
            "SOCIAL_CONFIRMATION_REQUIRED",
            "Publishing to a social platform cannot be undone. Ask the user to confirm explicitly, then retry with confirm=true.",
            409,
            False,
            True,
        )
    platform = (platform or "youtube").lower()
    if platform != "youtube":
        info = UNSUPPORTED.get(platform)
        raise HinaaError(
            "SOCIAL_REQUIRES_SETUP",
            f"{info['name'] if info else platform} publishing is not available yet. {info['requirements'] if info else ''}".strip(),
            501,
            False,
            True,
        )

    post: dict[str, Any] = {}
    if post_id:
        with _session(active)() as session:
            row = session.scalar(
                select(ContentPost).where(ContentPost.id == post_id, ContentPost.user_id == user_id)
            )
            if row is None:
                raise HinaaError(
                    "POST_NOT_FOUND", "There is no such content post for this account.", 404, False
                )
            post = {
                "title": row.title,
                "description": row.caption,
                "tags": [t for t in row.tags.split(",") if t],
                "media": row.media_path,
                "privacy": row.publish_privacy,
                "platform": row.platform,
            }
        if post["platform"] not in ("youtube", "other"):
            raise HinaaError(
                "SOCIAL_PLATFORM_MISMATCH",
                f"That post targets {post['platform']}, not YouTube.",
                422,
                False,
                True,
            )

    final_title = (title or post.get("title") or "").strip()
    media = media_path or post.get("media")
    if not final_title:
        raise HinaaError("SOCIAL_TITLE_REQUIRED", "A video title is required.", 422, False, True)
    if not media:
        raise HinaaError(
            "SOCIAL_MEDIA_REQUIRED",
            "A video file path (inside the media folder) is required.",
            422,
            False,
            True,
        )

    chosen_privacy = youtube.resolve_privacy(privacy or post.get("privacy"))
    when = youtube.normalize_publish_at(publish_at)
    body = youtube.build_video_body(
        final_title,
        description if description is not None else post.get("description", ""),
        tags if tags is not None else post.get("tags", []),
        chosen_privacy,
        when,
    )
    path = resolve_media(active, media)
    log_fields = {
        "platform": "youtube",
        "post_id": post_id,
        "title": final_title,
        "privacy": chosen_privacy,
        "publish_at": when,
    }

    async with _client(http) as client:
        try:
            token = await _access_token(active, user_id, client)
            video = await youtube.YouTubeClient(token, client).upload_video(path, body)
        except Exception as error:
            _log(
                active,
                user_id,
                status="failed",
                error=str(getattr(error, "message", error))[:500],
                **log_fields,
            )
            raise
    video_id = str(video.get("id", ""))
    url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
    _log(active, user_id, status="published", external_id=video_id, **log_fields)

    if post_id:
        with _session(active)() as session:
            row = session.scalar(
                select(ContentPost).where(ContentPost.id == post_id, ContentPost.user_id == user_id)
            )
            if row is not None:
                row.external_id, row.external_url = video_id, url
                row.status = "scheduled" if when else "published"
                session.commit()
    return {
        "platform": "youtube",
        "videoId": video_id,
        "url": url,
        "privacyStatus": chosen_privacy,
        "publishAt": when,
        "status": "scheduled" if when else "uploaded",
    }


async def list_uploads(
    settings: Settings | None, user_id: str, limit: int = 10, http: httpx.AsyncClient | None = None
) -> list[dict[str, Any]]:
    active = settings or get_settings()
    async with _client(http) as client:
        token = await _access_token(active, user_id, client)
        return await youtube.YouTubeClient(token, client).list_uploads(limit)


def publish_log(settings: Settings | None, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with _session(settings)() as session:
        rows = session.scalars(
            select(SocialPublishLog)
            .where(SocialPublishLog.user_id == user_id)
            .order_by(SocialPublishLog.created_at.desc())
            .limit(limit)
        ).all()
        return [
            {
                "id": r.id,
                "platform": r.platform,
                "title": r.title,
                "privacy": r.privacy,
                "status": r.status,
                "externalId": r.external_id,
                "error": r.error,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

# ruff: noqa: E501
