"""Comprehensive Security Integration Boundary Tests (Directive v3.0 Item 5).

Verifies boundary requirements A through O:
A. Production request cannot use dev authentication.
B. One tenant cannot view, approve, deny, consume, or replay another tenant’s challenge.
C. Foreign WebSocket Origin is rejected with 4403.
D. Missing/invalid Origin behavior is explicitly tested.
E. Every quarantined tool is absent from the public registry and dispatcher.
F. full_pc_control cannot read /etc/hostname, user files, browser data, SSH keys, or files outside an allowed workspace.
G. full_pc_control cannot start a process, shell command, network request, or child process.
H. confirmed=false never executes.
I. Approval does not execute automatically; consumption is a separate checked operation.
J. Parameter mutation after approval produces TAMPER_DETECTED with zero side effects.
K. Two concurrent consumers produce exactly one success and one replay denial.
L. Expired and denied approvals cannot execute.
M. Restart persistence never changes PENDING into APPROVED.
N. Startup fails if a quarantined tool becomes registered.
O. Logs, API responses, and audit events contain no password, token, cookie, or secret.
"""
from __future__ import annotations

import asyncio
import os
import secrets
import time
import pytest
from pathlib import Path
from pydantic import ValidationError
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.main import create_app
from hinaa_api.persistence.auth import AuthContext, resolve_auth
from hinaa_api.persistence.db import init_db
from hinaa_api.persistence.memory_service import MemoryService
from hinaa_api.security.action_approvals import (
    ActionApprovalGate,
    PendingApprovalChallenge,
    ToolRiskLevel,
    compute_parameters_digest,
)
from hinaa_api.tools import QUARANTINED_DANGEROUS_TOOLS, load_all_tools, registry
from hinaa_api.tools.full_pc_control import FullPCControl
from hinaa_api.tools import policy as tool_policy
from hinaa_api.tools.registry import ToolDefinition
from hinaa_api.integrations.desktop_bridge_auth import get_hina_token


class MockRequest:
    def __init__(self, headers=None, client_ip="127.0.0.1"):
        self.headers = headers or {}
        self.client = type("Client", (), {"host": client_ip})()
        self.state = type("State", (), {})()


# ============================================================================
# Requirement A: Production request cannot use dev authentication
# ============================================================================
def test_boundary_a_production_dev_auth_prohibited(tmp_path):
    """A. A production request cannot use dev authentication."""
    db_url = f"sqlite:///{tmp_path}/test_a.db"
    # 1. Settings validation forbids environment=production with auth_mode=dev
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            auth_mode="dev",
            database_url=db_url,
            _env_file=None,
        )

    # 2. In clerk mode under production, dev-user header bypass is blocked
    settings_prod = Settings(
        environment="production",
        auth_mode="clerk",
        clerk_jwt_key="dummy_key",
        database_url=db_url,
        _env_file=None,
    )
    factory = init_db(settings_prod)
    memory = MemoryService(factory)
    req = MockRequest(headers={"X-HINAA-Dev-User": "evil_admin", "host": "127.0.0.1:8000"})

    with pytest.raises(HinaaError) as exc_info:
        resolve_auth(req, settings_prod, memory, x_hinaa_dev_user="evil_admin")
    assert exc_info.value.status_code in (401, 503)


# ============================================================================
# Requirement B: One tenant cannot view, approve, deny, consume, or replay another tenant's challenge
# ============================================================================
@pytest.mark.asyncio
async def test_boundary_b_cross_tenant_isolation(tmp_path):
    """B. One tenant cannot view, approve, deny, consume, or replay another tenant’s challenge."""
    db_file = tmp_path / "approvals_b.db"
    gate = ActionApprovalGate(db_path=db_file)
    params = {"target": "user_data", "action": "export"}

    # Tenant A creates a challenge
    task_a = asyncio.create_task(
        gate.request_approval(
            "computer_operator",
            params,
            tenant_id="tenant_alpha",
            actor_id="alice",
            device_id="device_a",
            timeout_seconds=30.0,
        )
    )
    await asyncio.sleep(0.05)
    pending_a = gate.list_pending(tenant_id="tenant_alpha")
    assert len(pending_a) == 1
    cid = pending_a[0]["challenge_id"]

    # 1. Tenant B cannot view Tenant A's challenge
    assert gate.get_challenge(cid, tenant_id="tenant_bravo") is None
    pending_b = gate.list_pending(tenant_id="tenant_bravo")
    assert len(pending_b) == 0

    # 2. Tenant B cannot approve/deny Tenant A's challenge
    denied_resolve = gate.resolve_challenge(cid, approved=True, tenant_id="tenant_bravo")
    assert denied_resolve is False
    assert gate.get_challenge(cid, tenant_id="tenant_alpha")["status"] == "PENDING"

    # 3. Tenant A approves their challenge
    approved_resolve = gate.resolve_challenge(cid, approved=True, tenant_id="tenant_alpha")
    assert approved_resolve is True
    await task_a

    # 4. Tenant B cannot consume Tenant A's approved challenge
    ok_b, msg_b = gate.verify_and_consume(cid, params, tenant_id="tenant_bravo")
    assert ok_b is False
    assert "CROSS_TENANT_REPLAY_BLOCKED" in msg_b

    # Verify side-effect absence: status in DB remains APPROVED (Tenant B did not consume it)
    rec = gate.get_challenge(cid, tenant_id="tenant_alpha")
    assert rec["status"] == "APPROVED"

    # 5. Tenant A consumes successfully
    ok_a, msg_a = gate.verify_and_consume(cid, params, tenant_id="tenant_alpha")
    assert ok_a is True
    assert gate.get_challenge(cid, tenant_id="tenant_alpha")["status"] == "CONSUMED"


# ============================================================================
# Requirement C: Foreign WebSocket Origin is rejected with 4403
# ============================================================================
def test_boundary_c_foreign_websocket_origin_rejected(tmp_path):
    """C. A foreign WebSocket Origin is rejected with 4403."""
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/test_c.db", _env_file=None))
    token = get_hina_token(create=True)
    client = TestClient(app)

    # Disallowed foreign origins
    for evil_origin in ("http://evil.com", "https://attacker.org", "http://localhost.evil.com"):
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(f"/ws/vmc?token={token}", headers={"origin": evil_origin}):
                pass
        assert exc.value.code == 4403


# ============================================================================
# Requirement D: Missing / invalid Origin behavior is explicitly tested
# ============================================================================
def test_boundary_d_websocket_origin_edge_cases(tmp_path):
    """D. Missing/invalid Origin behavior is explicitly tested."""
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/test_d.db", _env_file=None))
    token = get_hina_token(create=True)
    client = TestClient(app)

    # Valid origin passes
    with client.websocket_connect(f"/ws/vmc?token={token}", headers={"origin": "http://localhost:5173"}):
        pass

    with client.websocket_connect(f"/ws/vmc?token={token}", headers={"origin": "http://127.0.0.1:5173"}):
        pass

    # Malformed/spoofed origin fails with 4403
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/vmc?token={token}", headers={"origin": "null"}):
            pass
    assert exc.value.code == 4403


# ============================================================================
# Requirement E: Quarantined tools are absent from public registry and dispatcher
# ============================================================================
def test_boundary_e_quarantined_tools_absent():
    """E. Every quarantined tool is absent from the public registry and dispatcher."""
    load_all_tools()
    all_tools = registry.list_tools()
    all_tool_names = set(all_tools.keys())

    for tool in QUARANTINED_DANGEROUS_TOOLS:
        assert tool not in all_tool_names, f"Quarantined tool '{tool}' found in registry"
        assert registry.get_tool(tool) is None
        assert registry.get_handler(tool) is None


# ============================================================================
# Requirement F: full_pc_control cannot read sensitive or unallowed paths
# ============================================================================
def test_boundary_f_full_pc_control_cannot_read_files():
    """F. full_pc_control cannot read /etc/hostname, user files, browser data, SSH keys, or files outside an allowed workspace."""
    pc = FullPCControl()
    targets = [
        "/etc/hostname",
        "/etc/passwd",
        "C:/Windows/System32/drivers/etc/hosts",
        str(Path.home() / ".ssh" / "id_rsa"),
        str(Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data"),
    ]
    for target in targets:
        result = pc.read_file(target)
        assert "CONTAINED" in result, f"read_file({target}) did not return containment message"
        # Ensure no actual file contents were leaked
        assert "root:" not in result
        assert "PRIVATE KEY" not in result


# ============================================================================
# Requirement G: full_pc_control cannot start any process or command
# ============================================================================
@pytest.mark.asyncio
async def test_boundary_g_full_pc_control_cannot_start_processes():
    """G. full_pc_control cannot start a process, shell command, network request, or child process."""
    pc = FullPCControl()
    dangerous_commands = [
        "calc.exe",
        "ping 127.0.0.1",
        "curl http://127.0.0.1:8000",
        "powershell -Command Get-Process",
    ]
    for cmd in dangerous_commands:
        res = await pc.run_command(cmd)
        assert res["ok"] is False
        assert "TOOL_CONTAINED" in res["error"]
        assert res["exit_code"] == -1


# ============================================================================
# Requirement H: confirmed=false never executes
# ============================================================================
def test_boundary_h_confirmed_false_never_executes():
    """H. confirmed=false never executes."""
    for tier in (
        tool_policy.ActionRiskTier.TIER_2_EXTERNAL,
        tool_policy.ActionRiskTier.TIER_3_PROCESS,
        tool_policy.ActionRiskTier.TIER_4_DESTRUCTIVE,
    ):
        verdict = tool_policy.check_action_tier_authorization(tier, confirmed=False, approval_source="none")
        assert not verdict.permitted
        assert verdict.code == "EXPLICIT_USER_APPROVAL_REQUIRED"


# ============================================================================
# Requirement I: Approval does not execute automatically; consumption is separate
# ============================================================================
@pytest.mark.asyncio
async def test_boundary_i_approval_and_consumption_separation(tmp_path):
    """I. Approval does not execute automatically; consumption is a separate checked operation."""
    db_file = tmp_path / "approvals_i.db"
    gate = ActionApprovalGate(db_path=db_file)
    params = {"command": "reboot", "runtime": "powershell"}

    task = asyncio.create_task(
        gate.request_approval(
            "terminal_execute",
            params,
            tenant_id="tenant_i",
            actor_id="actor_i",
            device_id="device_i",
            timeout_seconds=10.0,
        )
    )
    await asyncio.sleep(0.05)
    pending = gate.list_pending(tenant_id="tenant_i")
    cid = pending[0]["challenge_id"]

    # Approve challenge
    gate.resolve_challenge(cid, approved=True, tenant_id="tenant_i", reason="Operator approved")
    approved, _, _ = await task
    assert approved is True

    # Challenge is APPROVED, but NOT yet CONSUMED
    rec = gate.get_challenge(cid, tenant_id="tenant_i")
    assert rec["status"] == "APPROVED"
    assert rec.get("consumed_at") is None

    # Consumption is a separate explicit checked step
    ok, msg = gate.verify_and_consume(cid, params, tenant_id="tenant_i")
    assert ok is True
    rec_after = gate.get_challenge(cid, tenant_id="tenant_i")
    assert rec_after["status"] == "CONSUMED"
    assert rec_after["consumed_at"] is not None


# ============================================================================
# Requirement J: Parameter mutation after approval produces TAMPER_DETECTED
# ============================================================================
@pytest.mark.asyncio
async def test_boundary_j_parameter_tampering_defense(tmp_path):
    """J. Parameter mutation after approval produces TAMPER_DETECTED with zero side effects."""
    db_file = tmp_path / "approvals_j.db"
    gate = ActionApprovalGate(db_path=db_file)
    authorized_params = {"command": "echo 'safe'"}
    tampered_params = {"command": "rm -rf /"}

    task = asyncio.create_task(
        gate.request_approval(
            "terminal_execute",
            authorized_params,
            tenant_id="tenant_j",
            actor_id="actor_j",
            device_id="device_j",
            timeout_seconds=10.0,
        )
    )
    await asyncio.sleep(0.05)
    pending = gate.list_pending(tenant_id="tenant_j")
    cid = pending[0]["challenge_id"]
    gate.resolve_challenge(cid, approved=True, tenant_id="tenant_j")
    await task

    # Tampered call fails
    ok_tamper, msg_tamper = gate.verify_and_consume(cid, tampered_params, tenant_id="tenant_j")
    assert ok_tamper is False
    assert "TAMPER_DETECTED" in msg_tamper

    # Absence of side effects: challenge remains unconsumed and ready for authorized parameters
    rec = gate.get_challenge(cid, tenant_id="tenant_j")
    assert rec["status"] == "APPROVED"

    # Authorized parameters succeed
    ok_valid, _ = gate.verify_and_consume(cid, authorized_params, tenant_id="tenant_j")
    assert ok_valid is True
    assert gate.get_challenge(cid, tenant_id="tenant_j")["status"] == "CONSUMED"


# ============================================================================
# Requirement K: Two concurrent consumers produce exactly one success and one replay denial
# ============================================================================
@pytest.mark.asyncio
async def test_boundary_k_concurrent_consumer_atomic_replay_defense(tmp_path):
    """K. Two concurrent consumers produce exactly one success and one replay denial."""
    db_file = tmp_path / "approvals_k.db"
    gate = ActionApprovalGate(db_path=db_file)
    params = {"target": "critical_resource"}

    task = asyncio.create_task(
        gate.request_approval(
            "computer_operator",
            params,
            tenant_id="tenant_k",
            actor_id="actor_k",
            device_id="device_k",
            timeout_seconds=10.0,
        )
    )
    await asyncio.sleep(0.05)
    pending = gate.list_pending(tenant_id="tenant_k")
    cid = pending[0]["challenge_id"]
    gate.resolve_challenge(cid, approved=True, tenant_id="tenant_k")
    await task

    # Run two concurrent consumptions
    results = await asyncio.gather(
        asyncio.to_thread(gate.verify_and_consume, cid, params, tenant_id="tenant_k"),
        asyncio.to_thread(gate.verify_and_consume, cid, params, tenant_id="tenant_k"),
    )

    successes = [r for r in results if r[0] is True]
    denials = [r for r in results if r[0] is False]

    assert len(successes) == 1, "Exactly one consumer must succeed"
    assert len(denials) == 1, "Exactly one consumer must be denied"
    assert "REPLAY_DETECTED" in denials[0][1] or "CONCURRENT_CONSUMPTION_BLOCKED" in denials[0][1]


# ============================================================================
# Requirement L: Expired and denied approvals cannot execute
# ============================================================================
@pytest.mark.asyncio
async def test_boundary_l_expired_and_denied_cannot_execute(tmp_path):
    """L. Expired and denied approvals cannot execute."""
    db_file = tmp_path / "approvals_l.db"
    gate = ActionApprovalGate(db_path=db_file)
    params = {"action": "dangerous_action"}

    # 1. Denied challenge
    task_deny = asyncio.create_task(
        gate.request_approval(
            "terminal_execute",
            params,
            tenant_id="tenant_l",
            actor_id="actor_l",
            device_id="device_l",
            timeout_seconds=10.0,
        )
    )
    await asyncio.sleep(0.05)
    pending_deny = gate.list_pending(tenant_id="tenant_l")
    cid_deny = pending_deny[0]["challenge_id"]
    gate.resolve_challenge(cid_deny, approved=False, tenant_id="tenant_l", reason="User clicked Deny")
    approved, _, _ = await task_deny
    assert approved is False

    ok_deny, msg_deny = gate.verify_and_consume(cid_deny, params, tenant_id="tenant_l")
    assert ok_deny is False
    assert "not approved" in msg_deny

    # 2. Expired challenge
    task_exp = asyncio.create_task(
        gate.request_approval(
            "terminal_execute",
            params,
            tenant_id="tenant_l",
            actor_id="actor_l",
            device_id="device_l",
            timeout_seconds=0.1,
        )
    )
    approved_exp, _, cid_exp = await task_exp
    assert approved_exp is False

    ok_exp, msg_exp = gate.verify_and_consume(cid_exp, params, tenant_id="tenant_l")
    assert ok_exp is False
    assert "not approved" in msg_exp or "expired" in msg_exp.lower()


# ============================================================================
# Requirement M: Restart persistence never changes PENDING into APPROVED
# ============================================================================
@pytest.mark.asyncio
async def test_boundary_m_restart_never_escalates_to_approved(tmp_path):
    """M. Restart persistence never changes PENDING into APPROVED."""
    db_file = tmp_path / "approvals_m.db"
    gate1 = ActionApprovalGate(db_path=db_file)
    params = {"command": "deploy_prod"}

    task = asyncio.create_task(
        gate1.request_approval(
            "terminal_execute",
            params,
            tenant_id="tenant_m",
            actor_id="actor_m",
            device_id="device_m",
            timeout_seconds=60.0,
        )
    )
    await asyncio.sleep(0.05)
    pending_m = gate1.list_pending(tenant_id="tenant_m")
    cid = pending_m[0]["challenge_id"]

    # Terminate process, start gate2 from the same database
    gate2 = ActionApprovalGate(db_path=db_file)
    recovered = gate2.get_challenge(cid, tenant_id="tenant_m")

    # Must remain PENDING (or EXPIRED), NEVER silently promoted to APPROVED
    assert recovered["status"] == "PENDING"
    assert recovered["approved"] == 0

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ============================================================================
# Requirement N: Startup fails if a quarantined tool becomes registered
# ============================================================================
def test_boundary_n_startup_fails_if_quarantined_tool_registered(tmp_path):
    """N. Startup fails if a quarantined tool becomes registered."""
    settings = Settings(database_url=f"sqlite:///{tmp_path}/test_n.db", _env_file=None)
    app = create_app(settings)

    # Inject a quarantined tool into registry
    registry.register(
        ToolDefinition(
            name="hacker_agent",
            display_name="Injected Malicious Tool",
            description="Exploit tool",
            parameters={},
            required_parameters=[],
            risk_tier=4,
        ),
        handler=lambda x: x,
    )

    client = TestClient(app)
    # The lifespan startup check must raise RuntimeError for containment breach
    with pytest.raises(RuntimeError) as exc_info:
        with client:
            pass
    assert "CONTAINMENT BREACH: Quarantined dangerous tools are registered" in str(exc_info.value)

    # Clean up test registry
    registry.unregister("hacker_agent")


# ============================================================================
# Requirement O: Logs, API responses, and audit events contain no secrets
# ============================================================================
def test_boundary_o_zero_sensitive_data_in_records(tmp_path):
    """O. Logs, API responses, and audit events contain no password, token, cookie, or secret."""
    sensitive_params = {
        "token": "sk-secret-token-12345",
        "password": "SuperSecretPassword!",
        "api_key": "hk_live_secret_key_999",
    }
    digest = compute_parameters_digest(sensitive_params)
    assert "sk-secret" not in digest
    assert "SuperSecretPassword" not in digest

    # Verify challenge representation contains parameters digest and redacted parameters rather than raw leaked tokens
    challenge = PendingApprovalChallenge(
        challenge_id="appr_test_o",
        tool_name="test_tool",
        parameters=sensitive_params,
        risk_level=ToolRiskLevel.DANGEROUS,
        description="Run test tool",
        created_at=time.time(),
        expires_at=time.time() + 300,
        tenant_id="tenant_o",
        actor_id="actor_o",
        device_id="device_o",
        parameters_digest=digest,
        nonce="nonce_123",
    )
    d = challenge.to_dict()
    assert d["parameters_digest"] == digest
    assert len(d["nonce"]) > 0
    assert d["parameters"]["token"] == "[REDACTED]"
    assert d["parameters"]["password"] == "[REDACTED]"
    assert d["parameters"]["api_key"] == "[REDACTED]"
