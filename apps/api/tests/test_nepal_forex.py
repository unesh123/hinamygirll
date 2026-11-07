"""Official NRB exchange-rate grounding for currency questions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
import pytest

from hinaa_api import nepal_forex
from hinaa_api.config import Settings
from hinaa_api.models import TurnRequest
from hinaa_api.nepal_forex import detect_forex_query, format_forex_block, nepal_forex_block, parse_nrb_payload
from hinaa_api.services import ConversationService


def _rate(iso3: str, name: str, unit: int, buy: str, sell: str) -> dict:
    return {"currency": {"iso3": iso3, "name": name, "unit": unit}, "buy": buy, "sell": sell}


def _payload(*days: tuple[str, list[dict]]) -> dict:
    return {"status": {"code": 200}, "data": {"payload": [{"date": d, "rates": r} for d, r in days]}}


RATES = [
    _rate("USD", "U.S. Dollar", 1, "149.96", "150.56"),
    _rate("INR", "Indian Rupee", 100, "160.00", "160.15"),
    _rate("JPY", "Japanese Yen", 10, "9.54", "9.58"),
    _rate("QAR", "Qatari Riyal", 1, "41.46", "41.62"),
    _rate("SAR", "Saudi Arabian Riyal", 1, "40.26", "40.42"),
]
PAYLOAD = _payload(("2026-11-06", [_rate("USD", "U.S. Dollar", 1, "1.00", "1.00")]), ("2026-11-07", RATES))


@pytest.fixture(autouse=True)
def _fresh_cache():
    nepal_forex._cache.clear()
    yield
    nepal_forex._cache.clear()


@pytest.mark.parametrize(
    ("text", "currencies"),
    [
        ("dollar rate kati cha?", ("USD",)),
        ("डलरको भाउ कति छ?", ("USD",)),
        ("mujhe dollar ka rate batao", ("USD",)),
        ("australian dollar rate", ("AUD",)),
        ("qatar riyal rate today", ("QAR",)),
        ("riyal ko rate", ("SAR", "QAR")),
        ("dubai dirham bhau", ("AED",)),
    ],
)
def test_detects_currency_questions_in_english_nepali_and_hindi(text: str, currencies: tuple[str, ...]) -> None:
    assert detect_forex_query(text).currencies == currencies


@pytest.mark.parametrize(
    "text",
    ["explain recursion", "I won the match, worth it", "I need dollars for my trip", "the price of rice"],
)
def test_ignores_non_currency_questions(text: str) -> None:
    assert detect_forex_query(text) is None


def test_bare_exchange_rate_question_gets_the_household_basket() -> None:
    assert detect_forex_query("exchange rate").currencies[:3] == ("USD", "INR", "EUR")


def test_reads_amounts_in_both_directions() -> None:
    assert detect_forex_query("250 dollars in nepali rupees").foreign_amount == Decimal("250")
    assert detect_forex_query("$250 to NPR").foreign_amount == Decimal("250")
    query = detect_forex_query("10000 rupees in dollars")
    assert (query.foreign_amount, query.npr_amount) == (None, Decimal("10000"))
    # "Indian rupees" is a foreign currency, not NPR.
    assert detect_forex_query("1000 indian rupees kati hunchha").foreign_amount == Decimal("1000")


def test_uses_the_newest_published_day() -> None:
    rates = parse_nrb_payload(PAYLOAD)
    assert rates.published == date(2026, 11, 7)
    assert rates.rates["USD"].buy == Decimal("149.96")


def test_rejects_malformed_payloads() -> None:
    assert parse_nrb_payload({"data": {}}) is None
    assert parse_nrb_payload(_payload(("2026-11-07", [_rate("USD", "x", 0, "1", "1")]))) is None


def test_formats_exact_rates_and_respects_quoting_units() -> None:
    rates = parse_nrb_payload(PAYLOAD)
    block = format_forex_block(detect_forex_query("1000 indian rupees kati hunchha"), rates, date(2026, 11, 7))
    assert "published 2026-11-07 (21 Kartik 2083 BS)" in block
    # NRB quotes INR per 100: 1,000 INR is 10 x Rs. 160.00.
    assert "- 100 INR (Indian Rupee) = Rs. 160.00 buying / Rs. 160.15 selling" in block
    assert "1,000 INR = Rs. 1,600.00 at the buying rate" in block and "Rs. 1,601.50 at the selling rate" in block
    assert "latest published rates, not today's" not in block


def test_converts_npr_to_foreign_at_the_selling_rate_and_flags_stale_dates() -> None:
    rates = parse_nrb_payload(PAYLOAD)
    block = format_forex_block(detect_forex_query("10000 rupees in dollars"), rates, date(2026, 11, 9))
    assert "Rs. 10,000.00 buys about 66.42 USD at the NRB selling rate" in block
    assert "latest published rates, not today's" in block


def _serve(monkeypatch: pytest.MonkeyPatch, handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        nepal_forex.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(record), **kwargs),
    )
    monkeypatch.setattr(nepal_forex, "nepal_now", lambda: __import__("datetime").datetime(2026, 11, 7, 10, 0))
    return seen


@pytest.mark.asyncio
async def test_fetches_once_then_serves_from_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _serve(monkeypatch, lambda _r: httpx.Response(200, json=PAYLOAD))
    first = await nepal_forex_block("dollar rate kati cha?")
    second = await nepal_forex_block("डलरको भाउ कति छ?")
    assert "1 USD (U.S. Dollar) = Rs. 149.96 buying" in first and first == second
    assert len(seen) == 1
    assert seen[0].url.params["from"] == "2026-11-01" and seen[0].url.params["to"] == "2026-11-07"


@pytest.mark.asyncio
async def test_unreachable_nrb_degrades_to_no_block(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, lambda _r: httpx.Response(503))
    assert await nepal_forex_block("dollar rate kati cha?") == ""


@pytest.mark.asyncio
async def test_week_old_rates_are_not_offered(monkeypatch: pytest.MonkeyPatch) -> None:
    old = _payload(("2026-10-20", RATES))
    _serve(monkeypatch, lambda _r: httpx.Response(200, json=old))
    assert await nepal_forex_block("dollar rate kati cha?") == ""


@pytest.mark.asyncio
async def test_non_currency_turns_never_call_nrb(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _serve(monkeypatch, lambda _r: httpx.Response(200, json=PAYLOAD))
    assert await nepal_forex_block("explain recursion") == ""
    assert seen == []


def _request(provider: str) -> TurnRequest:
    return TurnRequest(sessionId="fx", text="dollar rate kati cha?", companionId="hinaa", providerMode=provider)


@pytest.mark.asyncio
async def test_service_grounds_real_turns_but_not_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_block(_text: str) -> str:
        return "OFFICIAL EXCHANGE RATES — test"

    monkeypatch.setattr(nepal_forex, "nepal_forex_block", fake_block)
    service = ConversationService(Settings(HINAA_PROVIDER_MODE="mock", _env_file=None))
    assert await service._nepal_facts_block(_request("mock")) == ""
    assert await service._nepal_facts_block(_request("claude")) == "OFFICIAL EXCHANGE RATES — test"


def test_official_rates_lead_the_grounding_block() -> None:
    merge = ConversationService._with_nepal_facts
    assert merge("", "search") == "search"
    assert merge("nrb", "") == "nrb"
    assert merge("nrb", "search") == "nrb\n\nsearch"
