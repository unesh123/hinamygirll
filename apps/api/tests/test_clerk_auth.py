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
