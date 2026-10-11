from __future__ import annotations

from hinaa_api.realtime_origin import choose_realtime_origin


def test_configured_origin_wins_and_is_normalised() -> None:
    result = choose_realtime_origin(
        configured="https://Api.Example.com/", host="hinaa-workspace.vercel.app", edge_request=True
    )
    assert result.origin == "api.example.com"
    assert result.source == "configured"


def test_edge_request_without_configuration_is_never_advertised_on_its_own_host() -> None:
    # Regression: the route advertised wss://<vercel-host>/v1/realtime, which cannot upgrade.
    result = choose_realtime_origin(
        configured="", host="hinaa-workspace.vercel.app", edge_request=True
    )
    assert result.origin is None
    assert result.source == "unavailable-edge"


def test_local_request_uses_its_own_host() -> None:
    result = choose_realtime_origin(configured="", host="127.0.0.1:8000", edge_request=False)
    assert result.origin == "127.0.0.1:8000"
    assert result.source == "host"


def test_no_host_and_no_configuration_is_unavailable() -> None:
    result = choose_realtime_origin(configured="", host="", edge_request=False)
    assert result.origin is None
    assert result.source == "unavailable"
