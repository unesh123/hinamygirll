import pytest
from hinaa_api.tools import load_all_tools, registry
from hinaa_api.tools.registry import RiskTier, ToolDefinition, ToolEffect, ToolRegistry
from hinaa_api.tools.policy import LOCAL_EFFECT_TOOLS, IRREVERSIBLE_EXTERNAL_TOOLS


def test_tool_definition_validation():
    """Verify registry validates required tool definition fields and risk tiers."""
    reg = ToolRegistry()

    # Empty name
    with pytest.raises(ValueError, match="Tool name must not be empty"):
        reg.register(
            ToolDefinition(
                name="",
                display_name="Test",
                description="desc",
                parameters={},
                required_parameters=[],
            ),
            handler=lambda x: x,
        )

    # Empty description
    with pytest.raises(ValueError, match="must have a non-empty description"):
        reg.register(
            ToolDefinition(
                name="valid_name",
                display_name="Test",
                description="",
                parameters={},
                required_parameters=[],
            ),
            handler=lambda x: x,
        )

    # Invalid risk tier
    with pytest.raises(Exception):
        ToolDefinition(
            name="bad_tier",
            display_name="Bad Tier",
            description="desc",
            parameters={},
            required_parameters=[],
            risk_tier=99,
        )


def test_risk_tier_and_tool_effect_enums():
    """Verify RiskTier and ToolEffect enum constants."""
    assert RiskTier.TIER_0_READ_ONLY == 0
    assert RiskTier.TIER_1_REVERSIBLE == 1
    assert RiskTier.TIER_2_EXTERNAL == 2
    assert RiskTier.TIER_3_PROCESS == 3
    assert RiskTier.TIER_4_DESTRUCTIVE == 4

    assert ToolEffect.READ.value == "read"
    assert ToolEffect.EXECUTE_PROCESS.value == "execute_process"
    assert ToolEffect.DESTRUCTIVE_SYSTEM.value == "destructive_system"


def test_full_registry_audit_passes():
    """Verify that every tool registered in production has complete schemas and descriptions."""
    load_all_tools()
    audit = registry.audit_registry()

    assert audit["total_tools"] > 0
    assert audit["missing_description"] == [], f"Tools missing description: {audit['missing_description']}"
    assert audit["missing_schema"] == [], f"Tools missing parameters: {audit['missing_schema']}"

    # Tier counts must sum to total tools
    assert sum(audit["tier_counts"].values()) == audit["total_tools"]


def test_tier_3_and_4_tools_have_policy_coverage():
    """Every tool capable of process execution or destructive action must be governed by policy."""
    load_all_tools()
    tools = registry.list_tools()

    for name, tdef in tools.items():
        if tdef.risk_tier >= 3:
            has_coverage = name in LOCAL_EFFECT_TOOLS or name in IRREVERSIBLE_EXTERNAL_TOOLS
            assert has_coverage, f"Tier {tdef.risk_tier} tool '{name}' lacks explicit effect policy entry!"
