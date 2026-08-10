from typing import Any, Callable, Awaitable
from pydantic import BaseModel, Field

class ToolParameter(BaseModel):
    type: str
    description: str
    required: bool = True

class ToolDefinition(BaseModel):
    name: str
    display_name: str
    description: str
    parameters: dict[str, dict[str, Any]]
    required_parameters: list[str]
    permission_level: str = "default"
    requires_confirmation: bool = False
    cancellable: bool = True
    voice_aliases: list[str] = []

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable] = {}
    
    def register(self, tool_def: ToolDefinition, handler: Callable):
        self._tools[tool_def.name] = tool_def
        self._handlers[tool_def.name] = handler
    
    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)
        
    def get_all_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())
        
    def generate_system_prompt(self) -> str:
        if not self._tools:
            return "No tools are registered."
            
        prompt = "REGISTERED TOOLS:\n"
        for t in self._tools.values():
            prompt += f"- {t.name}: {t.description}\n"
            prompt += f"  Parameters: {t.parameters}\n"
            prompt += f"  Required: {t.required_parameters}\n"
        return prompt

registry = ToolRegistry()
