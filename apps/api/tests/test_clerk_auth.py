from __future__ import annotations

from time import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.main import create_app


def _keys() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


def _settings(tmp_path, public_key: str) -> Settings:
    return Settings(
        HINAA_PROVIDER_MODE="mock",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_AUTH_MODE="clerk",
        HINAA_PERSISTENCE_ENABLED=True,
        HINAA_LOCAL_WORKSPACE_DIR=tmp_path,
        CLERK_JWT_KEY=public_key,
        CLERK_AUTHORIZED_PARTIES="https://hinaa.example",
        HINAA_VMC_PORT=0,
        _env_file=None,
    )


def _token(private_key: str, *, subject: str = "user_hinaa", azp: str = "https://hinaa.example") -> str:
    now = int(time())
    return jwt.encode(
        {
            "sub": subject,
            "sid": "sess_hinaa",
            "azp": azp,
            "iat": now,
            "nbf": now - 1,
            "exp": now + 60,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "hinaa-test"},
    )


def test_clerk_token_protects_and_unlocks_api(tmp_path) -> None:
    private_key, public_key = _keys()
    with TestClient(create_app(_settings(tmp_path, public_key))) as client:
        missing = client.get("/v1/conversations")
        accepted = client.get(
            "/v1/conversations",
            headers={"Authorization": f"Bearer {_token(private_key)}"},
        )

    assert missing.status_code == 401
    assert accepted.status_code == 200


def test_clerk_rejects_wrong_authorized_party(tmp_path) -> None:
    private_key, public_key = _keys()
    with TestClient(create_app(_settings(tmp_path, public_key))) as client:
        response = client.get(
            "/v1/conversations",
            headers={
                "Authorization": f"Bearer {_token(private_key, azp='https://attacker.example')}"
            },
        )

    assert response.status_code == 401
import pytest
from starlette.websockets import WebSocketDisconnect

@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/capabilities"), ("get", "/v1/vmc/status"),
    ("get", "/docs"), ("get", "/health"),
    ("post", "/api/v1/assets"), ("post", "/v1/vmc/test-signal"),
])
def test_private_runtime_guards_routes_without_dependencies(tmp_path, method, path):
    _, public_key = _keys()
    with TestClient(create_app(_settings(tmp_path, public_key))) as client:
        assert getattr(client, method)(path).status_code == 401
        assert client.get("/health/live").json()["service"] == "hinaa-api"


def test_private_runtime_accepts_only_owner_and_issues_voice_ticket(tmp_path):
    private_key, public_key = _keys()
    settings = _settings(tmp_path, public_key)
    settings.hinaa_allowed_user_ids = "user_owner"
    with TestClient(create_app(settings)) as client:
        stranger = {"Authorization": f"Bearer {_token(private_key, subject='user_other')}"}
        owner = {"Authorization": f"Bearer {_token(private_key, subject='user_owner')}"}
        assert client.get("/v1/vmc/status", headers=stranger).status_code == 403
        assert client.get("/v1/vmc/status", headers=owner).status_code == 200
        ticket = client.post("/v1/realtime/ticket", headers=owner).json()["ticket"]
        hello = {"type":"session.hello", "protocolVersion":"1.0", "sessionId":"private-test", "companionId":"hinaa", "providerMode":"mock", "generation":1, "language":"mixed", "languageMode":"fixed-hi-IN", "calibration":"soft", "authTicket":ticket}
        with client.websocket_connect("/v1/realtime") as socket:
            socket.send_json(hello)
            assert socket.receive_json()["type"] == "session.ready"
        with client.websocket_connect("/v1/realtime") as socket:
            socket.send_json(hello)
            with pytest.raises(WebSocketDisconnect) as closed:
                socket.receive_json()
            assert closed.value.code == 4401


def test_private_vmc_rejects_anonymous_and_accepts_single_use_ticket(tmp_path):
    private_key, public_key = _keys()
    with TestClient(create_app(_settings(tmp_path, public_key))) as client:
        with client.websocket_connect("/ws/vmc") as socket:
            socket.send_json({"authTicket":"invalid-ticket"})
            with pytest.raises(WebSocketDisconnect) as closed:
                socket.receive_json()
            assert closed.value.code == 4401
        headers = {"Authorization": f"Bearer {_token(private_key)}"}
        ticket = client.post("/v1/realtime/ticket", headers=headers).json()["ticket"]
        with client.websocket_connect("/ws/vmc") as socket:
            socket.send_json({"authTicket":ticket})
            assert "tracking" in socket.receive_json()

def test_owner_session_check_and_remote_terminal_gate(tmp_path):
    private_key, public_key = _keys()
    settings = _settings(tmp_path, public_key)
    settings.allow_remote_local_tools = False
    with TestClient(create_app(settings)) as client:
        headers = {"Authorization": f"Bearer {_token(private_key)}", "Host":"hinaa-workspace.vercel.app"}
        response = client.get("/api/v1/auth/session", headers=headers)
        assert response.json() == {"authenticated":True,"authMode":"clerk"}
        result = client.post("/api/v1/terminal/execute", json={"command":"echo must-not-run"}, headers=headers)
        assert result.status_code == 403
        assert result.json()["code"] == "LOCAL_TOOL_NOT_PERMITTED"
