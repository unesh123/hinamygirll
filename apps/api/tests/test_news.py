"""News AI: canonicalisation, dedupe, ranking, cited digests, scheduler, isolation, migration."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.main import create_app
from hinaa_api.news import delivery, scheduler, service
from hinaa_api.news.digest import (
    DigestValidationError,
    build_items,
    extractive_items,
    validate_items,
)
from hinaa_api.news.feeds import parse_feed
from hinaa_api.news.ranker import rank
from hinaa_api.news.schemas import WatchlistCreate
from hinaa_api.news.text import Article, canonicalize_url, dedupe, title_similarity
from hinaa_api.persistence.db import get_session_factory, reset_session_factory
from hinaa_api.persistence.migrations import MIGRATIONS, run_migrations
from hinaa_api.tools import news as news_tools
from hinaa_api.tools.registry import registry

ALICE = {"X-HINAA-Dev-User": "alice"}
BOB = {"X-HINAA-Dev-User": "bob"}
NOW = datetime(2026, 11, 8, 6, 0, tzinfo=UTC)
_NOW_RSS = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S +0000")
_NOW_ATOM = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

RSS = f"""<?xml version="1.0"?><rss version="2.0"><channel><title>Kathmandu Wire</title>
<item><title>Nepal central bank cuts policy rate</title><link>https://www.example.com/a?utm_source=x&amp;id=1#top</link>
<description>&lt;p&gt;The central bank lowered the rate on Sunday. More detail follows.&lt;/p&gt;</description>
<pubDate>{_NOW_RSS}</pubDate></item>
<item><title>Cricket: Nepal beats UAE</title><link>https://example.com/cricket</link><pubDate>{_NOW_RSS}</pubDate></item>
</channel></rss>"""

ATOM = f"""<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom Feed</title>
<entry><title>Hydropower export deal signed</title><link rel="alternate" href="https://atom.example.org/hydro/"/>
<updated>{_NOW_ATOM}</updated><summary>Nepal signs a power export deal.</summary></entry></feed>"""


def art(title, url, hours_old=1.0, summary="", origin="feed"):
    return Article(
        title=title,
        url=url,
        published=NOW - timedelta(hours=hours_old),
        summary=summary,
        origin=origin,
    )


# ---- canonicalisation / dedupe ---------------------------------------------


def test_canonicalize_strips_tracking_fragment_www_and_slash():
    assert (
        canonicalize_url("HTTPS://www.Example.com:443/a//b/?utm_source=x&b=2&a=1&fbclid=z#frag")
        == "https://example.com/a/b?a=1&b=2"
    )
    assert canonicalize_url("https://example.com") == "https://example.com/"
    assert canonicalize_url("ftp://example.com/x") is None
    assert canonicalize_url("javascript:alert(1)") is None
    assert canonicalize_url("not a url") is None


def test_dedupe_by_url_and_near_duplicate_title():
    items = [
        art("Nepal central bank cuts policy rate", "https://a.com/x?utm_medium=1"),
        art(
            "Nepal central bank cuts policy rate", "https://www.a.com/x/"
        ),  # same URL after canonicalising
        art("Central bank of Nepal cuts policy rate", "https://b.com/y"),  # near duplicate title
        art("Everest base camp reopens", "https://c.com/z"),
    ]
    kept = dedupe(items)
    assert [k.url for k in kept] == ["https://a.com/x", "https://c.com/z"]
    assert kept[0].also == ["https://b.com/y"]
    assert title_similarity("Totally different words here", "Nepal central bank cuts") == 0.0


# ---- feeds -------------------------------------------------------------------


def test_parse_rss_and_atom():
    rss = parse_feed(RSS, "https://feed")
    assert [a.title for a in rss] == [
        "Nepal central bank cuts policy rate",
        "Cricket: Nepal beats UAE",
    ]
    assert rss[0].url == "https://example.com/a?id=1"
    assert rss[0].summary.startswith("The central bank lowered the rate")
    assert rss[0].source == "Kathmandu Wire" and rss[0].published is not None
    atom = parse_feed(ATOM)
    assert atom[0].url == "https://atom.example.org/hydro" and atom[0].published.year == 2026


def test_feed_with_entity_declaration_is_refused():
    bomb = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><rss><channel/></rss>'
    with pytest.raises(ValueError):
        parse_feed(bomb)


# ---- ranking -----------------------------------------------------------------


def test_rank_prefers_relevant_and_recent():
    old_relevant = art("Nepal economy grows", "https://a.com/1", hours_old=60)
    fresh_relevant = art("Nepal economy grows faster", "https://a.com/2", hours_old=1)
    fresh_unrelated = art("Local football derby", "https://a.com/3", hours_old=0.5)
    ranked = rank([old_relevant, fresh_unrelated, fresh_relevant], ["Nepal economy"], NOW)
    assert [a.url for a in ranked] == ["https://a.com/2", "https://a.com/1", "https://a.com/3"]
    assert ranked[0].score > ranked[1].score > ranked[2].score


# ---- digest: cites only fetched URLs ----------------------------------------


def _articles():
    return [
        art(
            "Nepal central bank cuts policy rate",
            "https://a.com/x",
            summary="The bank cut the rate. More.",
        ),
        art("Everest base camp reopens", "https://c.com/z"),
    ]


def test_extractive_digest_cites_fetched_urls_only():
    items = extractive_items(_articles(), 8)
    assert items[0]["urls"] == ["https://a.com/x"]
    validate_items(items, {"https://a.com/x", "https://c.com/z"})


def test_validate_rejects_fabricated_and_uncited_bullets():
    fetched = {"https://a.com/x"}
    with pytest.raises(DigestValidationError):
        validate_items([{"text": "Rate cut", "urls": ["https://invented.example/story"]}], fetched)
    with pytest.raises(DigestValidationError):
        validate_items([{"text": "Rate cut", "urls": []}], fetched)
    with pytest.raises(DigestValidationError):  # URL smuggled into the text
        validate_items(
            [{"text": "See https://invented.example/x", "urls": ["https://a.com/x"]}], fetched
        )


def test_llm_bullet_with_fabricated_url_is_dropped():
    async def llm(_prompt: str) -> str:
        return (
            '[{"text": "Central bank cut the rate.", "urls": ["https://www.a.com/x?utm_source=n"]},'
            ' {"text": "Made-up scoop.", "urls": ["https://fabricated.example/scoop"]}]'
        )

    items, by = asyncio.run(build_items(_articles(), llm))
    assert by == "llm"
    assert [i["text"] for i in items] == ["Central bank cut the rate."]
    assert items[0]["urls"] == ["https://a.com/x"]


def test_all_fabricated_llm_output_falls_back_to_extractive():
    async def llm(_prompt: str) -> str:
        return '[{"text": "Invented", "urls": ["https://fabricated.example/1"]}]'

    items, by = asyncio.run(build_items(_articles(), llm))
    assert by == "extractive" and items[0]["urls"] == ["https://a.com/x"]


def test_llm_failure_and_no_llm_use_extractive_fallback():
    async def broken(_prompt: str) -> str:
        raise RuntimeError("provider down")

    assert asyncio.run(build_items(_articles(), broken))[1] == "extractive"
    assert asyncio.run(build_items(_articles(), None))[1] == "extractive"


# ---- persistence, pipeline, scheduler ---------------------------------------


def _settings(url: str) -> Settings:
    return Settings(
        _env_file=None,
        HINAA_PROVIDER_MODE="mock",
        HINAA_DATABASE_URL=url,
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
        HINAA_NEWS_SCHEDULER_ENABLED=False,
        HINAA_VMC_PORT=0,
        AZURE_SPEECH_KEY="",
        AZURE_SPEECH_REGION="",
        ELEVENLABS_API_KEY="",
    )


@pytest.fixture
def news_settings(tmp_path):
    reset_session_factory()
    settings = _settings(f"sqlite+pysqlite:///{(tmp_path / 'news.db').as_posix()}")
    get_session_factory(settings)
    yield settings
    reset_session_factory()


class Recorder:
    name = "recorder"

    def __init__(self):
        self.sent = []

    async def deliver(self, user_id, digest):
        self.sent.append((user_id, digest))


def _feed_client(body=RSS):
    return httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body.encode()))
    )


def _create(settings, user="alice", **over):
    data = {
        "name": "Nepal watch",
        "topics": ["Nepal"],
        "sources": ["https://feeds.example.com/rss"],
        **over,
    }
    return service.create_watchlist(settings, user, WatchlistCreate(**data))


def test_run_watchlist_saves_cited_digest_and_delivers(news_settings):
    watch = _create(news_settings)
    rec = Recorder()

    async def go():
        async with _feed_client() as http:
            return await service.run_watchlist(
                news_settings,
                "alice",
                watch["id"],
                http=http,
                deliverers=[rec],
                now=NOW,
                use_defaults=False,
            )

    result = asyncio.run(go())
    digest = result["digest"]
    assert digest["generatedBy"] == "extractive" and digest["items"]
    fetched = {"https://example.com/a?id=1", "https://example.com/cricket"}
    assert {u for i in digest["items"] for u in i["urls"]} <= fetched
    assert set(digest["sources"]) <= fetched
    assert result["deliveries"] == [{"channel": "recorder", "ok": True}]
    assert rec.sent[0][0] == "alice" and rec.sent[0][1]["id"] == digest["id"]
    assert service.latest_digests(news_settings, "alice")["items"][0]["id"] == digest["id"]

    # A second run does not repeat stories that were already delivered.
    again = asyncio.run(go())
    assert again["digest"] is None and again["skippedSeen"] > 0


def test_failing_channel_does_not_block_others_or_the_digest(news_settings):
    watch = _create(news_settings)

    class Broken:
        name = "broken"

        async def deliver(self, user_id, digest):
            raise RuntimeError("channel down")

    rec = Recorder()

    async def go():
        async with _feed_client() as http:
            return await service.run_watchlist(
                news_settings,
                "alice",
                watch["id"],
                http=http,
                deliverers=[Broken(), rec],
                now=NOW,
                use_defaults=False,
            )

    result = asyncio.run(go())
    assert [d["ok"] for d in result["deliveries"]] == [False, True]
    assert result["digest"] is not None and rec.sent


def test_failed_feed_is_a_warning_not_a_fabrication(news_settings):
    watch = _create(news_settings)

    async def go():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(500))
        ) as http:
            return await service.run_watchlist(
                news_settings,
                "alice",
                watch["id"],
                http=http,
                deliverers=[],
                now=NOW,
                use_defaults=False,
            )

    result = asyncio.run(go())
    assert result["digest"] is None and result["warnings"]


def test_watchlist_without_any_source_or_search_provider_is_an_error(news_settings):
    watch = _create(news_settings, sources=[], keywords=["ai"])
    with pytest.raises(HinaaError) as caught:
        asyncio.run(service.run_watchlist(news_settings, "alice", watch["id"], use_defaults=False))
    assert caught.value.code == "NEWS_NO_SOURCES"


def test_search_results_are_merged_with_feeds(news_settings):
    watch = _create(
        news_settings, topics=["Nepal hydropower"], sources=["https://feeds.example.com/rss"]
    )

    async def search(query, limit):
        return [
            Article(
                "Nepal hydropower exports rise",
                "https://search.example.net/h?utm_x=1",
                published=NOW,
                origin="search",
            )
        ]

    async def go():
        async with _feed_client() as http:
            return await service.run_watchlist(
                news_settings,
                "alice",
                watch["id"],
                http=http,
                search=search,
                deliverers=[],
                now=NOW,
                use_defaults=False,
            )

    urls = {u for i in asyncio.run(go())["digest"]["items"] for u in i["urls"]}
    assert "https://search.example.net/h" in urls


def test_next_run_is_nepal_time_for_daily_and_hourly():
    # 06:00 UTC = 11:45 NPT -> next 08:00 NPT is tomorrow = 02:15 UTC the day after... computed in NPT
    nxt = service.next_run_after("daily", 8, NOW)
    assert nxt == datetime(2026, 11, 9, 2, 15, tzinfo=UTC)
    early = datetime(2026, 11, 8, 1, 0, tzinfo=UTC)  # 06:45 NPT
    assert service.next_run_after("daily", 8, early) == datetime(2026, 11, 8, 2, 15, tzinfo=UTC)
    assert service.next_run_after("hourly", 8, NOW) == datetime(2026, 11, 8, 7, 0, tzinfo=UTC)
    assert service.next_run_after("manual", 8, NOW) is None


def test_scheduler_runs_only_due_enabled_watchlists(news_settings):
    due = _create(news_settings, name="due", cadence="hourly")
    manual = _create(news_settings, name="manual", cadence="manual")
    later = _create(news_settings, name="later", cadence="daily")
    rec = Recorder()

    async def fire(moment):
        async with _feed_client() as http:
            return await scheduler.run_due(
                settings=news_settings, now=moment, http=http, deliverers=[rec], use_defaults=False
            )

    assert asyncio.run(fire(datetime.now(UTC) - timedelta(days=1))) == []  # nothing due in the past
    outcomes = asyncio.run(fire(datetime.now(UTC) + timedelta(hours=2)))
    assert due["id"] in {o["watchlistId"] for o in outcomes}
    assert later["id"] is not None
    assert manual["id"] not in {o["watchlistId"] for o in outcomes}
    after = service.get_watchlist(news_settings, "alice", due["id"])
    assert after["lastRunAt"] is not None and after["nextRunAt"] > after["lastRunAt"]


def test_scheduler_failure_advances_next_run(news_settings, monkeypatch):
    watch = _create(news_settings, cadence="hourly")

    async def boom(*args, **kwargs):
        raise RuntimeError("db hiccup")

    monkeypatch.setattr(service, "run_watchlist", boom)
    moment = datetime.now(UTC) + timedelta(hours=2)
    asyncio.run(scheduler.run_due(settings=news_settings, now=moment))
    assert (
        service.get_watchlist(news_settings, "alice", watch["id"])["nextRunAt"] > moment.isoformat()
    )


def test_app_lifespan_starts_news_scheduler(tmp_path, monkeypatch):
    started = {}

    async def fake(*, settings, stop, tick_seconds):
        started["tick"] = tick_seconds
        await stop.wait()

    monkeypatch.setattr("hinaa_api.main.run_news_scheduler", fake)
    reset_session_factory()
    settings = _settings(f"sqlite+pysqlite:///{(tmp_path / 'life.db').as_posix()}").model_copy(
        update={"news_scheduler_enabled": True}
    )
    with TestClient(create_app(settings)):
        pass
    reset_session_factory()
    assert started["tick"] == settings.news_tick_seconds


def test_in_app_deliverer_writes_idempotent_notification():
    class Store:
        def __init__(self):
            self.saved = []

        def get_notification_by_idempotency_key(self, tenant, key):
            return next((n for n in self.saved if n.idempotency_key == key), None)

        def save_notification(self, n):
            self.saved.append(n)

    store = Store()
    digest = {
        "id": "d1",
        "title": "T",
        "items": [{"text": "Lead", "urls": ["https://a.com/x"]}],
        "sources": ["https://a.com/x"],
    }
    deliverer = delivery.InAppDeliverer(store)
    asyncio.run(deliverer.deliver("alice", digest))
    asyncio.run(deliverer.deliver("alice", digest))
    assert (
        len(store.saved) == 1
        and store.saved[0].user_id == "alice"
        and store.saved[0].event_type == "news.digest"
    )
    assert isinstance(deliverer, delivery.Deliverer)


# ---- REST + isolation --------------------------------------------------------


@pytest.fixture
def client(news_settings, monkeypatch):
    monkeypatch.setattr(delivery, "_registry", {})

    async def fake_fetch(http, url):
        return parse_feed(RSS, url)

    monkeypatch.setattr(service, "fetch_feed", fake_fetch)
    with TestClient(create_app(news_settings)) as c:
        yield c


def test_rest_crud_run_now_and_isolation(client):
    body = {"name": "Econ", "topics": ["Nepal"], "sources": ["https://feeds.example.com/rss"]}
    created = client.post("/v1/news/watchlists", json=body, headers=ALICE)
    assert created.status_code == 201, created.text
    wid = created.json()["id"]

    # Bob sees nothing and cannot touch Alice's watchlist, digests or run it.
    assert client.get("/v1/news/watchlists", headers=BOB).json()["items"] == []
    for method, path in (("get", ""), ("delete", ""), ("post", "/run")):
        assert (
            getattr(client, method)(f"/v1/news/watchlists/{wid}{path}", headers=BOB).status_code
            == 404
        )
    assert (
        client.patch(f"/v1/news/watchlists/{wid}", json={"name": "x"}, headers=BOB).status_code
        == 404
    )

    run = client.post(f"/v1/news/watchlists/{wid}/run", headers=ALICE)
    assert run.status_code == 200, run.text
    digest = run.json()["digest"]
    assert digest and all(i["urls"] for i in digest["items"])
    assert client.get("/v1/news/digests", headers=ALICE).json()["items"][0]["id"] == digest["id"]
    assert client.get("/v1/news/digests", headers=BOB).json()["items"] == []
    assert client.get("/api/v1/news/watchlists", headers=ALICE).json()["total"] == 1

    patched = client.patch(
        f"/v1/news/watchlists/{wid}", json={"cadence": "hourly", "dailyHour": 6}, headers=ALICE
    )
    assert patched.json()["cadence"] == "hourly"
    assert client.delete(f"/v1/news/watchlists/{wid}", headers=ALICE).status_code == 204
    assert client.get("/v1/news/digests", headers=ALICE).json()["items"] == []


def test_rest_validation(client):
    assert (
        client.post("/v1/news/watchlists", json={"name": "Empty"}, headers=ALICE).status_code == 422
    )
    bad = {"name": "x", "sources": ["javascript:alert(1)"]}
    assert client.post("/v1/news/watchlists", json=bad, headers=ALICE).status_code == 422


# ---- agent tools -------------------------------------------------------------


def test_news_tools_registered_and_work(news_settings, monkeypatch):
    for name in ("news_watch_create", "news_digest_now", "news_latest"):
        assert registry.get_tool(name) is not None
    monkeypatch.setattr(service, "get_settings", lambda: news_settings)
    monkeypatch.setattr(delivery, "_registry", {})

    async def fake_fetch(http, url):
        return parse_feed(RSS, url)

    monkeypatch.setattr(service, "fetch_feed", fake_fetch)
    created = asyncio.run(
        news_tools.news_watch_create(
            {
                "userId": "alice",
                "topics": "Nepal",
                "feeds": "https://feeds.example.com/rss",
                "cadence": "hourly",
            }
        )
    )
    assert created["status"] == "success" and created["watchlist"]["cadence"] == "hourly"
    assert (
        asyncio.run(
            news_tools.news_watch_create({"userId": "alice", "cadence": "weekly", "topics": "x"})
        )["status"]
        == "failed"
    )
    assert (
        asyncio.run(news_tools.news_watch_create({"userId": "alice"}))["code"] == "WATCHLIST_EMPTY"
    )

    digest = asyncio.run(news_tools.news_digest_now({"userId": "alice"}))
    assert digest["status"] == "success" and "https://example.com/" in digest["summaryText"]
    latest = asyncio.run(news_tools.news_latest({"userId": "alice"}))
    assert latest["digests"][0]["items"]
    assert asyncio.run(news_tools.news_latest({"userId": "bob"}))["digests"] == []
    assert asyncio.run(news_tools.news_digest_now({"userId": "bob"}))["code"] == "NEWS_NO_WATCHLIST"


# ---- migration ---------------------------------------------------------------


def test_migration_0017_adds_tables_and_backward_compatible_columns(tmp_path):
    assert MIGRATIONS[-1][0] >= "0017" and "0017" in {v for v, _, _ in MIGRATIONS}
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as conn:  # a pre-0017 content_posts table holding a row
        conn.execute(
            text(
                "CREATE TABLE content_posts (id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(64), title VARCHAR(200))"
            )
        )
        conn.execute(text("INSERT INTO content_posts VALUES ('p1', 'alice', 'old post')"))
    applied = run_migrations(engine)
    assert "0017" in applied
    inspector = inspect(engine)
    assert {"news_watchlists", "news_digests", "social_tokens", "social_publish_log"} <= set(
        inspector.get_table_names()
    )
    cols = {c["name"] for c in inspector.get_columns("content_posts")}
    assert {"media_path", "publish_privacy", "external_id", "external_url"} <= cols
    with engine.connect() as conn:
        assert conn.execute(text("SELECT title, media_path FROM content_posts")).one() == (
            "old post",
            None,
        )
    assert run_migrations(engine) == []  # idempotent

# ruff: noqa: E501, S105, S106
