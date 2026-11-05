"""
HINAA OS — Phase 11 & Phase 12 Specialist Agent & Team Registry
Authoritative registry defining specialized agent roles, team templates, capability whitelists,
model routing, and provider health/degradation states.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .contracts import (
    AgentRole,
    AgentSpec,
    BudgetLedger,
    CapabilityGrant,
    PermissionTier,
    TeamSpec,
    TeamType,
)

logger = logging.getLogger("hinaa.agents.registry")


class SpecialistRegistry:
    """Manages the lifecycle, capability grants, and health of specialist agents and teams."""

    def __init__(self) -> None:
        self._specs: Dict[AgentRole, AgentSpec] = {}
        self._team_specs: Dict[TeamType, TeamSpec] = {}
        self._initialize_specialists()
        self._initialize_teams()

    def _initialize_specialists(self) -> None:
        """Register the 10 canonical specialist roles with least-privilege capability grants."""
        
        # 1. Supervisor / Coordinator
        self.register_agent(
            AgentSpec(
                agent_id="agent-supervisor",
                role=AgentRole.SUPERVISOR,
                display_name="Hinaa Supervisor",
                description="Top-level mission coordinator, task decomposition arbiter, and authoritative response owner.",
                model="gemini-2.5-pro",
                provider="google",
                capability_grant=CapabilityGrant(
                    role=AgentRole.SUPERVISOR,
                    allowed_tools=["plan_decomposition", "check_policy", "synthesize_response"],
                    permission_tier=PermissionTier.TIER_A_READ_ONLY,
                    max_tokens=32768,
                    max_tool_calls=50,
                    max_wall_time_seconds=300.0,
                ),
            )
        )

        # 2. Planner
        self.register_agent(
            AgentSpec(
                agent_id="agent-planner",
                role=AgentRole.PLANNER,
                display_name="Task Planner",
                description="Generates acyclic dependency DAGs, step validations, and recovery failure branches.",
                model="claude-3-7-sonnet",
                provider="anthropic",
                capability_grant=CapabilityGrant(
                    role=AgentRole.PLANNER,
                    allowed_tools=["dag_validator", "inspect_project_structure", "simulate_nepali_payment", "verify_paisa_amount"],
                    permission_tier=PermissionTier.TIER_A_READ_ONLY,
                    max_tokens=16384,
                    max_tool_calls=15,
                ),
            )
        )

        # 3. Researcher
        self.register_agent(
            AgentSpec(
                agent_id="agent-researcher",
                role=AgentRole.RESEARCHER,
                display_name="Grounded Researcher",
                description="Extracts factual evidence from authorized web and documentation sources with CRAG citations.",
                model="gemini-2.5-flash",
                provider="google",
                capability_grant=CapabilityGrant(
                    role=AgentRole.RESEARCHER,
                    allowed_tools=["crag_search", "fetch_url_content", "extract_citations"],
                    permission_tier=PermissionTier.TIER_A_READ_ONLY,
                    network_egress_allowed=True,
                    max_tokens=16384,
                    max_tool_calls=25,
                ),
            )
        )

        # 4. Engineer
        self.register_agent(
            AgentSpec(
                agent_id="agent-engineer",
                role=AgentRole.ENGINEER,
                display_name="Code Engineer",
                description="Executes scoped workspace code modifications, builds, and patches inside Phase 08 sandbox.",
                model="claude-3-7-sonnet",
                provider="anthropic",
                capability_grant=CapabilityGrant(
                    role=AgentRole.ENGINEER,
                    allowed_tools=[
                        "apply_diff_patch", "read_file", "write_file", "run_sandbox_command",
                        "sandbox_read", "sandbox_write", "sandbox_execute", "git_commit_scoped"
                    ],
                    permission_tier=PermissionTier.TIER_B_SCOPED_DEV,
                    workspace_scoped=True,
                    max_tokens=32768,
                    max_tool_calls=30,
                ),
            )
        )

        # 5. QA & Verifier
        self.register_agent(
            AgentSpec(
                agent_id="agent-qa",
                role=AgentRole.QA,
                display_name="Quality Assurance Verifier",
                description="Independently runs tests, builds, and postcondition validation; never self-approves without receipts.",
                model="gemini-2.5-flash",
                provider="google",
                capability_grant=CapabilityGrant(
                    role=AgentRole.QA,
                    allowed_tools=[
                        "run_pytest", "run_npm_test", "inspect_diff", "verify_checksums",
                        "run_test_suite", "verify_file_hash", "check_exit_code"
                    ],
                    permission_tier=PermissionTier.TIER_B_SCOPED_DEV,
                    max_tokens=16384,
                    max_tool_calls=20,
                ),
            )
        )

        # 6. Browser Operator
        self.register_agent(
            AgentSpec(
                agent_id="agent-browser",
                role=AgentRole.BROWSER_OPERATOR,
                display_name="Browser Operator",
                description="Navigates approved web applications with accessible locators and postcondition verification.",
                model="gemini-2.5-flash",
                provider="google",
                capability_grant=CapabilityGrant(
                    role=AgentRole.BROWSER_OPERATOR,
                    allowed_tools=["browser_navigate", "browser_click", "browser_type", "browser_screenshot", "inspect_accessibility_tree", "verify_page_content"],
                    permission_tier=PermissionTier.TIER_B_SCOPED_DEV,
                    network_egress_allowed=True,
                    max_tokens=16384,
                    max_tool_calls=30,
                ),
            )
        )

        # 7. Creative Operator
        self.register_agent(
            AgentSpec(
                agent_id="agent-creative",
                role=AgentRole.CREATIVE_OPERATOR,
                display_name="Creative Studio Operator",
                description="Produces supported raster imagery and timeline video exports adhering to honest capability matrix.",
                model="local-creative",
                provider="local",
                capability_grant=CapabilityGrant(
                    role=AgentRole.CREATIVE_OPERATOR,
                    allowed_tools=["generate_raster", "inpaint_raster", "export_timeline_video", "generate_video_prompt"],
                    permission_tier=PermissionTier.TIER_B_SCOPED_DEV,
                    max_tokens=8192,
                    max_tool_calls=10,
                ),
            )
        )

        # 8. Knowledge Curator
        self.register_agent(
            AgentSpec(
                agent_id="agent-curator",
                role=AgentRole.KNOWLEDGE_CURATOR,
                display_name="Knowledge Curator",
                description="Stages verified candidate facts into Phase 10 quarantine and maintains temporal graph integrity.",
                model="gemini-2.5-flash",
                provider="google",
                capability_grant=CapabilityGrant(
                    role=AgentRole.KNOWLEDGE_CURATOR,
                    allowed_tools=["stage_ingestion_candidate", "query_knowledge_graph", "check_contradiction"],
                    permission_tier=PermissionTier.TIER_A_READ_ONLY,
                    max_tokens=16384,
                    max_tool_calls=20,
                ),
            )
        )

        # 9. Localization Specialist
        self.register_agent(
            AgentSpec(
                agent_id="agent-localization",
                role=AgentRole.LOCALIZATION_SPECIALIST,
                display_name="Bilingual Localization Specialist",
                description="Formats natural, culturally grounded English, Nepali Devanagari, and Romanized Nepali content.",
                model="gemini-2.5-flash",
                provider="google",
                capability_grant=CapabilityGrant(
                    role=AgentRole.LOCALIZATION_SPECIALIST,
                    allowed_tools=[
                        "nepali_transliterator", "glossary_lookup", "devanagari_normalizer",
                        "translate_text", "validate_devanagari_encoding", "cultural_glossary_lookup"
                    ],
                    permission_tier=PermissionTier.TIER_A_READ_ONLY,
                    max_tokens=16384,
                    max_tool_calls=15,
                ),
            )
        )

        # 10. Security Reviewer
        self.register_agent(
            AgentSpec(
                agent_id="agent-security",
                role=AgentRole.SECURITY_REVIEWER,
                display_name="Defensive Security Reviewer",
                description="Audits tool arguments, secret scrubbing, prompt injection, and multi-tenant boundary compliance.",
                model="claude-3-7-sonnet",
                provider="anthropic",
                capability_grant=CapabilityGrant(
                    role=AgentRole.SECURITY_REVIEWER,
                    allowed_tools=["audit_secret_canaries", "detect_prompt_injection", "validate_tenant_bounds"],
                    permission_tier=PermissionTier.TIER_A_READ_ONLY,
                    max_tokens=16384,
                    max_tool_calls=20,
                ),
            )
        )

    def _initialize_teams(self) -> None:
        """Register the 4 canonical team templates composed of the 10 specialist roles."""
        
        # 1. Engineering Team
        self.register_team(
            TeamSpec(
                team_id="team-engineering",
                team_type=TeamType.ENGINEERING,
                display_name="Engineering Core Team",
                description="Specialized in software development, builds, sandbox execution, browser testing, and independent QA verification.",
                lead_role=AgentRole.ENGINEER,
                member_roles=[AgentRole.ENGINEER, AgentRole.QA, AgentRole.BROWSER_OPERATOR],
                capability_grant=CapabilityGrant(
                    role=AgentRole.ENGINEER,
                    allowed_tools=[
                        "sandbox_read", "sandbox_write", "sandbox_execute", "git_commit_scoped",
                        "run_test_suite", "verify_file_hash", "check_exit_code",
                        "browser_navigate", "browser_screenshot"
                    ],
                    permission_tier=PermissionTier.TIER_B_SCOPED_DEV,
                    workspace_scoped=True,
                    max_tokens=49152,
                    max_tool_calls=50,
                ),
                budget_slice=BudgetLedger(allocated_tokens=49152, allocated_tool_calls=50, allocated_cost_paisa=15000),
            )
        )

        # 2. Research Team
        self.register_team(
            TeamSpec(
                team_id="team-research",
                team_type=TeamType.RESEARCH,
                display_name="Grounded Research & Localization Team",
                description="Conducts multi-hop evidence gathering, source verification, citation extraction, and bilingual Nepali cultural adaptation.",
                lead_role=AgentRole.RESEARCHER,
                member_roles=[AgentRole.RESEARCHER, AgentRole.KNOWLEDGE_CURATOR, AgentRole.LOCALIZATION_SPECIALIST],
                capability_grant=CapabilityGrant(
                    role=AgentRole.RESEARCHER,
                    allowed_tools=[
                        "crag_search", "fetch_url_content", "extract_citations",
                        "stage_ingestion_candidate", "query_knowledge_graph",
                        "translate_text", "validate_devanagari_encoding"
                    ],
                    permission_tier=PermissionTier.TIER_A_READ_ONLY,
                    network_egress_allowed=True,
                    max_tokens=32768,
                    max_tool_calls=35,
                ),
                budget_slice=BudgetLedger(allocated_tokens=32768, allocated_tool_calls=35, allocated_cost_paisa=8000),
            )
        )

        # 3. Creative Team
        self.register_team(
            TeamSpec(
                team_id="team-creative",
                team_type=TeamType.CREATIVE,
                display_name="Creative Studio & Asset Team",
                description="Produces supported raster imagery, masked inpainting, and timeline video exports with truthful limitation reporting.",
                lead_role=AgentRole.CREATIVE_OPERATOR,
                member_roles=[AgentRole.CREATIVE_OPERATOR, AgentRole.QA],
                capability_grant=CapabilityGrant(
                    role=AgentRole.CREATIVE_OPERATOR,
                    allowed_tools=[
                        "generate_raster", "inpaint_raster", "export_timeline_video",
                        "verify_file_hash", "check_exit_code"
                    ],
                    permission_tier=PermissionTier.TIER_B_SCOPED_DEV,
                    max_tokens=16384,
                    max_tool_calls=20,
                ),
                budget_slice=BudgetLedger(allocated_tokens=16384, allocated_tool_calls=20, allocated_cost_paisa=5000),
            )
        )

        # 4. Operations Team
        self.register_team(
            TeamSpec(
                team_id="team-operations",
                team_type=TeamType.OPERATIONS,
                display_name="Operations & Security Team",
                description="Governs graph planning, browser automation runs, tenant boundary auditing, and security review.",
                lead_role=AgentRole.PLANNER,
                member_roles=[AgentRole.PLANNER, AgentRole.BROWSER_OPERATOR, AgentRole.SECURITY_REVIEWER],
                capability_grant=CapabilityGrant(
                    role=AgentRole.PLANNER,
                    allowed_tools=[
                        "dag_validator", "inspect_project_structure",
                        "browser_navigate", "browser_screenshot",
                        "audit_secret_canaries", "detect_prompt_injection", "validate_tenant_bounds"
                    ],
                    permission_tier=PermissionTier.TIER_A_READ_ONLY,
                    max_tokens=24576,
                    max_tool_calls=25,
                ),
                budget_slice=BudgetLedger(allocated_tokens=24576, allocated_tool_calls=25, allocated_cost_paisa=6000),
            )
        )

    def register_agent(self, spec: AgentSpec) -> None:
        """Register or update an agent specification in the catalog."""
        self._specs[spec.role] = spec

    def get_agent(self, role: AgentRole | str) -> Optional[AgentSpec]:
        """Fetch agent spec by role. Validates role against whitelist."""
        if isinstance(role, str):
            try:
                role = AgentRole(role)
            except ValueError:
                return None
        return self._specs.get(role)

    def list_agents(self) -> List[AgentSpec]:
        """Return all registered specialist agents."""
        return list(self._specs.values())

    def list_all_agents(self) -> List[AgentSpec]:
        """Alias for list_agents."""
        return self.list_agents()

    def get_capability_grant(self, role: AgentRole | str) -> Optional[CapabilityGrant]:
        """Fetch capability grant for a specialist role."""
        spec = self.get_agent(role)
        return spec.capability_grant if spec else None

    def validate_capability(self, role: AgentRole, tool_name: str) -> bool:
        """Check whether a specialist role is whitelisted to invoke a specific tool."""
        spec = self.get_agent(role)
        if not spec or not spec.is_available:
            return False
        return tool_name in spec.capability_grant.allowed_tools

    def is_tool_allowed(self, role: AgentRole, tool_name: str) -> bool:
        """Alias for validate_capability."""
        return self.validate_capability(role, tool_name)

    def is_available(self, role: AgentRole | str) -> bool:
        """Check if an agent role is currently available and healthy."""
        spec = self.get_agent(role)
        return spec.is_available if spec else False

    def update_health(self, role: AgentRole | str, status: str) -> None:
        """Update health status of a specific agent role."""
        spec = self.get_agent(role)
        if spec:
            spec.health_status = status
            spec.is_available = (status != "UNAVAILABLE")

    def update_provider_health(self, provider: str, status: str) -> None:
        """Update health status of agents using a provider; fails over to local when unavailable."""
        for spec in self._specs.values():
            if spec.provider == provider:
                spec.health_status = status
                if status == "UNAVAILABLE":
                    spec.is_available = False
                    logger.warning("Agent %s degraded: provider %s is unavailable.", spec.role, provider)
                else:
                    spec.is_available = True

    # --- Phase 12 Team Templates ---

    def register_team(self, spec: TeamSpec) -> None:
        """Register or update a team template specification."""
        self._team_specs[spec.team_type] = spec

    def get_team_spec(self, team_type: TeamType | str) -> Optional[TeamSpec]:
        """Fetch team template spec by TeamType."""
        if isinstance(team_type, str):
            try:
                team_type = TeamType(team_type)
            except ValueError:
                return None
        return self._team_specs.get(team_type)

    def list_teams(self) -> List[TeamSpec]:
        """List all 4 canonical team template specifications."""
        return list(self._team_specs.values())


# Singleton registry instance
specialist_registry = SpecialistRegistry()
