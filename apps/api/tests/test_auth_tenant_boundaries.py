import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.main import create_app
from hinaa_api.ops.context import actor_id_var, tenant_id_var
from hinaa_api.persistence.auth import AuthContext, resolve_auth
from hinaa_api.persistence.db import get_session_factory, init_db
from hinaa_api.persistence.memory_service import MemoryService
from hinaa_api.integrations.desktop_bridge_auth import get_hina_token


class MockRequest:
    def __init__(self, headers=None, client_ip="127.0.0.1"):
        self.headers = headers or {}
        self.client = type("Client", (), {"host": client_ip})()
        self.state = type("State", (), {})()


def test_auth_context_actor_and_tenant_properties():
    """Verify actor_id and tenant_id properties on AuthContext."""
    ctx_personal = AuthContext(user_id="user_123", auth_subject="sub_123", mode="clerk")
    assert ctx_personal.actor_id == "user_123"
    assert ctx_personal.tenant_id == "user_123"

    ctx_org = AuthContext(user_id="user_123", auth_subject="sub_123", mode="clerk", org_id="org_abc")
    assert ctx_org.actor_id == "user_123"
    assert ctx_org.tenant_id == "org_abc"


def test_dev_auth_rejected_in_production(tmp_path):
    """Dev authentication mode is rejected unconditionally in production."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="production",
            auth_mode="dev",
            database_url=f"sqlite:///{tmp_path}/test.db",
            _env_file=None,
        )
    assert "Development authentication bypass cannot be enabled in production" in str(exc_info.value)


def test_dev_auth_clerk_loopback_rejected_in_production(tmp_path):
    """Even in clerk mode, loopback dev bypass is forbidden in production."""
    db_url = f"sqlite:///{tmp_path}/test.db"
    settings = Settings(
        environment="production",
        auth_mode="clerk",
        clerk_jwt_key="dummy_pem",
        database_url=db_url,
        _env_file=None,
    )
    factory = init_db(settings)
    memory = MemoryService(factory)
    req = MockRequest(headers={"X-HINAA-Dev-User": "test-dev-user", "host": "127.0.0.1:8000"})

    with pytest.raises(HinaaError) as exc_info:
        resolve_auth(req, settings, memory, x_hinaa_dev_user="test-dev-user")
    assert exc_info.value.status_code in (401, 503)


def test_resolve_auth_binds_actor_and_tenant_context(tmp_path):
    """Verify resolve_auth binds contextvars for actor_id and tenant_id."""
    db_url = f"sqlite:///{tmp_path}/test.db"
    settings = Settings(
        environment="development",
        auth_mode="dev",
        database_url=db_url,
        _env_file=None,
    )
    factory = init_db(settings)
    memory = MemoryService(factory)
    req = MockRequest(headers={"X-HINAA-Dev-User": "alice", "host": "127.0.0.1:8000"})

    ctx = resolve_auth(req, settings, memory, x_hinaa_dev_user="alice")
    assert ctx.user_id
    assert actor_id_var.get() == ctx.actor_id
    assert tenant_id_var.get() == ctx.tenant_id


def test_websocket_rejects_evil_origin(tmp_path):
    """WebSocket connection with disallowed origin is rejected with 4403."""
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/test.db", _env_file=None))
    token = get_hina_token(create=True)
    client = TestClient(app)

    # With evil origin header
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/vmc?token={token}", headers={"origin": "http://evil-attacker.com"}):
            pass
    assert exc.value.code == 4403


def test_websocket_accepts_valid_origin(tmp_path):
    """WebSocket connection with valid origin header is accepted."""
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/test.db", _env_file=None))
    token = get_hina_token(create=True)
    client = TestClient(app)

    with client.websocket_connect(f"/ws/vmc?token={token}", headers={"origin": "http://localhost:5173"}):
        pass
