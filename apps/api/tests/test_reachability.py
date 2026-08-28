"""Reachability probes must tell the truth about ephemeral tunnels.

The bug these tests pin: a CX gateway on a dead ``trycloudflare.com`` quick
tunnel kept reporting "configured and ready" because the health check only
looked at environment variables. The user selected that brain, saw a green
Ready badge, and every single turn failed with PROVIDER_UNAVAILABLE.
"""

from __future__ import annotations

import asyncio
import socket

import pytest

from hinaa_api.reachability import (
    ProbeOutcome,
    is_ephemeral_tunnel,
    probe_gateway,
    reset_probe_cache,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_probe_cache()
    yield
    reset_probe_cache()


class TestEphemeralTunnelDetection:
    @pytest.mark.parametrize(
        "url",
        [
            "https://revenue-mystery-pharmacy-springer.trycloudflare.com",
            "https://foo.trycloudflare.com/v1",
            "http://bar.ngrok-free.app",
            "https://baz.ngrok.io",
            "https://qux.loca.lt",
            "trycloudflare.com",
        ],
    )
    def test_flags_disposable_tunnel_hosts(self, url: str) -> None:
        assert is_ephemeral_tunnel(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://api.mwapi.dev",
            "https://api.openai.com/v1",
            "http://127.0.0.1:8000",
            "https://api.hcnsec.cn/v1",
        ],
    )
    def test_does_not_flag_stable_endpoints(self, url: str) -> None:
        assert is_ephemeral_tunnel(url) is False

    @pytest.mark.parametrize("url", [None, "", "   ", "not a url at all ::::"])
    def test_handles_missing_or_malformed_urls(self, url: str | None) -> None:
        assert is_ephemeral_tunnel(url) is False


class TestProbeGateway:
    def test_reports_unreachable_without_a_url(self) -> None:
        outcome = asyncio.run(probe_gateway(None, use_cache=False))
        assert outcome.reachable is False
        assert outcome.reason == "no_host"

    def test_reports_unreachable_when_dns_does_not_resolve(self, monkeypatch) -> None:
        async def fail_dns(*_args, **_kwargs):
            raise socket.gaierror("Name or service not known")

        monkeypatch.setattr(asyncio, "open_connection", fail_dns)
        outcome = asyncio.run(
            probe_gateway("https://dead-tunnel.trycloudflare.com", use_cache=False)
        )
        assert outcome.reachable is False
        assert outcome.reason == "dns_unresolved"
        assert "expired" in outcome.detail

    def test_reports_unreachable_on_timeout(self, monkeypatch) -> None:
        async def hang(*_args, **_kwargs):
            await asyncio.sleep(10)

        monkeypatch.setattr(asyncio, "open_connection", hang)
        outcome = asyncio.run(
            probe_gateway("https://slow.trycloudflare.com", timeout=0.05, use_cache=False)
        )
        assert outcome.reachable is False
        assert outcome.reason == "timeout"

    def test_reports_unreachable_when_connection_refused(self, monkeypatch) -> None:
        async def refuse(*_args, **_kwargs):
            raise ConnectionRefusedError("refused")

        monkeypatch.setattr(asyncio, "open_connection", refuse)
        outcome = asyncio.run(probe_gateway("https://example.invalid", use_cache=False))
        assert outcome.reachable is False
        assert outcome.reason == "refused"

    def test_reports_reachable_when_connection_opens(self, monkeypatch) -> None:
        class _Writer:
            def close(self) -> None:
                pass

            async def wait_closed(self) -> None:
                pass

        async def connect(*_args, **_kwargs):
            return object(), _Writer()

        monkeypatch.setattr(asyncio, "open_connection", connect)
        outcome = asyncio.run(probe_gateway("https://api.mwapi.dev", use_cache=False))
        assert outcome.reachable is True
        assert outcome.reason == "ok"

    def test_does_not_spend_provider_quota(self, monkeypatch) -> None:
        """The probe must be connection-level only — never a model request."""
        opened: list[tuple] = []

        class _Writer:
            def close(self) -> None:
                pass

            async def wait_closed(self) -> None:
                pass

        async def connect(host, port, **_kwargs):
            opened.append((host, port))
            return object(), _Writer()

        monkeypatch.setattr(asyncio, "open_connection", connect)
        asyncio.run(probe_gateway("https://api.mwapi.dev/v1", use_cache=False))
        # Exactly one TCP connection, to the host root, with no request payload.
        assert opened == [("api.mwapi.dev", 443)]

    def test_infers_port_from_scheme(self, monkeypatch) -> None:
        seen: list[int] = []

        class _Writer:
            def close(self) -> None:
                pass

            async def wait_closed(self) -> None:
                pass

        async def connect(_host, port, **_kwargs):
            seen.append(port)
            return object(), _Writer()

        monkeypatch.setattr(asyncio, "open_connection", connect)
        asyncio.run(probe_gateway("http://localhost", use_cache=False))
        asyncio.run(probe_gateway("https://localhost", use_cache=False))
        asyncio.run(probe_gateway("http://localhost:8123", use_cache=False))
        assert seen == [80, 443, 8123]


class TestProbeCaching:
    def test_caches_results_to_keep_the_endpoint_fast(self, monkeypatch) -> None:
        calls = 0

        class _Writer:
            def close(self) -> None:
                pass

            async def wait_closed(self) -> None:
                pass

        async def connect(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            return object(), _Writer()

        monkeypatch.setattr(asyncio, "open_connection", connect)

        async def run_twice():
            first = await probe_gateway("https://api.mwapi.dev")
            second = await probe_gateway("https://api.mwapi.dev")
            return first, second

        first, second = asyncio.run(run_twice())
        assert first.reachable is True
        assert second.reachable is True
        assert calls == 1, "second call should be served from cache"

    def test_cache_can_be_bypassed(self, monkeypatch) -> None:
        calls = 0

        class _Writer:
            def close(self) -> None:
                pass

            async def wait_closed(self) -> None:
                pass

        async def connect(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            return object(), _Writer()

        monkeypatch.setattr(asyncio, "open_connection", connect)

        async def run_twice():
            await probe_gateway("https://api.mwapi.dev", use_cache=False)
            await probe_gateway("https://api.mwapi.dev", use_cache=False)

        asyncio.run(run_twice())
        assert calls == 2

    def test_reset_clears_cached_results(self, monkeypatch) -> None:
        calls = 0

        class _Writer:
            def close(self) -> None:
                pass

            async def wait_closed(self) -> None:
                pass

        async def connect(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            return object(), _Writer()

        monkeypatch.setattr(asyncio, "open_connection", connect)

        async def run():
            await probe_gateway("https://api.mwapi.dev")
            reset_probe_cache()
            await probe_gateway("https://api.mwapi.dev")

        asyncio.run(run())
        assert calls == 2


class TestProbeNeverRaises:
    def test_unexpected_errors_become_an_outcome(self, monkeypatch) -> None:
        async def explode(*_args, **_kwargs):
            raise RuntimeError("something odd")

        monkeypatch.setattr(asyncio, "open_connection", explode)
        outcome = asyncio.run(probe_gateway("https://api.mwapi.dev", use_cache=False))
        assert isinstance(outcome, ProbeOutcome)
        assert outcome.reachable is False
        assert outcome.reason == "error"
