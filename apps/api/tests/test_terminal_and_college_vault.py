from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hinaa_api.main import app
from hinaa_api.college.vault import StudentRegistrationRequest, college_vault_service
from hinaa_api.tools.terminal_hands import execute_terminal_hands, TerminalExecuteParams
from hinaa_api.tools.email import execute_email_handler, EmailDraftParams
from hinaa_api.tools.registry import registry


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.asyncio
async def test_terminal_hands_guardrail():
    """Ensure dangerous commands are blocked by security policy."""
    bad_res = await execute_terminal_hands({"command": "format C: /fs:ntfs"})
    assert bad_res["status"] == "rejected"
    assert "Security Guardrail" in bad_res["error"]

    bad_rm = await execute_terminal_hands({"command": "rmdir /s /q c:"})
    assert bad_rm["status"] == "rejected"


@pytest.mark.asyncio
async def test_terminal_hands_safe_execution():
    """Ensure safe commands execute and return stdout."""
    res = await execute_terminal_hands({"command": "python --version"})
    assert res["status"] == "success"
    assert "Python" in res["stdout"] or "Python" in res["stderr"]
    assert res["exitCode"] == 0


def test_terminal_hands_registered_in_tool_registry():
    """Ensure terminal_hands is registered in tool registry."""
    tool = registry.get_tool("terminal_hands")
    assert tool is not None
    assert tool.name == "terminal_hands"
    assert "Terminal" in tool.display_name


def test_college_vault_service():
    """Ensure student registration, verification, and VIP resource listing works."""
    req = StudentRegistrationRequest(
        student_id="TEST-ENG-9901",
        full_name="Aarav Sharma",
        email="aarav.sharma@college.edu.np",
        department="Computer Science & Engineering",
        semester=6,
        role="student",
    )
    reg = college_vault_service.register_student(req)
    assert reg["status"] == "registered"
    assert reg["student"]["student_id"] == "TEST-ENG-9901"
    assert reg["student"]["vip_access_granted"] is True

    # Verification
    verified = college_vault_service.verify_student("TEST-ENG-9901")
    assert verified is not None
    assert verified["full_name"] == "Aarav Sharma"

    # VIP resources
    resources = college_vault_service.list_vip_resources()
    assert len(resources) >= 4
    cyber_res = college_vault_service.list_vip_resources(category="cybersecurity")
    assert len(cyber_res) >= 1
    assert "Ethical Hacking" in cyber_res[0]["title"]

    # Admin stats
    stats = college_vault_service.get_admin_dashboard_stats()
    assert stats["total_enrolled_students"] >= 1
    assert stats["resources_in_vault"] >= 4


def test_college_endpoints_via_api(client: TestClient):
    """Test REST API routes for college portal and VIP vault."""
    # Register
    res = client.post(
        "/v1/college/students/register",
        json={
            "student_id": "TEST-API-101",
            "full_name": "Priya Adhikari",
            "email": "priya.a@college.edu.np",
            "department=" : "Artificial Intelligence",
            "department": "Artificial Intelligence",
            "semester": 4,
            "role": "student",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["student"]["student_id"] == "TEST-API-101"

    # Verify
    res_get = client.get("/v1/college/students/TEST-API-101")
    assert res_get.status_code == 200
    assert res_get.json()["student"]["full_name"] == "Priya Adhikari"

    # Non-existent
    res_not_found = client.get("/v1/college/students/NON_EXISTENT_ID")
    assert res_not_found.status_code == 404

    # List resources
    res_vault = client.get("/v1/college/vault/resources")
    assert res_vault.status_code == 200
    assert "resources" in res_vault.json()

    # Admin dashboard
    res_dash = client.get("/v1/college/admin/dashboard")
    assert res_dash.status_code == 200
    assert res_dash.json()["resources_in_vault"] >= 4


@pytest.mark.asyncio
async def test_email_draft_mode():
    """Ensure Outlook email tool correctly constructs academic emails in draft mode."""
    res = await execute_email_handler({
        "recipient": "dean@college.edu.np",
        "subject": "Curriculum Modernization Proposal",
        "body": "Dear Dean, HINAA VIP Deep Vault has been successfully deployed.",
        "category": "academic_announcement",
        "send_immediately": False,
    })
    assert res["status"] == "draft_created"
    assert res["recipient"] == "dean@college.edu.np"
    assert "HINAA Academic Partner" in res["body"]


@pytest.mark.asyncio
async def test_terminal_rejects_working_directory_escape(tmp_path):
    result=await execute_terminal_hands({"command":"echo check", "cwd":"../../../../outside-hina-workspace"})
    assert result["status"] == "rejected"
    assert "workspace" in result["error"]

@pytest.mark.asyncio
async def test_terminal_preserves_timeout_and_output(monkeypatch):
    import subprocess
    from hinaa_api.tools import terminal_hands
    def expired(*args):
        raise subprocess.TimeoutExpired("test",1)
    monkeypatch.setattr(terminal_hands,"_run_command",expired)
    result=await execute_terminal_hands({"command":"echo test", "timeout_seconds":1})
    assert result["status"] == "timeout"
    assert result["timeoutSeconds"] == 1

@pytest.mark.asyncio
async def test_terminal_runtime_passes_through_api(client, monkeypatch):
    from hinaa_api import omega_router as module
    async def fake(params):
        return {"status":"success","runtime":params.runtime,"stdout":"test"}
    monkeypatch.setattr(module,"execute_terminal_hands",fake)
    response=client.post("/api/v1/terminal/execute",json={"command":"echo test","runtime":"powershell"})
    assert response.status_code == 200
    assert response.json()["runtime"] == "powershell"
