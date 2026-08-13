from __future__ import annotations

import asyncio

from hinaa_api.tools import youtube


class _FakePage:
    def __init__(self) -> None:
        self.url = "https://www.youtube.com/watch?v=abc123"
        self.visited: list[str] = []

    async def goto(self, url: str, **_: object) -> None:
        self.visited.append(url)
        self.url = url

    async def bring_to_front(self) -> None:
        return None

    async def wait_for_timeout(self, _: int) -> None:
        return None


def test_youtube_tool_requires_explicit_confirmation() -> None:
    assert youtube.youtube_playback_request_def.requires_confirmation is True
    assert youtube.youtube_playback_request_def.cancellable is True


def test_watch_url_accepts_only_first_party_watch_targets() -> None:
    assert youtube._watch_url("/watch?v=abc123") == "https://www.youtube.com/watch?v=abc123"
    assert youtube._watch_url("https://www.youtube.com/watch?v=abc123&list=xyz") == "https://www.youtube.com/watch?v=abc123&list=xyz"
    assert youtube._watch_url("https://evil.example/watch?v=abc123") is None
    assert youtube._watch_url("https://www.youtube.com/results?search_query=music") is None


def test_media_verification_requires_unpaused_advancing_ready_media() -> None:
    assert youtube._is_verified_playback(
        {"exists": True, "readyState": 4, "currentTime": 1.0, "paused": False},
        {"exists": True, "readyState": 4, "currentTime": 2.0, "paused": False},
    )
    assert not youtube._is_verified_playback(
        {"exists": True, "readyState": 4, "currentTime": 1.0, "paused": False},
        {"exists": True, "readyState": 4, "currentTime": 1.0, "paused": False},
    )
    assert not youtube._is_verified_playback(
        {"exists": True, "readyState": 4, "currentTime": 1.0, "paused": False},
        {"exists": True, "readyState": 4, "currentTime": 2.0, "paused": True},
    )


def test_playback_reports_success_only_with_observed_media_progress(monkeypatch) -> None:
    page = _FakePage()
    snapshots = iter(
        [
            {"exists": True, "readyState": 4, "currentTime": 0.2, "paused": False, "muted": False},
            {"exists": True, "readyState": 4, "currentTime": 1.4, "paused": False, "muted": False},
        ]
    )

    async def fake_page() -> _FakePage:
        return page

    async def fake_keep(_: _FakePage) -> int:
        return 1

    async def fake_select(_: _FakePage, __: str) -> tuple[str, str]:
        return "https://www.youtube.com/watch?v=abc123", "Example song"

    async def fake_request(_: _FakePage) -> None:
        return None

    async def fake_snapshot(_: _FakePage) -> dict[str, object]:
        return next(snapshots)

    monkeypatch.setattr(youtube, "_get_page", fake_page)
    monkeypatch.setattr(youtube, "_keep_single_owned_page", fake_keep)
    monkeypatch.setattr(youtube, "_select_first_video", fake_select)
    monkeypatch.setattr(youtube, "_request_media_playback", fake_request)
    monkeypatch.setattr(youtube, "_media_snapshot", fake_snapshot)

    result = asyncio.run(youtube.play_youtube_video(youtube.PlayYoutubeVideoParams(query="example song")))

    assert result["status"] == "success"
    assert result["data"]["verified"] is True
    assert result["data"]["ownedPageCount"] == 1
    assert "autoplay=1" in page.visited[-1]


def test_playback_reports_blocked_when_media_does_not_advance(monkeypatch) -> None:
    page = _FakePage()
    snapshots = iter(
        [
            {"exists": True, "readyState": 4, "currentTime": 0.2, "paused": True, "muted": False},
            {"exists": True, "readyState": 4, "currentTime": 0.2, "paused": True, "muted": False},
        ]
    )

    async def fake_page() -> _FakePage:
        return page

    async def fake_keep(_: _FakePage) -> int:
        return 1

    async def fake_select(_: _FakePage, __: str) -> tuple[str, str]:
        return "https://www.youtube.com/watch?v=abc123", "Example song"

    async def fake_request(_: _FakePage) -> None:
        return None

    async def fake_snapshot(_: _FakePage) -> dict[str, object]:
        return next(snapshots)

    monkeypatch.setattr(youtube, "_get_page", fake_page)
    monkeypatch.setattr(youtube, "_keep_single_owned_page", fake_keep)
    monkeypatch.setattr(youtube, "_select_first_video", fake_select)
    monkeypatch.setattr(youtube, "_request_media_playback", fake_request)
    monkeypatch.setattr(youtube, "_media_snapshot", fake_snapshot)

    result = asyncio.run(youtube.play_youtube_video(youtube.PlayYoutubeVideoParams(query="example song")))

    assert result["status"] == "blocked"
    assert result["data"]["verified"] is False
    assert result["data"]["state"] == "needs-user-play"
