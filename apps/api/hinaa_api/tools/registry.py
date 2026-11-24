from enum import Enum, IntEnum
from typing import Any, Callable, Awaitable
from pydantic import BaseModel, Field


class RiskTier(IntEnum):
    TIER_0_READ_ONLY = 0      # Read-only inspection
    TIER_1_REVERSIBLE = 1     # Reversible workspace mutation
    TIER_2_EXTERNAL = 2       # External navigation and downloads
    TIER_3_PROCESS = 3        # Process execution and credential use
    TIER_4_DESTRUCTIVE = 4    # Destructive, privileged, deletion, external publication


class ToolEffect(str, Enum):
    NONE = "none"
    READ = "read"
    MUTATE_WORKSPACE = "mutate_workspace"
    EXTERNAL_NETWORK = "external_network"
    EXECUTE_PROCESS = "execute_process"
    DESTRUCTIVE_SYSTEM = "destructive_system"


class ToolParameter(BaseModel):
    type: str
    description: str
    required: bool = True

class ToolDefinition(BaseModel):
    timeout_seconds: float = Field(default=120.0, gt=0, le=600)
    name: str
    display_name: str
    description: str
    parameters: dict[str, dict[str, Any]]
    required_parameters: list[str]
    permission_level: str = "default"
    requires_confirmation: bool = False
    risk_level: str = "medium"  # low, medium, high
    cancellable: bool = True
    voice_aliases: list[str] = []
    # Claude Code-style execution metadata
    is_read_only: bool = False          # tool never mutates state (safe to parallelize)
    is_concurrency_safe: bool = True    # can run in parallel with other tools
    is_destructive: bool = False        # tool modifies/deletes persistent data
    is_long_running: bool = False       # tool may take >30s
    max_retries: int = 1                # how many times to retry on transient failure
    # Phase 05 Singularity Enhancements
    retry_policy: str = "exponential_backoff"  # exponential_backoff | immediate | none
    risk_tier: int = Field(default=0, ge=0, le=4)  # 0..4 mapped to RiskTier
    tool_effect: ToolEffect = Field(default=ToolEffect.NONE)
    audit_category: str = "general"            # general | file_system | terminal | network | browser | code | media
    output_schema: dict[str, Any] = Field(default_factory=dict)

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable] = {}
    
    def register(self, tool_def: ToolDefinition, handler: Callable):
        if not tool_def.name or not tool_def.name.strip():
            raise ValueError("Tool name must not be empty")
        if not tool_def.description or not tool_def.description.strip():
            raise ValueError(f"Tool '{tool_def.name}' must have a non-empty description")
        if not isinstance(tool_def.parameters, dict):
            raise ValueError(f"Tool '{tool_def.name}' parameters must be a dict")
        if tool_def.risk_tier not in (0, 1, 2, 3, 4):
            raise ValueError(f"Tool '{tool_def.name}' risk_tier must be between 0 and 4")
        self._tools[tool_def.name] = tool_def
        self._handlers[tool_def.name] = handler
    
    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)
        self._handlers.pop(name, None)

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def get_handler(self, name: str) -> Callable | None:
        return self._handlers.get(name)
        
    def get_all_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def list_tools(self) -> dict[str, ToolDefinition]:
        return dict(self._tools)

    def audit_registry(self) -> dict[str, Any]:
        """Audit all registered tools for schema completeness, risk tiering, and policy coverage."""
        from .policy import LOCAL_EFFECT_TOOLS, IRREVERSIBLE_EXTERNAL_TOOLS
        report: dict[str, Any] = {
            "total_tools": len(self._tools),
            "tier_counts": {0: 0, 1: 0, 2: 0, 3: 0, 4: 0},
            "unmapped_policy": [],
            "missing_description": [],
            "missing_schema": [],
        }
        for name, tdef in self._tools.items():
            report["tier_counts"][tdef.risk_tier] = report["tier_counts"].get(tdef.risk_tier, 0) + 1
            if not tdef.description or not tdef.description.strip():
                report["missing_description"].append(name)
            if not isinstance(tdef.parameters, dict):
                report["missing_schema"].append(name)
            if tdef.risk_tier >= 3:
                if name not in LOCAL_EFFECT_TOOLS and name not in IRREVERSIBLE_EXTERNAL_TOOLS:
                    report["unmapped_policy"].append(name)
        return report
        
    def generate_system_prompt(self, allowed_names: Any | None = None) -> str:
        if not self._tools:
            return "No tools are registered."

        tools = (
            [t for t in self._tools.values() if t.name in allowed_names]
            if allowed_names is not None
            else list(self._tools.values())
        )
        if not tools:
            return "No tools are available for this turn."

        prompt = "REGISTERED TOOLS:\n"
        for t in tools:
            param_names = [
                f"{p}{'*' if p in (t.required_parameters or []) else ''}"
                for p in (t.parameters or {}).keys()
            ]
            params_str = ", ".join(param_names) if param_names else "none"
            flags = []
            if t.is_read_only:
                flags.append("read-only")
            if not t.is_concurrency_safe:
                flags.append("serial-only")
            if t.is_destructive:
                flags.append("DESTRUCTIVE")
            if t.is_long_running:
                flags.append("long-running")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            prompt += f"- {t.name}({params_str}){flag_str}: {t.description}\n"
        return prompt

registry = ToolRegistry()
