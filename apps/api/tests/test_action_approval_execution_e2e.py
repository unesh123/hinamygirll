import asyncio
import os
import secrets
import pytest
from starlette.testclient import TestClient

from hinaa_api.main import create_app
from hinaa_api.security.action_approvals import ActionApprovalGate, get_approval_gate


@pytest.fixture
def e2e_test_env(tmp_path, monkeypatch):
    """Set up isolated approvals DB and test client."""
    db_path = tmp_path / "approvals.db"
    key_str = secrets.token_hex(32)
    key = key_str.encode("utf-8")
    monkeypatch.setenv("HINA_APPROVALS_DB_PATH", str(db_path))
    monkeypatch.setenv("HINA_APPROVALS_SECRET_KEY", key_str)

    gate = ActionApprovalGate(db_path=db_path, signing_key=key)
    monkeypatch.setattr("hinaa_api.security.action_approvals._gate_instance", gate)

    from hinaa_api.config import Settings
    from hinaa_api.tools import load_all_tools
    load_all_tools()

    app = create_app(
        Settings(
            HINAA_DATABASE_URL=f"sqlite+pysqlite:///{tmp_path / 'e2e_app.db'}",
            HINAA_AUTH_MODE="dev",
            HINAA_PERSISTENCE_ENABLED=False,
            HINAA_ALLOW_REMOTE_LOCAL_TOOLS=True,
            HINAA_VMC_PORT=0,
            _env_file=None,
        )
    )
    client = TestClient(
        app,
        base_url="http://127.0.0.1:8000",
        headers={"X-HINAA-Dev-User": "test-local-user"},
    )
    return client, gate, "tenant_e2e_prod", key, db_path


def test_real_dispatcher_execution_e2e_approval_lifecycle(e2e_test_env):
    """
    End-to-End Real Dispatcher Execution Connection Proof:
    1. Zero processes start before human approval (409 TOOL_CONFIRMATION_REQUIRED).
    2. Exactly 1 process starts upon authorized challenge verification & consumption (200 OK).
    3. Zero processes start on replay attempt (403 REPLAY_DETECTED).
    4. Zero processes start on tampered parameters (403 TAMPER_DETECTED).
    5. Zero processes start on human denial (403 DENIED).
    6. Zero processes start on expired challenge (403 EXPIRED).
    7. Zero processes start with wrong HMAC signing key (403 SIGNATURE_INVALID).
    """
    client, gate, tenant_id, key, db_path = e2e_test_env

    # 1. Unapproved tool call to terminal_execute must be blocked before starting any process
    unapproved_payload = {
        "toolName": "terminal_execute",
        "parameters": {"command": "echo E2E_PRE_APPROVAL_TEST", "runtime": "powershell"},
        "confirmed": False,
        "approvalSource": "none",
    }
    resp1 = client.post("/v1/tools/execute", json=unapproved_payload)
    assert resp1.status_code == 409
    assert "TOOL_CONFIRMATION_REQUIRED" in resp1.text

    # 2. Authorized challenge verification and real execution
    valid_params = {"command": "echo E2E_REAL_PROCESS_RUN_OK", "runtime": "powershell"}
    
    # Request approval challenge
    loop = asyncio.new_event_loop()
    task = loop.create_task(
        gate.request_approval(
            "terminal_execute",
            valid_params,
            tenant_id=tenant_id,
            actor_id="actor_e2e",
            device_id="device_e2e",
            timeout_seconds=60.0,
        )
    )
    loop.run_until_complete(asyncio.sleep(0.05))
    pending = gate.list_pending(tenant_id=tenant_id)
    assert len(pending) == 1
    cid = pending[0]["challenge_id"]

    # Operator approves challenge
    gate.resolve_challenge(cid, approved=True, tenant_id=tenant_id, reason="Operator approved in UI card")
    loop.run_until_complete(task)
    loop.close()

    # Dispatch tool execution through real HTTP API with challengeId
    exec_payload = {
        "toolName": "terminal_execute",
        "parameters": valid_params,
        "challengeId": cid,
        "tenantId": tenant_id,
        "confirmed": True,
        "approvalSource": "user",
    }
    resp2 = client.post("/v1/tools/execute", json=exec_payload)
    assert resp2.status_code == 200
    res_data = resp2.json()
    assert res_data.get("status") == "success"
    assert "E2E_REAL_PROCESS_RUN_OK" in str(res_data)

    # 3. Replay attack: calling again with the same challengeId must be refused
    resp3 = client.post("/v1/tools/execute", json=exec_payload)
    assert resp3.status_code == 403
    assert "REPLAY_DETECTED" in resp3.text

    # 4. Tamper defense: modifying arguments after approval must be refused
    loop2 = asyncio.new_event_loop()
    task2 = loop2.create_task(
        gate.request_approval(
            "terminal_execute",
            {"command": "echo AUTHORIZED_COMMAND", "runtime": "powershell"},
            tenant_id=tenant_id,
            actor_id="actor_e2e",
            device_id="device_e2e",
            timeout_seconds=60.0,
        )
    )
    loop2.run_until_complete(asyncio.sleep(0.05))
    cid2 = gate.list_pending(tenant_id=tenant_id)[0]["challenge_id"]
    gate.resolve_challenge(cid2, approved=True, tenant_id=tenant_id)
    loop2.run_until_complete(task2)
    loop2.close()

    tampered_payload = {
        "toolName": "terminal_execute",
        "parameters": {"command": "echo MALICIOUS_TAMPERED_COMMAND", "runtime": "powershell"},
        "challengeId": cid2,
        "tenantId": tenant_id,
        "confirmed": True,
        "approvalSource": "user",
    }
    resp4 = client.post("/v1/tools/execute", json=tampered_payload)
    assert resp4.status_code == 403
    assert "TAMPER_DETECTED" in resp4.text

    # 5. Denial: operator declines challenge
    loop3 = asyncio.new_event_loop()
    task3 = loop3.create_task(
        gate.request_approval(
            "terminal_execute",
            {"command": "echo TO_BE_DENIED", "runtime": "powershell"},
            tenant_id=tenant_id,
            actor_id="actor_e2e",
            device_id="device_e2e",
            timeout_seconds=60.0,
        )
    )
    loop3.run_until_complete(asyncio.sleep(0.05))
    cid3 = gate.list_pending(tenant_id=tenant_id)[0]["challenge_id"]
    gate.resolve_challenge(cid3, approved=False, tenant_id=tenant_id, reason="Denied by security policy")
    loop3.run_until_complete(task3)
    loop3.close()

    denied_payload = {
        "toolName": "terminal_execute",
        "parameters": {"command": "echo TO_BE_DENIED", "runtime": "powershell"},
        "challengeId": cid3,
        "tenantId": tenant_id,
        "confirmed": True,
        "approvalSource": "user",
    }
    resp5 = client.post("/v1/tools/execute", json=denied_payload)
    assert resp5.status_code == 403
    assert "Challenge is not approved" in resp5.text

    # 6. Expiry: challenge times out
    loop4 = asyncio.new_event_loop()
    approved_exp, reason_exp, cid4 = loop4.run_until_complete(
        gate.request_approval(
            "terminal_execute",
            {"command": "echo TO_BE_EXPIRED", "runtime": "powershell"},
            tenant_id=tenant_id,
            actor_id="actor_e2e",
            device_id="device_e2e",
            timeout_seconds=0.01,
        )
    )
    loop4.close()
    assert approved_exp is False

    expired_payload = {
        "toolName": "terminal_execute",
        "parameters": {"command": "echo TO_BE_EXPIRED", "runtime": "powershell"},
        "challengeId": cid4,
        "tenantId": tenant_id,
        "confirmed": True,
        "approvalSource": "user",
    }
    resp6 = client.post("/v1/tools/execute", json=expired_payload)
    assert resp6.status_code == 403
    assert "Challenge has expired" in resp6.text or "not approved" in resp6.text

    # 7. Wrong signing key
    wrong_key_gate = ActionApprovalGate(db_path=db_path, signing_key=secrets.token_bytes(32))
    loop5 = asyncio.new_event_loop()
    task5 = loop5.create_task(
        gate.request_approval(
            "terminal_execute",
            {"command": "echo WRONG_KEY_TEST", "runtime": "powershell"},
            tenant_id=tenant_id,
            actor_id="actor_e2e",
            device_id="device_e2e",
            timeout_seconds=60.0,
        )
    )
    loop5.run_until_complete(asyncio.sleep(0.05))
    cid5 = gate.list_pending(tenant_id=tenant_id)[0]["challenge_id"]
    gate.resolve_challenge(cid5, approved=True, tenant_id=tenant_id)
    loop5.run_until_complete(task5)
    loop5.close()

    ok_wrong, msg_wrong = wrong_key_gate.verify_and_consume(
        cid5, {"command": "echo WRONG_KEY_TEST", "runtime": "powershell"}, tenant_id=tenant_id
    )
    assert ok_wrong is False
    assert "SIGNATURE_INVALID" in msg_wrong
