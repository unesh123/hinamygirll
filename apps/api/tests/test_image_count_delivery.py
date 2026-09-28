"""How many pictures a turn actually gets, from the ask to the wire.

Measured on his own turns: "20 images" came back as 3 because every image
source got its own `if anything matched: return`, and a batch of 8 renders
became 4 because one request asked the vendor for four and stopped there.
"""

from __future__ import annotations

import asyncio
import base64
from types import SimpleNamespace

import pytest

from hinaa_api.config import Settings
from hinaa_api.models import AssistantTurnPlan, ToolRequest
from hinaa_api.prompts import neutral_fallback_plan
from hinaa_api.services import ConversationService, ParsedCommand
from hinaa_api.tools import browser, freepik_suite
from hinaa_api.tools.intent_gate import gate_tool_requests


TINY_PNG_B64 = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode("ascii")


def _pics(source: str, how_many: int, subject: str = "supernatural landscape"):
    return [
        {
            "id": f"{source}-{i}",
            "title": f"{subject.title()} photo {i}",
            "imageUrl": f"https://{source}.test/{i}.jpg",
            "pageUrl": f"https://{source}.test/{i}",
            "source": source,
        }
        for i in range(how_many)
    ]


def _search(count: int, monkeypatch, **providers):
    async def fake_safebooru(query, count=6):
        return providers.get("safebooru", [])

    async def fake_multi(query, count=8):
        return {"images": providers.get("multi", []), "provider": "multi-source-web", "boards": []}

    async def fake_youcom(query, count=5):
        return {"images": providers.get("youcom", [])}

    async def fake_wiki(query, count=6):
        return providers.get("wikimedia", [])

    monkeypatch.setattr(browser, "search_safebooru_images", fake_safebooru)
    monkeypatch.setattr(browser, "search_multi_source_images", fake_multi)
    monkeypatch.setattr(browser, "search_wikimedia_images", fake_wiki)
    monkeypatch.setattr(browser.YouComClient, "image_search", fake_youcom)

    return asyncio.run(browser.search_images({
        "query": "supernatural landscape",
        "canonicalSubject": "supernatural landscape",
        "expectedEntities": ["supernatural landscape"],
        "providerProfile": "general_web_image_search",
        "count": count,
    }))


def test_twenty_pictures_needs_every_source_that_has_them(monkeypatch):
    """The old shape returned after Safebooru matched anything at all, so a
    request for 20 stopped at whatever the first source happened to hold."""
    result = _search(
        20,
        monkeypatch,
        safebooru=_pics("safebooru", 8),
        multi=_pics("multi", 7),
        wikimedia=_pics("wikimedia", 9),
    )
    assert result["imageCount"] == 20
    assert result["resultSet"]["count"] == 20
    assert "safebooru" in result["provider"]
    assert "wikimedia-commons" in result["provider"]


def test_one_picture_from_two_sources_is_still_one_picture(monkeypatch):
    """Different sources hand back the same file all the time. Counting it twice
    would promise him a grid that shows the same photo twice."""
    shared = _pics("safebooru", 3)
    result = _search(
        6,
        monkeypatch,
        safebooru=shared,
        multi=shared + _pics("multi", 2),
        wikimedia=_pics("wikimedia", 1),
    )
    urls = [img["imageUrl"] for img in result["images"]]
    assert len(urls) == len(set(urls)) == 6


def test_the_search_stops_asking_once_the_request_is_filled(monkeypatch):
    calls = {"youcom": 0}

    async def safebooru(query, count=6):
        return _pics("safebooru", 12)

    async def multi(query, count=8):
        return {"images": _pics("multi", 12), "provider": "multi-source-web", "boards": []}

    async def youcom(query, count=5):
        calls["youcom"] += 1
        return {"images": _pics("youcom", 4)}

    async def wiki(query, count=6):
        return _pics("wikimedia", 4)

    monkeypatch.setattr(browser, "search_safebooru_images", safebooru)
    monkeypatch.setattr(browser, "search_multi_source_images", multi)
    monkeypatch.setattr(browser, "search_wikimedia_images", wiki)
    monkeypatch.setattr(browser.YouComClient, "image_search", youcom)

    result = asyncio.run(browser.search_images({
        "query": "supernatural landscape",
        "canonicalSubject": "supernatural landscape",
        "expectedEntities": ["supernatural landscape"],
        "count": 6,
    }))
    assert result["imageCount"] == 6
    assert calls["youcom"] == 0


def test_a_short_result_is_counted_as_the_result_not_the_request(monkeypatch):
    """He asked for 20 and there were 4 to find. The card may not say 20."""
    result = _search(20, monkeypatch, safebooru=_pics("safebooru", 4))
    assert result["imageCount"] == 4
    assert result["resultSet"]["count"] == 4
    assert result["trace"]["rawResultCount"] == 4


def test_twenty_is_the_ceiling_and_nonsense_still_lands_on_the_default():
    assert browser.MAX_IMAGE_RESULTS == 20
    assert "20" in browser.image_search_def.parameters["count"]["description"]
    assert "maximum 12" not in str(browser.image_search_def.description)


# ─── generation batches ──────────────────────────────────────────────────────


class _Response:
    def __init__(self, payload, *, content=b"", status=200):
        self._payload = payload
        self.status_code = status
        self.text = ""
        self.content = content
        self.headers = {"content-type": "image/jpeg"}

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _Tracker:
    def __init__(self, allowed_requests: int | None = None):
        self.allowed_requests = allowed_requests
        self.recorded = 0

    def check_quota(self, credits_needed: int = 1):
        if self.allowed_requests is not None and self.recorded >= self.allowed_requests:
            return (False, self.recorded, 10)
        return (True, self.recorded, 500)

    def record_usage(self, action, model="flux-schnell", credits=1, **kwargs):
        self.recorded += 1


def _freepik(monkeypatch, tmp_path, *, posted, served_per_request, tracker):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, headers=None, json=None):
            posted.append(json)
            asked = json["num_images"]
            return _Response({
                "data": [
                    {"base64": TINY_PNG_B64}
                    for _ in range(min(asked, served_per_request))
                ]
            })

        async def get(self, url, timeout=None):
            return _Response({}, content=b"0" * 64)

    monkeypatch.setattr(freepik_suite.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(freepik_suite, "IMAGE_STORE", tmp_path)
    monkeypatch.setattr(freepik_suite, "usage_tracker", tracker)
    monkeypatch.setattr(
        freepik_suite,
        "get_settings",
        lambda: SimpleNamespace(active_freepik_key=SimpleNamespace(get_secret_value=lambda: "test-key")),
    )


def test_eight_images_are_asked_for_as_eight_images_not_four(monkeypatch, tmp_path):
    """`num_images` was clamped to 4 inside a single request, so the other four
    were never asked for and nothing said so."""
    posted: list[dict] = []
    tracker = _Tracker()
    _freepik(monkeypatch, tmp_path, posted=posted, served_per_request=4, tracker=tracker)

    entries = asyncio.run(freepik_suite.generate_freepik_image("a mountain lake", count=8))

    assert [payload["num_images"] for payload in posted] == [4, 4]
    assert len(entries) == 8
    assert len(list(tmp_path.glob("freepik_*.jpg"))) == 8
    assert tracker.recorded == 2


def test_one_image_still_costs_one_request(monkeypatch, tmp_path):
    posted: list[dict] = []
    tracker = _Tracker()
    _freepik(monkeypatch, tmp_path, posted=posted, served_per_request=4, tracker=tracker)

    entries = asyncio.run(freepik_suite.generate_freepik_image("a mountain lake", count=1))

    assert [payload["num_images"] for payload in posted] == [1]
    assert len(entries) == 1
    assert tracker.recorded == 1


def test_a_vendor_that_under_delivers_is_not_asked_again(monkeypatch, tmp_path):
    """The loop has to stop on a short answer. Re-asking a vendor that only
    serves two at a time would spend the whole daily budget for nothing."""
    posted: list[dict] = []
    tracker = _Tracker()
    _freepik(monkeypatch, tmp_path, posted=posted, served_per_request=2, tracker=tracker)

    entries = asyncio.run(freepik_suite.generate_freepik_image("a mountain lake", count=8))

    assert len(posted) == 1
    assert len(entries) == 2
    # Two images really rendered, so the day's meter has to say so.
    assert tracker.recorded == 1


def test_a_half_filled_set_is_reported_instead_of_raising(monkeypatch, tmp_path):
    """Four images really are on disk when the quota runs out. Turning that into
    an error would throw away the half he can still look at."""
    posted: list[dict] = []
    tracker = _Tracker(allowed_requests=1)
    _freepik(monkeypatch, tmp_path, posted=posted, served_per_request=4, tracker=tracker)

    entries = asyncio.run(freepik_suite.generate_freepik_image("a mountain lake", count=8))

    assert len(posted) == 1
    assert len(entries) == 4


def test_an_empty_set_still_raises_the_quota_error(monkeypatch, tmp_path):
    posted: list[dict] = []
    tracker = _Tracker(allowed_requests=0)
    _freepik(monkeypatch, tmp_path, posted=posted, served_per_request=4, tracker=tracker)

    with pytest.raises(freepik_suite.HinaaError) as raised:
        asyncio.run(freepik_suite.generate_freepik_image("a mountain lake", count=4))

    assert raised.value.code == "QUOTA_EXCEEDED"
    assert posted == []


# ─── his words setting the batch and the subject ─────────────────────────────


def _plan() -> AssistantTurnPlan:
    return neutral_fallback_plan(
        user_text="Thinking about that.",
        companion_id="hinaa",
        language="en-US",
        depth="standard",
    )


def _service() -> ConversationService:
    return ConversationService(Settings())


def _injected(text: str, tool_name: str) -> dict:
    service = _service()
    plan = _plan()
    service._inject_deterministic_tool_intents(text, plan)
    request = next(t for t in plan.toolRequests if t.toolName == tool_name)
    return request.parameters


def _slash(command: str, raw: str, tool_name: str) -> dict:
    service = _service()
    plan = _plan()
    service._map_explicit_command(ParsedCommand(command=command, args=raw.split(" ", 1)[1], raw=raw), plan)
    request = next(t for t in plan.toolRequests if t.toolName == tool_name)
    return request.parameters


def test_a_counted_range_leaves_his_subject_alone():
    """Measured on his turn "Generate 3 or 4 image of super natural landscape":
    only "4 image" was removed, so the renderer was told to draw a picture of
    "3 or of super natural landscape"."""
    kept, dropped, _ = gate_tool_requests(
        "Generate 3 or 4 image of super natural landscape",
        [ToolRequest(toolName="image_generate", parameters={"prompt": "placeholder", "count": 1})],
    )
    assert dropped == []
    parameters = kept[0].parameters
    assert parameters["prompt"] == "Super natural landscape"
    assert parameters["count"] == 4


def test_the_gate_honours_the_range_for_a_plain_batch_too():
    kept, _, _ = gate_tool_requests(
        "generate 3 images of a snowy mountain",
        [ToolRequest(toolName="image_generate", parameters={"prompt": "placeholder", "count": 1})],
    )
    assert kept[0].parameters == {"prompt": "Snowy mountain", "count": 3}


def test_twenty_pictures_reaches_the_tool_that_fetches_them():
    """The search tool pools providers up to 20, but every planner filled the
    call with a hard-coded six, so the ceiling could not be asked for."""
    parameters = _injected("give me 20 images tokyo ghoul", "image_search")
    assert parameters["count"] == 20


def test_an_unnumbered_picture_ask_keeps_the_grid_size():
    assert _injected("show me some mikasa images", "image_search")["count"] == 6


def test_a_flagged_fetch_count_is_clamped_to_the_ceiling():
    parameters = _slash("image_search", "/image_search cats --count=99", "image_search")
    assert parameters["count"] == 20


def test_a_slash_generate_counts_the_number_in_his_words():
    """/imagine read its batch size from --count only, so "6 images" queued one
    picture and left the digit inside the subject."""
    parameters = _slash("imagine", "/imagine 6 images of a red fox", "image_generate")
    assert parameters["count"] == 6
    assert "6" not in parameters["prompt"]
    assert "images" not in parameters["prompt"].lower()


def test_a_generate_batch_stops_where_the_renderer_stops():
    parameters = _slash("generate", "/generate 40 images of a cat", "image_generate")
    assert parameters["count"] == 10
