"""Official Nepal Rastra Bank (NRB) exchange rates as trusted prompt context.

"Dollar rate kati cha?" is one of the most common questions a Nepali assistant
gets. Search snippets are often stale or from money changers, so currency
questions are grounded in NRB's public forex API instead.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import httpx

from .nepal_calendar import bikram_sambat_label, nepal_now

logger = logging.getLogger("hinaa.nepal_forex")

NRB_RATES_URL = "https://www.nrb.org.np/api/forex/v1/rates"
_CACHE_TTL_SECONDS = 30 * 60
# Shown when he asks about "exchange rates" without naming a currency: the
# currencies most Nepali households deal with (remittance corridors first).
DEFAULT_CURRENCIES = ("USD", "INR", "EUR", "GBP", "AUD", "QAR", "SAR", "AED", "MYR", "KRW", "JPY")

# Specific names come before the bare "dollar" so "australian dollar" is not read as USD.
_CURRENCY_ALIASES: tuple[tuple[str, str], ...] = (
    ("AUD", r"\baud\b|australian\s+dollars?|अस्ट्रेलियन\s*डलर"),
    ("CAD", r"\bcad\b|canadian\s+dollars?|क्यानेडियन\s*डलर"),
    ("SGD", r"\bsgd\b|singapore\s+dollars?"),
    ("HKD", r"\bhkd\b|hong\s*kong\s+dollars?"),
    ("USD", r"\busd\b|\bus\s*dollars?|american\s+dollars?|\bdollars?\b|\$|डलर|डॉलर"),
    ("INR", r"\binr\b|indian\s+(?:rupees?|rupaiya|currency)|\bbharu\b|भारु|भारतीय\s*(?:रुपैयाँ|रुपया|मुद्रा)"),
    ("EUR", r"\beur\b|\beuros?\b|युरो"),
    ("GBP", r"\bgbp\b|\bpounds?\b|sterling|पाउन्ड"),
    ("CHF", r"\bchf\b|swiss\s+franc"),
    ("JPY", r"\bjpy\b|\byen\b|येन"),
    ("CNY", r"\bcny\b|\byuan\b|\brmb\b|युआन"),
    ("SAR", r"\bsar\b|saudi\s+(?:riyal|rial)|साउदी"),
    ("QAR", r"\bqar\b|qatar(?:i)?\s+(?:riyal|rial)|कतारी|कतार\s*रियाल"),
    ("AED", r"\baed\b|dirhams?|दिराम|दिरहम|\buae\b|dubai"),
    ("MYR", r"\bmyr\b|ringgit|रिङ्गिट|रिंगिट|malaysian\s+(?:currency|money)"),
    # Bare "won" is left out: "I won ... worth" is far more common than the currency.
    ("KRW", r"\bkrw\b|korean\s+won|कोरियन\s*वन"),
    ("KWD", r"\bkwd\b|kuwait(?:i|y)?\s+dinar"),
    ("BHD", r"\bbhd\b|bahrain(?:i)?\s+dinar"),
    ("OMR", r"\bomr\b|omani?\s+(?:rial|riyal)"),
    ("THB", r"\bthb\b|\bbaht\b"),
)
_BARE_RIYAL = re.compile(r"\briyals?\b|\brials?\b|रियाल")
_BARE_DINAR = re.compile(r"\bdinars?\b|दिनार")

_RATE_WORDS = re.compile(
    r"\b(?:rates?|exchange|forex|convert|conversion|price|value|worth|kati|kitna|kitne|bhau|bhaau|"
    r"dar|rupees?|rupaiya|npr|nrs|rs|nepali|paisa)\b|how\s+much|नेपाली|पैसा|भाउ|दर|रेट|कति|कितना|रुपैयाँ|रुपैयां|रूपैयाँ|रुपया|नेरु|विनिमय"
)
_NUMBER = r"(\d[\d,]*(?:\.\d+)?)"
_NPR_AMOUNT = re.compile(
    _NUMBER + r"\s*(?:npr|nrs|rs\.?|(?<!indian\s)rupees?|(?<!indian\s)rupaiya|रुपैयाँ|रुपैयां|रु\.?|नेरु)"
    r"|(?:npr|nrs|rs\.?|रु\.?)\s*" + _NUMBER,
)


@dataclass(frozen=True)
class ForexQuery:
    currencies: tuple[str, ...]
    # Amount of a foreign currency to convert into NPR ("250 dollars").
    foreign_amount: Decimal | None = None
    # Amount of NPR to convert into the first currency ("10000 rupees in dollars").
    npr_amount: Decimal | None = None


@dataclass(frozen=True)
class Rate:
    iso3: str
    name: str
    unit: int
    buy: Decimal
    sell: Decimal


@dataclass
class NrbRates:
    published: date
    rates: dict[str, Rate] = field(default_factory=dict)


def _amount(raw: str) -> Decimal | None:
    try:
        value = Decimal(raw.replace(",", ""))
    except InvalidOperation:
        return None
    return value if value > 0 else None


def detect_forex_query(text: str) -> ForexQuery | None:
    """A currency question, or None. Needs a currency plus rate/price wording, or 'exchange rate'."""
    lowered = text.casefold()
    found: list[str] = []
    spans: list[tuple[int, int]] = []
    for iso3, pattern in _CURRENCY_ALIASES:
        for match in re.finditer(pattern, lowered):
            # "australian dollar" must not also count as a bare US "dollar".
            if any(start <= match.start() < end for start, end in spans):
                continue
            spans.append(match.span())
            if iso3 not in found:
                found.append(iso3)
    if not any(code in found for code in ("SAR", "QAR", "OMR")) and _BARE_RIYAL.search(lowered):
        found.extend(["SAR", "QAR"])
    if not any(code in found for code in ("KWD", "BHD")) and _BARE_DINAR.search(lowered):
        found.extend(["KWD", "BHD"])

    asks_rate = bool(_RATE_WORDS.search(lowered))
    general = bool(re.search(r"exchange\s+rates?|forex|विनिमय\s*दर", lowered))
    if not found and not general:
        return None
    if found and not asks_rate:
        return None

    foreign_amount = None
    first_pattern = dict(_CURRENCY_ALIASES).get(found[0]) if found else None
    if first_pattern:
        near = re.search(_NUMBER + r"\s*(?:" + first_pattern + r")", lowered)
        if near is None and found[0] == "USD":
            near = re.search(r"\$\s*" + _NUMBER, lowered)
        if near:
            foreign_amount = _amount(near.group(1))
    npr_amount = None
    if found and foreign_amount is None:
        npr = _NPR_AMOUNT.search(lowered)
        if npr:
            npr_amount = _amount(npr.group(1) or npr.group(2))
    return ForexQuery(tuple(found) or DEFAULT_CURRENCIES, foreign_amount, npr_amount)


def parse_nrb_payload(payload: dict) -> NrbRates | None:
    """Latest day in an NRB /forex/v1/rates response (days arrive oldest first)."""
    try:
        days = payload["data"]["payload"]
        latest = max(days, key=lambda day: day["date"])
        rates: dict[str, Rate] = {}
        for item in latest["rates"]:
            currency = item["currency"]
            rate = Rate(
                iso3=str(currency["iso3"]).upper(),
                name=str(currency["name"]),
                unit=int(currency["unit"]),
                buy=Decimal(str(item["buy"])),
                sell=Decimal(str(item["sell"])),
            )
            if rate.unit > 0 and rate.buy > 0 and rate.sell > 0:
                rates[rate.iso3] = rate
        if not rates:
            return None
        return NrbRates(published=date.fromisoformat(str(latest["date"])[:10]), rates=rates)
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None


_cache: dict[str, object] = {}


async def fetch_latest_rates(today: date | None = None) -> NrbRates | None:
    """NRB publishes daily but not on every holiday, so read the last week and take the newest day."""
    today = today or nepal_now().date()
    cached = _cache.get("rates")
    if cached is not None and time.monotonic() - float(_cache.get("at", 0.0)) < _CACHE_TTL_SECONDS:
        return cached  # type: ignore[return-value]
    params = {"page": 1, "per_page": 10, "from": (today - timedelta(days=6)).isoformat(), "to": today.isoformat()}
    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            response = await client.get(NRB_RATES_URL, params=params)
            response.raise_for_status()
            rates = parse_nrb_payload(response.json())
    except (httpx.HTTPError, ValueError):
        logger.info("NRB forex rates unavailable", exc_info=True)
        return None
    if rates is not None:
        _cache.update(rates=rates, at=time.monotonic())
    return rates


def _npr(value: Decimal) -> str:
    return f"Rs. {value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,}"


def format_forex_block(query: ForexQuery, rates: NrbRates, today: date) -> str:
    wanted = [rates.rates[code] for code in query.currencies if code in rates.rates]
    if not wanted:
        return ""
    bs = bikram_sambat_label(datetime.combine(rates.published, datetime.min.time()))
    published = rates.published.isoformat() + (f" ({bs.split(' (')[0]})" if bs else "")
    lines = [
        f"OFFICIAL EXCHANGE RATES — Nepal Rastra Bank (NRB), published {published}. Source: https://www.nrb.org.np/forex/",
    ]
    for rate in wanted:
        lines.append(
            f"- {rate.unit} {rate.iso3} ({rate.name}) = {_npr(rate.buy)} buying / {_npr(rate.sell)} selling"
        )
    first = wanted[0]
    if query.foreign_amount is not None:
        units = query.foreign_amount / first.unit
        lines.append(
            f"- Conversion: {query.foreign_amount:,} {first.iso3} = {_npr(units * first.buy)} at the buying rate "
            f"(what a bank pays when he sells {first.iso3}) / {_npr(units * first.sell)} at the selling rate "
            f"(what he pays to buy {first.iso3})."
        )
    elif query.npr_amount is not None:
        amount = (query.npr_amount / first.sell * first.unit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        lines.append(
            f"- Conversion: {_npr(query.npr_amount)} buys about {amount:,} {first.iso3} at the NRB selling rate."
        )
    stale_note = (
        " These are the latest published rates, not today's; say so."
        if rates.published < today
        else ""
    )
    lines.append(
        "RULES: Quote these exact NRB numbers with the published date and cite Nepal Rastra Bank; never invent or "
        "round them differently. Banks and money changers differ slightly from NRB reference rates, and remittance "
        f"companies set their own rates.{stale_note} Use this only if he is asking about currency."
    )
    return "\n".join(lines)


async def nepal_forex_block(text: str) -> str:
    """Trusted prompt context for a currency question, or '' when not applicable or NRB is unreachable."""
    query = detect_forex_query(text)
    if query is None:
        return ""
    today = nepal_now().date()
    rates = await fetch_latest_rates(today)
    if rates is None or (today - rates.published).days > 7:
        return ""
    return format_forex_block(query, rates, today)
