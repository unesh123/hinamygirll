"""Tests for Hina Agent OS Runtime Specification (12 states, 13-field envelope, manifest & connector health)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.runtime.os_contract import (
    ALLOWED_CAPABILITY_STATES,
    PREVIEW_STAGES,
    CapabilityState,
    ToolResultEnvelope,
    make_tool_envelope,
    register_runtime_os_tools,
)
from hinaa_api.tools.registry import registry


def test_capability_states_and_envelope_schema() -> None:
    assert len(ALLOWED_CAPABILITY_STATES) == 12
    for expected in (
        "unavailable",
        "configured",
        "authorized",
        "connected",
        "reachable",
        "executing",
        "tested",
        "healthy",
        "degraded",
        "failed",
        "revoked",
        "not_verified",
    ):
        assert expected in ALLOWED_CAPABILITY_STATES

    assert len(PREVIEW_STAGES) >= 9
    env = make_tool_envelope(
        "workspace_hash",
        {"status": "success", "path": "README.md", "sha256": "abc"},
        verification_state=CapabilityState.TESTED,
    )
    assert isinstance(env, ToolResultEnvelope)
    for field in (
        "success",
        "status",
        "operation_id",
        "timestamp",
        "tool_name",
        "human_summary",
        "structured_result",
        "evidence",
        "changed_resources",
        "warnings",
        "error",
        "reversible",
        "verification_state",
    ):
        assert hasattr(env, field)
    assert env.success is True
    assert env.verification_state == "tested"


def test_runtime_os_tools_registered_and_policy_clean() -> None:
    register_runtime_os_tools()
    for name in (
        "workspace_read",
        "workspace_write",
        "workspace_patch",
        "workspace_tree",
        "workspace_search",
        "workspace_hash",
        "workspace_export",
        "workspace_verify",
        "terminal_execute",
        "process_start",
        "process_stop",
        "process_status",
        "process_logs",
        "port_check",
        "build_project",
        "test_project",
        "project_detect",
        "preview_start",
        "preview_healthcheck",
        "preview_routes",
        "preview_status",
        "preview_stop",
        "visual_snapshot",
        "layout_audit",
        "responsive_audit",
        "accessibility_audit",
        "performance_audit",
        "console_error_audit",
        "connector_list",
        "connector_status",
        "connector_test",
        "connector_healthcheck",
    ):
        assert registry.get(name) is not None, f"Missing registered runtime OS tool: {name}"

    audit = registry.audit_registry()
    assert audit["unmapped_policy"] == []


def test_runtime_manifest_and_connector_health_endpoints() -> None:
    from hinaa_api.main import create_app

    app = create_app(Settings(provider_mode="mock"))
    with TestClient(app) as client:
        manifest = client.get("/v1/runtime/tools-manifest")
        assert manifest.status_code == 200
        m_data = manifest.json()
        assert m_data["totalTools"] >= 32
        assert m_data["audit"]["unmapped_policy"] == []

        health = client.get("/v1/connectors/health")
        assert health.status_code == 200
        h_data = health.json()
        assert h_data["status"] == "success"
        ids = {c["id"]: c for c in h_data["connectors"]}
        assert "edge_tts" in ids
        assert "heygen" in ids
        assert "workspace_fs" in ids
