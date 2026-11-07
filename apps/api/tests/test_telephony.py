from __future__ import annotations

import json
import uuid

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from hinaa_api.config import Settings
from hinaa_api.persistence.db import make_engine
from hinaa_api.persistence.orm import Base
from hinaa_api.telephony import calls, twilio
from hinaa_api.telephony.router import build_telephony_router, is_webhook_path
from hinaa_api.tools import policy
from hinaa_api.tools.registry import registry

TOKEN = "unit-test-auth-token"
BASE = "https://hina.example.test"
OWNER = "+15551230001"


def make_settings(**overrides) -> Settings:
    values = dict(
        HINAA_PROVIDER_MODE="mock",
        TWILIO_ACCOUNT_SID="ACtest",
        TWILIO_AUTH_TOKEN=TOKEN,
        TWILIO_FROM_NUMBER="+15551230000",
        HINAA_OWNER_PHONE_NUMBER=OWNER,
        HINAA_PUBLIC_BASE_URL=BASE,
        HINAA_TELEPHONY_MAX_CALLS_PER_HOUR=2,
        ELEVENLABS_API_KEY="",
        _env_file=None,
    )
    values.update(overrides)
    return Settings(**values)


class FakeService:
    def __init__(self) -> None:
        self.requests = []

    async def stream_turn(self, request, correlation_id, *, user_id=None):
        self.requests.append(request)
        yield json.dumps({"type": "thinking"}).encode()
        yield json.dumps({"type": "plan", "plan": {"spokenText": "Sure **boss**, on it.", "displayText": "x"}}).encode()

    async def synthesize(self, request):  # pragma: no cover - mock mode never reaches it
        raise AssertionError("TTS must not run in mock mode")


class FakeMemory:
    def __init__(self) -> None:
        self.turns = []

    def append_turn(self, user_id, companion, conversation_id, user_text, assistant_text, language):
        self.turns.append((user_id, user_text, assistant_text))
        return "conv-1"


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch):
    engine = make_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    monkeypatch.setattr(calls, "get_session_factory", lambda _s: factory)
    calls.reset_runtime_state()
    yield
    calls.reset_runtime_state()


def signed_post(client, path, data, settings, token=TOKEN, sign=True):
    headers = {}
    if sign:
        headers["X-Twilio-Signature"] = twilio.compute_signature(token, BASE + path, list(data.items()))
    return client.post(path, data=data, headers=headers)


def add_error_handler(app):
    from fastapi.responses import JSONResponse
    from hinaa_api.errors import HinaaError

    @app.exception_handler(HinaaError)
    async def handler(_r, e):
        return JSONResponse({"error": {"code": e.code}}, status_code=e.status_code)


def make_client(settings, service=None, memory=None, transport=None):
    app = FastAPI()

    async def auth():
        return object()

    app.include_router(build_telephony_router(settings, service or FakeService(), memory, auth, transport))
    add_error_handler(app)
    return TestClient(app)


def test_signature_known_vector():
    # Vector from Twilio's security docs (HMAC-SHA1 over URL + sorted params).
    token = "12345"
    url = "https://mycompany.com/myapp.php?foo=1&bar=2"
    params = [
        ("Digits", "1234"), ("To", "+18005551212"), ("From", "+14158675310"),
        ("Caller", "+14158675310"), ("CallSid", "CA1234567890ABCDE"),
    ]
    assert twilio.compute_signature(token, url, params) == "GvWf1cFY/Q7PnoempGyD5oXAezc="
    assert twilio.validate_signature(token, url, params, "GvWf1cFY/Q7PnoempGyD5oXAezc=")
    assert not twilio.validate_signature(token, url, params, "bogus")
    assert not twilio.validate_signature(token, url, params, None)


def test_webhook_rejects_bad_or_missing_signature():
    s = make_settings()
    client = make_client(s)
    data = {"CallSid": "CA1", "Direction": "outbound-api"}
    assert signed_post(client, calls.VOICE_PATH, data, s, sign=False).status_code == 403
    assert signed_post(client, calls.VOICE_PATH, data, s, token="wrong").status_code == 403
    assert signed_post(client, calls.GATHER_PATH, data, s, token="wrong").status_code == 403
    assert signed_post(client, calls.STATUS_PATH, data, s, token="wrong").status_code == 403


def test_voice_webhook_twiml_shape_outbound_uses_opening_line():
    s = make_settings()
    sid = "CA" + uuid.uuid4().hex
    calls._states[sid] = calls.CallState(sid, "outbound", "Hello boss, are you busy?")
    res = signed_post(make_client(s), calls.VOICE_PATH, {"CallSid": sid, "Direction": "outbound-api"}, s)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/xml")
    body = res.text
    assert body.startswith('<?xml version="1.0" encoding="UTF-8"?><Response><Gather input="speech"')
    assert f'action="{BASE}{calls.GATHER_PATH}"' in body
    assert "<Say" in body and "Hello boss, are you busy?" in body


def test_inbound_from_unknown_number_is_rejected():
    s = make_settings()
    client = make_client(s)
    stranger = {"CallSid": "CA" + uuid.uuid4().hex, "Direction": "inbound", "From": "+15559998888"}
    res = signed_post(client, calls.VOICE_PATH, stranger, s)
    assert "<Hangup/>" in res.text and "<Gather" not in res.text
    owner = {"CallSid": "CA" + uuid.uuid4().hex, "Direction": "inbound", "From": OWNER, "To": "+15551230000"}
    res = signed_post(client, calls.VOICE_PATH, owner, s)
    assert "<Gather" in res.text
    assert calls.list_calls(s)[0]["direction"] == "inbound"


def test_conversation_turn_uses_chat_pipeline_and_persists():
    s = make_settings(HINAA_TELEPHONY_USER_ID="user-1")
    service, memory = FakeService(), FakeMemory()
    client = make_client(s, service, memory)
    sid = "CA" + uuid.uuid4().hex
    voice = {"CallSid": sid, "Direction": "inbound", "From": OWNER, "To": "+15551230000"}
    signed_post(client, calls.VOICE_PATH, voice, s)
    res = signed_post(client, calls.GATHER_PATH, {"CallSid": sid, "SpeechResult": "remind me about lunch"}, s)
    assert res.status_code == 200
    assert "Sure boss, on it." in res.text and "<Gather" in res.text and "**" not in res.text
    req = service.requests[0]
    assert req.text.startswith(calls.PHONE_INSTRUCTION) and req.text.endswith("remind me about lunch")
    assert memory.turns == [("user-1", "remind me about lunch", "Sure boss, on it.")]
    logged = calls.list_calls(s)[0]
    assert logged["transcript"][0] == {"role": "user", "content": "remind me about lunch"}
    # Second turn carries the first as history.
    signed_post(client, calls.GATHER_PATH, {"CallSid": sid, "SpeechResult": "thanks bye"}, s)
    assert len(service.requests[1].history) == 2


def test_goodbye_hangs_up_and_silence_ends_call():
    s = make_settings()
    client = make_client(s)
    sid = "CA" + uuid.uuid4().hex
    res = signed_post(client, calls.GATHER_PATH, {"CallSid": sid, "SpeechResult": "ok bye"}, s)
    assert "<Hangup/>" in res.text
    sid2 = "CA" + uuid.uuid4().hex
    first = signed_post(client, calls.GATHER_PATH, {"CallSid": sid2}, s)
    assert "<Gather" in first.text
    assert "<Hangup/>" in signed_post(client, calls.GATHER_PATH, {"CallSid": sid2}, s).text


def test_status_callback_updates_call_log():
    s = make_settings()
    sid = "CA" + uuid.uuid4().hex
    st = calls.CallState(sid, "outbound", "hi")
    calls.record_call(s, st, to=OWNER, from_="+15551230000")
    res = signed_post(make_client(s), calls.STATUS_PATH, {"CallSid": sid, "CallStatus": "completed"}, s)
    assert res.status_code == 204
    assert calls.list_calls(s)[0]["status"] == "completed"


def test_audio_served_by_token_only():
    s = make_settings()
    client = make_client(s)
    token = calls.store_audio(b"ID3fakemp3")
    ok = client.get(calls.AUDIO_PREFIX + token)
    assert ok.status_code == 200 and ok.headers["content-type"] == "audio/mpeg"
    assert client.get(calls.AUDIO_PREFIX + "nope").status_code == 404


def twilio_transport(seen):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201, json={"sid": "CA" + uuid.uuid4().hex, "status": "queued"})

    return httpx.MockTransport(handler)


def test_outbound_call_posts_to_twilio_and_masks_number():
    s = make_settings()
    seen: list[httpx.Request] = []
    client = make_client(s, transport=twilio_transport(seen))
    res = client.post("/v1/telephony/calls", json={"reason": "your 5pm meeting"})
    assert res.status_code == 200, res.text
    assert OWNER not in res.text and res.json()["to"].startswith("+15")
    req = seen[0]
    assert str(req.url) == "https://api.twilio.com/2010-04-01/Accounts/ACtest/Calls.json"
    form = req.content.decode()
    assert "Url=https%3A%2F%2Fhina.example.test%2Fv1%2Ftelephony%2Fvoice" in form
    assert "To=%2B15551230001" in form
    state = calls._states[res.json()["callSid"]]
    assert "your 5pm meeting" in state.opening
    assert client.get("/v1/telephony/calls").json()[0]["direction"] == "outbound"


def test_outbound_allow_list_enforced():
    s = make_settings(HINAA_TELEPHONY_ALLOWED_NUMBERS="+15551230002, +15551230003")
    seen: list[httpx.Request] = []
    client = make_client(s, transport=twilio_transport(seen))
    bad = client.post("/v1/telephony/calls", json={"to": "+19005550100"})
    assert bad.status_code == 403 and bad.json()["error"]["code"] == "TELEPHONY_NUMBER_NOT_ALLOWED"
    assert not seen
    assert client.post("/v1/telephony/calls", json={"to": "+1 (555) 123-0002"}).status_code == 200
    assert client.post("/v1/telephony/calls", json={"to": "not-a-number"}).status_code == 422


def test_outbound_rate_limit():
    s = make_settings()
    seen: list[httpx.Request] = []
    client = make_client(s, transport=twilio_transport(seen))
    assert client.post("/v1/telephony/calls", json={}).status_code == 200
    assert client.post("/v1/telephony/calls", json={}).status_code == 200
    assert client.post("/v1/telephony/calls", json={}).status_code == 429
    assert len(seen) == 2


def test_not_configured_reports_cleanly():
    s = make_settings(TWILIO_ACCOUNT_SID="", TWILIO_AUTH_TOKEN="", HINAA_PUBLIC_BASE_URL="")
    client = make_client(s)
    status = client.get("/v1/telephony/status").json()
    assert status["configured"] is False
    assert "TWILIO_AUTH_TOKEN" in status["missing"]
    assert client.post("/v1/telephony/calls", json={}).status_code == 503
    assert client.post(calls.VOICE_PATH, data={"CallSid": "CA1"}).status_code == 503


def test_status_masks_owner_number():
    s = make_settings()
    status = make_client(s).get("/v1/telephony/status").json()
    assert status["configured"] is True
    assert status["ownerNumber"] != OWNER and status["ownerNumber"].endswith("01")
    assert "TOKEN" not in json.dumps(status) and TOKEN not in json.dumps(status)


def test_management_routes_require_auth():
    s = make_settings()
    app = FastAPI()

    async def anon():
        return None

    app.include_router(build_telephony_router(s, FakeService(), None, anon))
    add_error_handler(app)

    client = TestClient(app)
    assert client.get("/v1/telephony/status").status_code == 401
    assert client.post("/v1/telephony/calls", json={}).status_code == 401


def test_only_webhooks_are_auth_exempt():
    for p in (calls.VOICE_PATH, calls.GATHER_PATH, calls.STATUS_PATH, calls.AUDIO_PREFIX + "abc"):
        assert is_webhook_path(p)
    for p in ("/v1/telephony/calls", "/v1/telephony/status", "/v1/telephony/voice/extra", "/v1/telephony"):
        assert not is_webhook_path(p)


def test_phone_call_tool_is_high_risk_and_confirmed():
    import hinaa_api.tools  # noqa: F401  (registers tools)

    tool = registry.get_tool("phone_call_user")
    assert tool is not None
    assert tool.risk_level == "high" and tool.requires_confirmation is True
    assert "phone_call_user" in policy.IRREVERSIBLE_EXTERNAL_TOOLS


@pytest.mark.asyncio
async def test_phone_call_tool_reports_not_configured():
    from hinaa_api.tools.phone_call import execute_phone_call_user

    out = await execute_phone_call_user({})
    assert out["status"] == "failed" and out["code"] == "TELEPHONY_NOT_CONFIGURED"
