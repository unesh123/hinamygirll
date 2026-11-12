from __future__ import annotations

import pytest
from hinaa_api.agents.contracts import AgentRole, PermissionTier, PHASE05_ROLE_MAP
from hinaa_api.agents.registry import SpecialistRegistry
from hinaa_api.tools.registry import ToolDefinition, ToolRegistry


def test_specialist_registry_contains_10_phase05_roles():
    reg = SpecialistRegistry()
    assert len(reg.list_all_agents()) == 10
    assert len(AgentRole) == 10

    phase05_aliases = [
        "orchestrator",
        "research",
        "frontend",
        "backend",
        "database",
        "qa",
        "security",
        "docs",
        "creative",
        "media",
    ]
    for alias in phase05_aliases:
        agent = reg.get_agent_by_role(alias)
        assert agent is not None, f"Phase 05 alias '{alias}' could not be resolved"
        assert agent.capability_grant is not None
        assert len(agent.capability_grant.allowed_tools) > 0
        assert agent.capability_grant.max_tokens >= 8192


def test_specialist_least_privilege_tiers():
    reg = SpecialistRegistry()

    # Research and Orchestrator are TIER_A_READ_ONLY
    orchestrator = reg.get_agent_by_role("orchestrator")
    assert orchestrator.capability_grant.permission_tier == PermissionTier.TIER_A_READ_ONLY

    researcher = reg.get_agent_by_role("research")
    assert researcher.capability_grant.permission_tier == PermissionTier.TIER_A_READ_ONLY
    assert researcher.capability_grant.network_egress_allowed is True

    # Frontend and Backend are TIER_B_SCOPED_DEV and workspace scoped
    frontend = reg.get_agent_by_role("frontend")
    assert frontend.capability_grant.permission_tier == PermissionTier.TIER_B_SCOPED_DEV
    assert frontend.capability_grant.workspace_scoped is True

    backend = reg.get_agent_by_role("backend")
    assert backend.capability_grant.permission_tier == PermissionTier.TIER_B_SCOPED_DEV
    assert backend.capability_grant.workspace_scoped is True


def test_tool_definition_phase05_contracts():
    tool = ToolDefinition(
        name="test_tool",
        display_name="Test Tool",
        description="A verified test tool.",
        parameters={"path": {"type": "string"}},
        required_parameters=["path"],
        timeout_seconds=45.0,
        retry_policy="exponential_backoff",
        risk_tier=2,
        audit_category="file_system",
        output_schema={"status": "string", "lines": "integer"},
    )
    assert tool.timeout_seconds == 45.0
    assert tool.retry_policy == "exponential_backoff"
    assert tool.risk_tier == 2
    assert tool.audit_category == "file_system"
    assert "status" in tool.output_schema

    reg = ToolRegistry()
    reg.register(tool, lambda path: {"status": "ok", "lines": 10})
    prompt = reg.generate_system_prompt()
    assert "test_tool(path*)" in prompt
    assert "A verified test tool." in prompt
