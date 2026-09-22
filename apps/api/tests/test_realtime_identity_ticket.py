"""Who the voice socket thinks it is talking to.

A browser cannot set an Authorization header on a WebSocket handshake, so the
realtime route can never read the session the way the HTTP routes do. Identity
reaches it through a single-use ticket bought over an authorized HTTP request
and spent in the socket's first frame.
"""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from hinaa_api import realtime_tickets
from hinaa_api.realtime import ClientHello, RealtimeGateway


def _hello(**overrides) -> ClientHello:
    payload = {
        "type": "session.hello",
        "protocolVersion": "1.0",
        "sessionId": "live-ticket-test",
    }
    payload.update(overrides)
    return ClientHello.model_validate(payload)


def test_a_hello_without_a_ticket_keeps_whatever_the_route_resolved():
    assert RealtimeGateway._resolve_identity(_hello(), "local-owner") == "local-owner"
    assert RealtimeGateway._resolve_identity(_hello(), None) is None


def test_a_ticket_names_its_owner_exactly_once():
    ticket = realtime_tickets.issue("owner-a")
    assert RealtimeGateway._resolve_identity(_hello(authTicket=ticket), None) == "owner-a"
    # A replay must not hand the same socket a different owner either.
    assert RealtimeGateway._resolve_identity(_hello(authTicket=ticket), "owner-b") is None


def test_an_expired_ticket_cannot_borrow_the_handshake_identity(monkeypatch):
    monkeypatch.setattr(realtime_tickets, "TICKET_TTL_SECONDS", -1)
    ticket = realtime_tickets.issue("owner-a")
    assert RealtimeGateway._resolve_identity(_hello(authTicket=ticket), "stranger") is None


def test_a_ticket_request_without_identity_is_refused(client: TestClient):
    # The shared fixture names itself the way the frontend does, so anonymity
    # has to be asked for by blanking that header.
    response = client.post(
        "/v1/realtime/ticket", headers={"X-HINAA-Dev-User": ""}
    )
    assert response.status_code == 401


def test_the_ticket_is_bound_to_the_caller_not_to_anyone(
    client: TestClient, monkeypatch
):
    issued: list[str] = []
    monkeypatch.setattr(
        realtime_tickets,
        "issue",
        lambda user_id: (issued.append(user_id), "t" * 32)[1],
    )
    response = client.post(
        "/v1/realtime/ticket", headers={"X-HINAA-Dev-User": "voice-owner"}
    )
    assert response.status_code == 200
    expected = client.app.state.memory_service.ensure_user("voice-owner").id
    assert issued == [expected]


def test_the_socket_is_owned_by_whoever_bought_the_ticket(
    client: TestClient, caplog
):
    response = client.post(
        "/v1/realtime/ticket", headers={"X-HINAA-Dev-User": "voice-owner"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["expiresInSeconds"] == realtime_tickets.TICKET_TTL_SECONDS

    with caplog.at_level(logging.INFO, logger="hinaa.realtime"):
        with client.websocket_connect("/v1/realtime") as socket:
            socket.send_json(
                {
                    "type": "session.hello",
                    "protocolVersion": "1.0",
                    "sessionId": "live-ticket-socket",
                    "authTicket": body["ticket"],
                }
            )
            socket.receive_json()

    assert "identified=True" in caplog.text
