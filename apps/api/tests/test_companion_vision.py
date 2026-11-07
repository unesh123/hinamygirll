import base64
import json

import pytest
from starlette.testclient import TestClient

from hinaa_api.intelligence import companion_vision as cv
from hinaa_api.intelligence.companion_vision import CompanionVisionService
from hinaa_api.main import create_app

JPEG = base64.b64encode(b"\xff\xd8\xff\xe0fakejpeg").decode()


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make(payload, clock=None, **kw):
    async def analyzer(img, mime, prompt):
        p = payload() if callable(payload) else payload
        return None if p is None else json.dumps(p)

    return CompanionVisionService(analyzer=analyzer, clock=clock or Clock(), **kw)


SNACK = {"observations": ["holding chips"], "present": True, "salient_event": "snack",
         "emotion": "smug", "remark": "Chips again? Bold choice.", "wellbeing_flag": "none"}
IDLE = {"observations": ["at desk"], "present": True, "salient_event": "none",
        "emotion": "warm", "remark": "", "wellbeing_flag": "none"}


async def test_structured_reaction_and_cooldown():
    clock = Clock()
    svc = make(SNACK, clock)
    first = await svc.react(JPEG)
    assert first["should_speak"] and first["emotion"] == "smug" and first["salient_event"] == "snack"
    second = await svc.react(JPEG)
    assert not second["should_speak"] and second["reason"] == "cooldown"
    clock.t += 901
    assert (await svc.react(JPEG))["should_speak"]


async def test_invalid_enums_clamped_and_remark_truncated():
    svc = make({**SNACK, "emotion": "bogus", "remark": "word " * 60, "wellbeing_flag": "x"})
    r = await svc.react(JPEG)
    assert r["emotion"] == "neutral" and r["wellbeing_flag"] == "none"
    assert len(r["remark"].split()) <= 25


async def test_identifying_remark_suppressed():
    svc = make({**SNACK, "salient_event": "new_person", "remark": "That's John Smith behind you"})
    r = await svc.react(JPEG)
    assert not r["should_speak"] and r["remark"] == ""


async def test_no_provider_fallback():
    r = await make(None).react(JPEG)
    assert r["should_speak"] is False and r["reason"] == "no_multimodal_provider"


async def test_unparseable_output():
    async def analyzer(*a):
        return "not json"

    r = await CompanionVisionService(analyzer=analyzer).react(JPEG)
    assert r["should_speak"] is False


async def test_sedentary_nudge_timing():
    clock = Clock()
    svc = make(IDLE, clock, sedentary_minutes=45)
    for _ in range(16):
        r = await svc.react(JPEG)
        clock.t += 170
    assert not r["should_speak"]
    r = await svc.react(JPEG)
    assert r["should_speak"] and r["salient_event"] == "sedentary"
    assert r["wellbeing_flag"] == "sedentary" and "minutes" in r["remark"]
    clock.t += 170
    assert not (await svc.react(JPEG))["should_speak"]


async def test_absence_resets_sedentary():
    clock = Clock()
    state = {"p": IDLE}
    svc = make(lambda: state["p"], clock, sedentary_minutes=10)
    await svc.react(JPEG)
    clock.t += 500
    state["p"] = {**IDLE, "present": False, "salient_event": "absent"}
    await svc.react(JPEG)
    state["p"] = IDLE
    clock.t += 170
    await svc.react(JPEG)
    clock.t += 170
    assert not (await svc.react(JPEG))["should_speak"]


async def test_memory_candidate_only_when_opted_in():
    svc = make(SNACK)
    assert "memory_candidate" not in await svc.react(JPEG)
    assert (await svc.react(JPEG, store_observations=True))["memory_candidate"]


def test_size_cap_rejects_oversize():
    big = base64.b64encode(b"\0" * (cv.MAX_FRAME_BYTES + 1)).decode()
    with pytest.raises(cv.FrameTooLarge):
        cv.decode_frame(big)
    with pytest.raises(cv.InvalidFrame):
        cv.decode_frame("***")


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


def test_endpoint_contract(client, monkeypatch):
    monkeypatch.setattr(cv, "companion_vision_service", make(SNACK))
    r = client.post("/v1/vision/react", json={"frame": JPEG, "consent": True, "sessionId": "t"})
    assert r.status_code == 200 and r.json()["should_speak"] is True
    assert client.post("/v1/vision/react", json={"frame": JPEG}).status_code == 403
    big = base64.b64encode(b"\0" * (cv.MAX_FRAME_BYTES + 1)).decode()
    assert client.post("/v1/vision/react", json={"frame": big, "consent": True}).status_code == 413
    assert client.post("/v1/vision/react", json={"frame": "***", "consent": True}).status_code == 400


def test_endpoint_without_provider(client, monkeypatch):
    monkeypatch.setattr(cv, "companion_vision_service", make(None))
    r = client.post("/v1/vision/react", json={"frame": JPEG, "consent": True})
    assert r.status_code == 200 and r.json()["reason"] == "no_multimodal_provider"
