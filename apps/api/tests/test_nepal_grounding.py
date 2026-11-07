"""Nepal time, Bikram Sambat grounding, and authoritative client history."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hinaa_api.config import Settings
from hinaa_api.models import TurnRequest
from hinaa_api.nepal_calendar import bikram_sambat_label, nepal_now
from hinaa_api.prompts import assembly
from hinaa_api.services import ConversationService


@pytest.mark.parametrize(
    ("utc", "expected"),
    [
        # Nepali New Year (1 Baisakh) anchors.
        (datetime(2024, 4, 13, 6, 0, tzinfo=timezone.utc), "1 Baishakh 2081 BS"),
        (datetime(2025, 4, 14, 6, 0, tzinfo=timezone.utc), "1 Baishakh 2082 BS"),
        (datetime(2026, 11, 7, 6, 0, tzinfo=timezone.utc), "21 Kartik 2083 BS"),
    ],
)
def test_bikram_sambat_anchor_dates(utc: datetime, expected: str) -> None:
    assert bikram_sambat_label(nepal_now(utc)).startswith(expected)


def test_nepal_day_rolls_over_at_1815_utc() -> None:
    before = nepal_now(datetime(2026, 11, 6, 18, 14, tzinfo=timezone.utc))
    after = nepal_now(datetime(2026, 11, 6, 18, 15, tzinfo=timezone.utc))
    assert (before.hour, before.minute) == (23, 59)
    assert (after.day, after.hour, after.minute) == (7, 0, 0)
    assert bikram_sambat_label(before).startswith("20 Kartik 2083")
    assert bikram_sambat_label(after).startswith("21 Kartik 2083")


def test_label_includes_devanagari() -> None:
    label = bikram_sambat_label(nepal_now(datetime(2026, 11, 7, 6, 0, tzinfo=timezone.utc)))
    assert "२०८३ कार्तिक २१" in label and "शनिबार" in label


def test_out_of_range_date_degrades_to_none() -> None:
    assert bikram_sambat_label(datetime(2150, 1, 1)) is None


def test_identity_layer_grounds_nepal_time_and_bs_date() -> None:
    layer = assembly._product_identity_layer()
    assert "Nepal Time (NPT, UTC+05:45)" in layer
    assert "Bikram Sambat" in layer and " BS (" in layer


def test_identity_layer_survives_missing_bs_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(assembly, "bikram_sambat_label", lambda _moment: None)
    layer = assembly._product_identity_layer()
    assert "Nepal Time (NPT, UTC+05:45)" in layer
    assert "Bikram Sambat" not in layer


def _service() -> ConversationService:
    return ConversationService(Settings(HINAA_PROVIDER_MODE="mock", _env_file=None))


def _request(**extra: object) -> TurnRequest:
    return TurnRequest(sessionId="hist", text="hi", companionId="hinaa", language="en-US", providerMode="mock", **extra)


def test_omitted_history_falls_back_to_stored_turns(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service()
    monkeypatch.setattr(service, "_resolve_session_history", lambda *_a, **_k: [("user", "stored")])
    assert service._turn_history(_request()) == [("user", "stored")]


def test_empty_history_is_authoritative(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regenerating or editing the first message sends []; old stored turns must not come back.
    service = _service()
    monkeypatch.setattr(service, "_resolve_session_history", lambda *_a, **_k: [("user", "stale")])
    assert service._turn_history(_request(history=[])) == []


def test_sent_history_is_used_verbatim() -> None:
    history = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}, {"role": "user"}]
    assert _service()._turn_history(_request(history=history)) == [("user", "a"), ("assistant", "b")]
