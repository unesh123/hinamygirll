"""Social publishing: YouTube OAuth + resumable upload shapes, privacy default, confirmation gating."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.integrations_hub import connectors, mcp_agent_tools
from hinaa_api.main import create_app
from hinaa_api.persistence.db import get_session_factory, reset_session_factory
from hinaa_api.persistence.orm import ContentPost, SocialPublishLog, SocialToken
from hinaa_api.productivity import service as productivity
from hinaa_api.productivity.schemas import ContentPostCreate
from hinaa_api.social import service, youtube
from hinaa_api.social.crypto import decrypt_json, encrypt_json
from hinaa_api.tools import policy
from hinaa_api.tools import social as social_tool
from hinaa_api.tools.registry import registry

ALICE = {"X-HINAA-Dev-User": "alice"}
BOB = {"X-HINAA-Dev-User": "bob"}
VIDEO = b"\x00\x00\x00\x18ftypmp42" + b"v" * 4096


def _settings(tmp_path, **extra) -> Settings:
    return Settings(
        _env_file=None,
        HINAA_PROVIDER_MODE="mock",
        HINAA_DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'social.db').as_posix()}",
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
        HINAA_NEWS_SCHEDULER_ENABLED=False,
        HINAA_VMC_PORT=0,
        AZURE_SPEECH_KEY="",
        AZURE_SPEECH_REGION="",
        ELEVENLABS_API_KEY="",
        HINAA_SOCIAL_TOKEN_KEY="unit-test-key",
        HINAA_SOCIAL_MEDIA_ROOT=str(tmp_path / "media"),
        GOOGLE_OAUTH_CLIENT_ID="cid.apps.googleusercontent.com",
        GOOGLE_OAUTH_CLIENT_SECRET="csecret",
        GOOGLE_OAUTH_REDIRECT_URI="https://hinaa.example/v1/social/youtube/callback",
        **extra,
    )


@pytest.fixture
def cfg(tmp_path):
    reset_session_factory()
    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "clip.mp4").write_bytes(VIDEO)
    settings = _settings(tmp_path)
    get_session_factory(settings)
    yield settings
    reset_session_factory()


def _connect(cfg, user="alice", expires_in=3600):
    service._store_token(
        cfg,
        user,
        "youtube",
        {
            "access_token": "ya29.ACCESS",
            "refresh_token": "1//REFRESH",
            "expires_in": expires_in,
            "scope": "x",
        },
        "My Channel",
    )


class FakeGoogle:
    """Records every request and answers like YouTube's resumable protocol."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.bodies: dict[int, bytes] = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        if request.url.path == "/upload/youtube/v3/videos" and request.method == "POST":
            return httpx.Response(
                200,
                headers={
                    "Location": "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&upload_id=SESSION"
                },
            )
        if request.method == "PUT" and "upload_id=SESSION" in url:
            return httpx.Response(
                201, json={"id": "vid123", "status": {"privacyStatus": "private"}}
            )
        if url.startswith("https://oauth2.googleapis.com/token"):
            return httpx.Response(200, json={"access_token": "ya29.FRESH", "expires_in": 3600})
        if request.url.path.endswith("/channels"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "snippet": {"title": "My Channel"},
                            "contentDetails": {"relatedPlaylists": {"uploads": "UUx"}},
                        }
                    ]
                },
            )
        if request.url.path.endswith("/playlistItems"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "snippet": {
                                "title": "First",
                                "publishedAt": "2026-01-01T00:00:00Z",
                                "resourceId": {"videoId": "abc"},
                            },
                            "status": {"privacyStatus": "private"},
                        }
                    ]
                },
            )
        return httpx.Response(404)

    def client(self):
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


def run(coro):
    return asyncio.run(coro)


# ---- request shapes ----------------------------------------------------------


def test_resumable_upload_request_shape(cfg):
    _connect(cfg)
    google = FakeGoogle()

    async def go():
        async with google.client() as http:
            return await service.publish(
                cfg,
                "alice",
                confirm=True,
                title="Studio tour",
                description="Behind the scenes",
                tags=["vlog", "nepal"],
                media_path="clip.mp4",
                http=http,
            )

    result = run(go())
    init, put = google.requests
    assert init.method == "POST" and init.url.path == "/upload/youtube/v3/videos"
    query = parse_qs(init.url.query.decode())
    assert query == {"uploadType": ["resumable"], "part": ["snippet,status"]}
    assert init.headers["authorization"] == "Bearer ya29.ACCESS"
    assert init.headers["content-type"] == "application/json; charset=UTF-8"
    assert init.headers["x-upload-content-length"] == str(len(VIDEO))
    assert init.headers["x-upload-content-type"] == "video/mp4"
    body = json.loads(init.content)
    assert body["snippet"] == {
        "title": "Studio tour",
        "description": "Behind the scenes",
        "tags": ["vlog", "nepal"],
        "categoryId": "22",
    }
    assert body["status"]["privacyStatus"] == "private" and "publishAt" not in body["status"]

    assert put.method == "PUT" and "upload_id=SESSION" in str(put.url)
    assert put.headers["authorization"] == "Bearer ya29.ACCESS"
    assert (
        put.headers["content-length"] == str(len(VIDEO))
        and put.headers["content-type"] == "video/mp4"
    )
    assert put.content == VIDEO
    assert result == {
        "platform": "youtube",
        "videoId": "vid123",
        "url": "https://www.youtube.com/watch?v=vid123",
        "privacyStatus": "private",
        "publishAt": None,
        "status": "uploaded",
    }


def test_scheduled_publish_sets_publish_at_and_stays_private(cfg):
    _connect(cfg)
    google = FakeGoogle()
    when = (datetime.now(UTC) + timedelta(days=2)).astimezone(UTC).replace(microsecond=0)

    async def go():
        async with google.client() as http:
            return await service.publish(
                cfg,
                "alice",
                confirm=True,
                title="Later",
                media_path="clip.mp4",
                publish_at=when.isoformat(),
                http=http,
            )

    result = run(go())
    status = json.loads(google.requests[0].content)["status"]
    assert status["privacyStatus"] == "private"
    assert status["publishAt"] == when.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    assert result["status"] == "scheduled"


def test_publish_at_requires_private_and_future():
    with pytest.raises(HinaaError) as e:
        youtube.build_video_body("t", "", [], "public", "2030-01-01T00:00:00.000Z")
    assert e.value.code == "SOCIAL_PUBLISH_AT_REQUIRES_PRIVATE"
    with pytest.raises(HinaaError):
        youtube.normalize_publish_at("2001-01-01T00:00:00+00:00")
    with pytest.raises(HinaaError):
        youtube.normalize_publish_at("2099-01-01T00:00:00")  # no timezone
    assert youtube.normalize_publish_at("2099-01-01T05:45:00+05:45") == "2099-01-01T00:00:00.000Z"


def test_interrupted_upload_resumes_from_received_range(cfg):
    _connect(cfg)
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        if request.method == "POST":
            return httpx.Response(
                200,
                headers={
                    "Location": "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=S"
                },
            )
        puts = [r for r in seen if r.method == "PUT"]
        if len(puts) == 1:
            return httpx.Response(503)
        if request.headers.get("content-range") == f"bytes */{len(VIDEO)}":
            return httpx.Response(308, headers={"Range": "bytes=0-1023"})
        return httpx.Response(201, json={"id": "resumed"})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await service.publish(
                cfg, "alice", confirm=True, title="T", media_path="clip.mp4", http=http
            )

    assert run(go())["videoId"] == "resumed"
    last = seen[-1]
    assert last.headers["content-range"] == f"bytes 1024-{len(VIDEO) - 1}/{len(VIDEO)}"
    assert last.content == VIDEO[1024:]


# ---- privacy default ---------------------------------------------------------


def test_privacy_defaults_to_private_and_honours_explicit_choice():
    assert youtube.resolve_privacy(None) == "private"
    assert youtube.resolve_privacy("  ") == "private"
    assert youtube.resolve_privacy("Unlisted") == "unlisted"
    assert youtube.resolve_privacy("public") == "public"
    with pytest.raises(HinaaError):
        youtube.resolve_privacy("friends")


def test_explicit_public_is_sent_as_public(cfg):
    _connect(cfg)
    google = FakeGoogle()

    async def go():
        async with google.client() as http:
            await service.publish(
                cfg,
                "alice",
                confirm=True,
                title="T",
                media_path="clip.mp4",
                privacy="public",
                http=http,
            )

    run(go())
    assert json.loads(google.requests[0].content)["status"]["privacyStatus"] == "public"


# ---- confirmation gating -----------------------------------------------------


def test_publish_without_confirmation_never_touches_the_network(cfg):
    _connect(cfg)
    google = FakeGoogle()

    async def go(**kw):
        async with google.client() as http:
            return await service.publish(
                cfg, "alice", title="T", media_path="clip.mp4", http=http, **kw
            )

    for kw in ({"confirm": False}, {"confirm": None}):
        with pytest.raises(HinaaError) as e:
            run(go(**kw))
        assert e.value.code == "SOCIAL_CONFIRMATION_REQUIRED"
    assert google.requests == []


def test_tool_is_confirmation_gated_in_registry_policy_and_handler(cfg, monkeypatch):
    tool = registry.get_tool("social_publish")
    assert tool is not None and tool.requires_confirmation is True
    assert "social_publish" in policy.IRREVERSIBLE_EXTERNAL_TOOLS
    assert (
        policy.decide(
            "social_publish", Settings(_env_file=None), "evil.trycloudflare.com"
        ).permitted
        is False
    )

    calls = []

    async def fake_publish(settings, user_id, **kw):
        calls.append(kw)
        return {
            "platform": "youtube",
            "videoId": "v",
            "url": "https://www.youtube.com/watch?v=v",
            "privacyStatus": "private",
            "publishAt": None,
            "status": "uploaded",
        }

    monkeypatch.setattr(service, "publish", fake_publish)
    asyncio.run(social_tool.social_publish({"userId": "alice", "title": "T"}))
    assert calls[-1]["confirm"] is False  # no verified user approval in context
    token = mcp_agent_tools.set_user_approved(True)
    try:
        out = asyncio.run(
            social_tool.social_publish({"userId": "alice", "title": "T", "tags": "a, b"})
        )
    finally:
        mcp_agent_tools.reset_user_approved(token)
    assert (
        calls[-1]["confirm"] is True
        and calls[-1]["tags"] == ["a", "b"]
        and out["status"] == "success"
    )


def test_tool_handler_without_approval_fails_for_real(cfg, monkeypatch):
    monkeypatch.setattr(service, "get_settings", lambda: cfg)
    out = asyncio.run(
        social_tool.social_publish({"userId": "alice", "title": "T", "media_path": "clip.mp4"})
    )
    assert out["status"] == "failed" and out["code"] == "SOCIAL_CONFIRMATION_REQUIRED"


# ---- safety: media, platforms, isolation ------------------------------------


def test_media_must_be_a_video_inside_the_media_root(cfg, tmp_path):
    (tmp_path / "secret.mp4").write_bytes(VIDEO)
    (tmp_path / "media" / "notes.txt").write_text("not video")
    for bad in (
        "../secret.mp4",
        str(tmp_path / "secret.mp4"),
        "/etc/passwd",
        "notes.txt",
        "missing.mp4",
    ):
        with pytest.raises(HinaaError):
            service.resolve_media(cfg, bad)
    assert service.resolve_media(cfg, "clip.mp4").name == "clip.mp4"


def test_unsupported_platforms_are_honest(cfg):
    for platform in ("instagram", "tiktok", "facebook", "x"):
        with pytest.raises(HinaaError) as e:
            run(
                service.publish(
                    cfg, "alice", confirm=True, platform=platform, title="T", media_path="clip.mp4"
                )
            )
        assert e.value.code == "SOCIAL_REQUIRES_SETUP" and e.value.status_code == 501
    statuses = {c["id"]: c["status"] for c in service.connections(cfg, "alice")}
    assert (
        statuses["instagram"]
        == statuses["tiktok"]
        == statuses["facebook"]
        == statuses["x"]
        == "requires_setup"
    )
    assert statuses["youtube"] == "ready"
    ids = {c["id"] for c in connectors.list_connectors("social")}
    assert {"youtube", "instagram", "tiktok", "facebook", "x"} <= ids


def test_tokens_are_per_user_and_encrypted_at_rest(cfg):
    _connect(cfg, "alice")
    with get_session_factory(cfg)() as session:
        row = session.scalar(select(SocialToken))
        assert "ya29.ACCESS" not in row.ciphertext and "1//REFRESH" not in row.ciphertext
    assert decrypt_json(cfg, row.ciphertext)["refresh_token"] == "1//REFRESH"
    assert encrypt_json(cfg, {"a": 1}) != encrypt_json(cfg, {"a": 1})  # random IV
    assert service.connections(cfg, "bob")[0]["connected"] is False
    google = FakeGoogle()

    async def go():
        async with google.client() as http:
            return await service.publish(
                cfg, "bob", confirm=True, title="T", media_path="clip.mp4", http=http
            )

    with pytest.raises(HinaaError) as e:
        run(go())
    assert e.value.code == "YOUTUBE_NOT_CONNECTED" and google.requests == []


def test_expired_access_token_is_refreshed_and_stored(cfg):
    _connect(cfg, expires_in=1)
    google = FakeGoogle()

    async def go():
        async with google.client() as http:
            await service.publish(
                cfg, "alice", confirm=True, title="T", media_path="clip.mp4", http=http
            )

    run(go())
    refresh = google.requests[0]
    assert str(refresh.url) == "https://oauth2.googleapis.com/token"
    assert parse_qs(refresh.content.decode()) == {
        "client_id": ["cid.apps.googleusercontent.com"],
        "client_secret": ["csecret"],
        "refresh_token": ["1//REFRESH"],
        "grant_type": ["refresh_token"],
    }
    assert google.requests[1].headers["authorization"] == "Bearer ya29.FRESH"
    with get_session_factory(cfg)() as session:
        stored = decrypt_json(cfg, session.scalar(select(SocialToken)).ciphertext)
    assert stored == {"access_token": "ya29.FRESH", "refresh_token": "1//REFRESH"}


def test_every_attempt_is_logged_including_failures(cfg):
    _connect(cfg)

    def handler(request):
        return httpx.Response(403, json={"error": "quotaExceeded"})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            await service.publish(
                cfg, "alice", confirm=True, title="T", media_path="clip.mp4", http=http
            )

    with pytest.raises(HinaaError):
        run(go())
    google = FakeGoogle()

    async def ok():
        async with google.client() as http:
            await service.publish(
                cfg, "alice", confirm=True, title="Second", media_path="clip.mp4", http=http
            )

    run(ok())
    with get_session_factory(cfg)() as session:
        rows = session.scalars(select(SocialPublishLog).order_by(SocialPublishLog.created_at)).all()
    assert [(r.status, r.privacy) for r in rows] == [
        ("failed", "private"),
        ("published", "private"),
    ]
    assert rows[1].external_id == "vid123"
    assert service.publish_log(cfg, "bob") == []


# ---- OAuth -------------------------------------------------------------------


def test_authorization_url_and_state(cfg):
    out = service.start_youtube_connect(cfg, "alice")
    parts = urlsplit(out["authUrl"])
    q = {k: v[0] for k, v in parse_qs(parts.query).items()}
    assert (
        f"{parts.scheme}://{parts.netloc}{parts.path}"
        == "https://accounts.google.com/o/oauth2/v2/auth"
    )
    assert q["response_type"] == "code" and q["access_type"] == "offline"
    assert q["client_id"] == "cid.apps.googleusercontent.com"
    assert q["redirect_uri"] == "https://hinaa.example/v1/social/youtube/callback"
    assert set(q["scope"].split()) == {
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    }
    assert service.verify_state(cfg, q["state"]) == "alice"
    with pytest.raises(HinaaError):
        service.verify_state(cfg, q["state"][:-4] + "AAAA")
    with pytest.raises(HinaaError):
        service.verify_state(cfg, service.make_state(cfg, "alice", now=1.0))  # expired
    with pytest.raises(HinaaError):
        service.verify_state(cfg, "garbage")


def test_code_exchange_stores_encrypted_tokens_for_the_state_user(cfg):
    google = FakeGoogle()
    google_handler = google.handler

    def handler(request):
        if str(request.url).startswith("https://oauth2.googleapis.com/token"):
            google.requests.append(request)
            return httpx.Response(
                200,
                json={
                    "access_token": "ya29.NEW",
                    "refresh_token": "1//NEW",
                    "expires_in": 3600,
                    "scope": "s",
                },
            )
        return google_handler(request)

    state = service.make_state(cfg, "alice")

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await service.complete_youtube_connect(cfg, state, "auth-code", http)

    assert run(go()) == "alice"
    form = parse_qs(google.requests[0].content.decode())
    assert form["grant_type"] == ["authorization_code"] and form["code"] == ["auth-code"]
    assert form["redirect_uri"] == ["https://hinaa.example/v1/social/youtube/callback"]
    conn = service.connections(cfg, "alice")[0]
    assert conn["connected"] is True and conn["account"] == "My Channel"
    assert service.connections(cfg, "bob")[0]["connected"] is False


def test_connect_requires_configuration(tmp_path):
    reset_session_factory()
    bare = Settings(
        _env_file=None, HINAA_DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'b.db').as_posix()}"
    )
    with pytest.raises(HinaaError) as e:
        service.start_youtube_connect(bare, "alice")
    assert e.value.code == "YOUTUBE_NOT_CONFIGURED"
    reset_session_factory()


def test_list_uploads(cfg):
    _connect(cfg)
    google = FakeGoogle()

    async def go():
        async with google.client() as http:
            return await service.list_uploads(cfg, "alice", 5, http)

    items = run(go())
    assert items == [
        {
            "videoId": "abc",
            "title": "First",
            "publishedAt": "2026-01-01T00:00:00Z",
            "privacyStatus": "private",
            "url": "https://www.youtube.com/watch?v=abc",
        }
    ]
    assert (
        google.requests[1].url.params["playlistId"] == "UUx"
        and google.requests[1].url.params["maxResults"] == "5"
    )


# ---- content calendar link ---------------------------------------------------


def test_content_post_carries_media_and_is_published_from_the_calendar(cfg):
    post = productivity.create_post(
        cfg,
        "alice",
        ContentPostCreate(
            title="Reel",
            platform="youtube",
            caption="cap",
            tags=["a"],
            mediaPath="clip.mp4",
            publishPrivacy="unlisted",
        ),
    )
    assert (
        post["mediaPath"] == "clip.mp4"
        and post["publishPrivacy"] == "unlisted"
        and post["externalId"] is None
    )
    other = productivity.create_post(
        cfg, "alice", ContentPostCreate(title="IG", platform="instagram")
    )
    assert other["mediaPath"] is None  # backward compatible default
    _connect(cfg)
    google = FakeGoogle()

    async def go(post_id, user="alice"):
        async with google.client() as http:
            return await service.publish(cfg, user, confirm=True, post_id=post_id, http=http)

    result = run(go(post["id"]))
    body = json.loads(google.requests[0].content)
    assert (
        body["snippet"]["title"] == "Reel"
        and body["snippet"]["description"] == "cap"
        and body["status"]["privacyStatus"] == "unlisted"
    )
    saved = productivity.get_post(cfg, "alice", post["id"])
    assert (
        saved["externalId"] == "vid123"
        and saved["externalUrl"] == result["url"]
        and saved["status"] == "published"
    )
    with pytest.raises(HinaaError) as e:
        run(go(other["id"]))
    assert e.value.code == "SOCIAL_PLATFORM_MISMATCH"
    _connect(cfg, "bob")
    with pytest.raises(HinaaError) as e:
        run(go(post["id"], "bob"))
    assert e.value.code == "POST_NOT_FOUND"
    with get_session_factory(cfg)() as session:
        assert (
            session.scalar(select(ContentPost).where(ContentPost.id == post["id"])).media_path
            == "clip.mp4"
        )


# ---- REST --------------------------------------------------------------------


def test_rest_publish_needs_confirmation_and_connections(cfg):
    with TestClient(create_app(cfg)) as client:
        conns = client.get("/v1/social/connections", headers=ALICE).json()["items"]
        assert {c["id"]: c["status"] for c in conns}["x"] == "requires_setup"
        refused = client.post(
            "/v1/social/publish", json={"title": "T", "mediaPath": "clip.mp4"}, headers=ALICE
        )
        assert (
            refused.status_code == 409 and refused.json()["code"] == "SOCIAL_CONFIRMATION_REQUIRED"
        )
        unconnected = client.post(
            "/v1/social/publish",
            json={"confirm": True, "title": "T", "mediaPath": "clip.mp4"},
            headers=ALICE,
        )
        assert (
            unconnected.status_code == 409 and unconnected.json()["code"] == "YOUTUBE_NOT_CONNECTED"
        )
        auth_url = client.get("/api/v1/social/youtube/connect", headers=ALICE).json()["authUrl"]
        assert auth_url.startswith("https://accounts.google.com/")
        assert client.get("/v1/social/youtube/callback?state=bad&code=c").status_code == 400
        assert client.get("/v1/social/youtube/callback?error=access_denied").status_code == 400
        assert client.get("/v1/social/publish-log", headers=BOB).json()["items"] == []
        assert client.post("/v1/social/youtube/disconnect", headers=BOB).json() == {
            "disconnected": False
        }

# ruff: noqa: E501, S105, S106
