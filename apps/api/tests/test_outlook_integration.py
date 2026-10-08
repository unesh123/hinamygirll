from __future__ import annotations
import time
import httpx
import pytest
from hinaa_api.integrations import outlook_graph as graph_module
from hinaa_api.integrations.saas_bridge import SaaSBridgedManager
from hinaa_api.tools import email
from hinaa_api.integrations import desktop_bridge_auth

@pytest.fixture(autouse=True)
def no_mail_credentials(monkeypatch, tmp_path):
    for key in ("OUTLOOK_ACCESS_TOKEN", "SMTP_USER", "SMTP_PASSWORD", "OUTLOOK_EMAIL", "OUTLOOK_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(graph_module, "CACHE_PATH", tmp_path / "credentials.dpapi")

@pytest.mark.asyncio
async def test_no_fake_delivery_or_connection():
    result = await email.execute_email_handler({"recipient": "student@example.org", "subject": "Test", "body": "A draft", "send_immediately": True})
    assert result["status"] == "unavailable"
    assert "nothing was sent" in result["message"]
    status = next(s for s in SaaSBridgedManager().get_all_statuses() if s.service_id == "outlook")
    assert not status.connected
    assert SaaSBridgedManager().get_todays_agenda() == []

@pytest.mark.asyncio
async def test_graph_draft_uses_real_message_id(monkeypatch):
    monkeypatch.setenv("OUTLOOK_ACCESS_TOKEN", "test-only")
    async def draft(*args):
        return {"id": "draft-123", "webLink": "https://outlook.office.com/mail/"}
    monkeypatch.setattr(email.outlook_graph, "draft", draft)
    result = await email.execute_email_handler({"recipient": "student@example.org", "subject": "Test", "body": "Draft"})
    assert result["id"] == "draft-123"
    assert result["provider"] == "microsoft-graph"

@pytest.mark.asyncio
async def test_graph_permission_error_is_not_success(monkeypatch):
    monkeypatch.setenv("OUTLOOK_ACCESS_TOKEN", "test-only")
    async def denied(*args):
        raise graph_module.OutlookError("Microsoft denied the mailbox permission.")
    monkeypatch.setattr(email.outlook_graph, "draft", denied)
    result = await email.execute_email_handler({"recipient": "student@example.org", "subject": "Test", "body": "Draft"})
    assert result["status"] == "failed"

@pytest.mark.asyncio
async def test_refresh_rotation_saved_and_serialized(monkeypatch):
    credentials = {"client_id": "test-client", "tenant": "organizations", "scope": "offline_access", "refresh_token": "old", "expires_at": 0}
    monkeypatch.setattr(graph_module, "load_credentials", lambda: dict(credentials))
    saved = []
    monkeypatch.setattr(graph_module, "save_credentials", lambda value: saved.append(value.copy()))
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, data):
            assert data["refresh_token"] == "old"
            assert url.startswith("https://login.microsoftonline.com/organizations/")
            return httpx.Response(200, json={"access_token": "new-access", "refresh_token": "rotated", "expires_in": 3600})
    monkeypatch.setattr(graph_module.httpx, "AsyncClient", lambda **kwargs: Client())
    assert await graph_module.OutlookGraph().token() == "new-access"
    assert saved[0]["refresh_token"] == "rotated"
    assert saved[0]["expires_at"] > time.time()

@pytest.mark.asyncio
async def test_graph_read_limit_and_message_id_encoding(monkeypatch):
    calls = []
    graph = graph_module.OutlookGraph()
    async def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"value": []}
    monkeypatch.setattr(graph, "request", request)
    await graph.inbox(1000)
    await graph.message("message/?id")
    assert calls[0][2]["params"]["$top"] == 25
    assert calls[1][1] == "/me/messages/message%2F%3Fid"

@pytest.mark.skipif(__import__("os").name != "nt", reason="DPAPI is Windows-specific")
def test_credentials_encrypted_and_readable():
    graph_module.save_credentials({"access_token": "test-secret", "refresh_token": "test-refresh"})
    assert b"test-secret" not in graph_module.CACHE_PATH.read_bytes()
    assert graph_module.load_credentials()["refresh_token"] == "test-refresh"

def test_bridge_pairing_requires_token(monkeypatch, tmp_path):
    monkeypatch.delenv("HINAA_DESKTOP_BRIDGE_TOKEN", raising=False)
    monkeypatch.setattr(desktop_bridge_auth, "TOKEN_PATH", tmp_path / "bridge.token")
    assert desktop_bridge_auth.bridge_token() == ""
    token = desktop_bridge_auth.bridge_token(create=True)
    assert len(token) >= 32
    assert desktop_bridge_auth.bridge_token() == token
    assert desktop_bridge_auth.authorized("Bearer " + token, token)
    assert not desktop_bridge_auth.authorized("Bearer wrong", token)
    assert not desktop_bridge_auth.authorized(None, token)


@pytest.mark.asyncio
async def test_graph_send_acceptance_is_not_delivery(monkeypatch):
    graph = graph_module.OutlookGraph()
    async def accepted(*args, **kwargs): return {}
    monkeypatch.setattr(graph, "request", accepted)
    result = await graph.send("student@example.org", "Subject", "Draft")
    assert result["status"] == "accepted"
    assert "not yet verified" in result["message"]

def test_terminal_capability_distinguishes_remote_and_local(monkeypatch):
    from fastapi.testclient import TestClient
    from hinaa_api.main import app
    from hinaa_api.tools import terminal_hands
    monkeypatch.setattr(terminal_hands, "_wsl_distributions", lambda: ["kali-linux"])
    with TestClient(app) as client:
        monkeypatch.setattr(app.state.settings, "allow_remote_local_tools", False)
        local = client.get("/api/v1/terminal/status", headers={"host": "127.0.0.1"})
        remote = client.get("/api/v1/terminal/status", headers={"host": "hinaa-workspace.vercel.app"})
        assert local.json()["execution_allowed"] is True
        assert remote.json()["execution_allowed"] is False
        assert remote.json()["wsl_distributions"] == ["kali-linux"]


@pytest.mark.skipif(__import__("os").name != "nt", reason="Desktop bridge is Windows-specific")
def test_daemon_rejects_unpaired_and_browser_requests(monkeypatch):
    import importlib.util
    from pathlib import Path
    from http.server import HTTPServer
    import threading
    monkeypatch.setenv("HINAA_DESKTOP_BRIDGE_TOKEN", "test-pairing-token-" + "x" * 40)
    path = Path(__file__).resolve().parents[3] / "scripts" / "hinaa_desktop_daemon.py"
    spec = importlib.util.spec_from_file_location("test_desktop_daemon", path)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    # No screen capture, mouse movement, or native desktop calls in this test.
    monkeypatch.setattr(daemon.WindowsDesktopActuator, "capture_screenshot", lambda: pytest.fail("Unauthorized actuator executed"))
    server = HTTPServer(("127.0.0.1", 0), daemon.DaemonRequestHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with httpx.Client(trust_env=False) as client:
            denied = client.post(base + "/api/action", json={"action": "screenshot"})
            assert denied.status_code == 401
            assert "access-control-allow-origin" not in denied.headers
            browser = client.post(base + "/api/action", headers={"Authorization": "Bearer " + daemon.BRIDGE_TOKEN, "Origin": "https://example.org"}, json={"action": "screenshot"})
            assert browser.status_code == 401
            import socket
            with socket.create_connection(("127.0.0.1", server.server_port), timeout=3) as connection:
                request = f"POST /api/action HTTP/1.0\r\nAuthorization: Bearer {daemon.BRIDGE_TOKEN}\r\nContent-Length: 65537\r\n\r\n"
                connection.sendall(request.encode())
                assert b"413" in connection.recv(4096)
    finally:
        server.shutdown()
        worker.join(timeout=2)
        server.server_close()


@pytest.mark.asyncio
async def test_editor_launch_has_real_errors_and_workspace(monkeypatch):
    import subprocess
    from hinaa_api.tools import computer_operator as operator
    cls = operator.NativeComputerOperator
    monkeypatch.setattr(cls, "emit_motion_event", lambda *args: None)
    monkeypatch.setattr(cls, "observe", lambda: operator.GeneralPerception(active_window_title="Test window"))
    monkeypatch.setattr(operator.platform, "system", lambda: "Windows")
    monkeypatch.setenv("HINAA_PREFERRED_EDITOR", "antigravity")
    calls = []
    def launch(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0)
    monkeypatch.setattr(operator.subprocess, "run", launch)
    result = await cls.open_application("my editor")
    assert result.success and not result.verified
    assert "Google.Antigravity" in calls[0][0][-1]
    assert "HINAMYGIRL" in calls[0][0][-1]
    assert calls[0][1]["check"] is True
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "test-launcher")
    monkeypatch.setattr(operator.subprocess, "run", fail)
    failed = await cls.open_application("my editor")
    assert not failed.success and not failed.verified


def test_mail_read_routes_only_when_requested():
    from hinaa_api.tools.intent_gate import gate_tool_requests
    from hinaa_api.models import ToolRequest
    kept, dropped, _ = gate_tool_requests("Check my Outlook emails", [])
    assert len(kept) == 1 and kept[0].toolName == "read_outlook"
    assert kept[0].parameters["limit"] == 10
    kept, dropped, _ = gate_tool_requests("Tell me about astronomy", [ToolRequest(toolName="read_outlook", parameters={"limit": 10}, reason="test")])
    assert kept == [] and dropped == ["read_outlook"]
