"""Local probes must not hammer a dead service on every poll.

The backend log showed "Ollama probe error: ConnectTimeout" repeating forever
while Hina sat idle, because every provider-status poll re-probed a configured
but dead local engine. These tests pin the short TTL cache that ended it.
"""
from __future__ import annotations

import time

from hinaa_api import main as app_main


def test_probe_cache_is_empty_initially() -> None:
    app_main._PROBE_CACHE.clear()
    assert app_main._probe_cached("ollama") is None


def test_probe_cache_remembers_an_answer() -> None:
    app_main._PROBE_CACHE.clear()
    app_main._probe_store("ollama", ("unavailable", "down", []))
    assert app_main._probe_cached("ollama") == ("unavailable", "down", [])


def test_probe_cache_expires_after_ttl() -> None:
    app_main._PROBE_CACHE.clear()
    app_main._PROBE_CACHE["ollama"] = (time.time() - 1000, ("stale",))
    assert app_main._probe_cached("ollama", ttl=45.0) is None


def test_ledger_response_text_picks_the_spoken_reply() -> None:
    assert app_main._ledger_response_text({"spokenText": "Hi there"}) == "Hi there"
    assert app_main._ledger_response_text({"message": "Hello"}) == "Hello"
    assert app_main._ledger_response_text({"spokenText": "   "}) is None
    assert app_main._ledger_response_text(None) is None
