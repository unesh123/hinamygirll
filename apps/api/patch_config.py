import sys
import re

file_path = "apps/api/hinaa_api/config.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace old AgentRouter fields
old_agent_router_pattern = re.compile(r'    agent_router_api_key:.*?alias="AGENT_ROUTER_ALLOWED_MODELS",\n    \)', re.DOTALL)

new_agent_router_fields = '''    # AgentRouter OpenAI Compatible Profile
    agentrouter_openai_enabled: bool = Field(False, alias="AGENTROUTER_OPENAI_ENABLED")
    agentrouter_openai_base_url: str = Field("https://co.agentrouter.org/v1", alias="AGENTROUTER_OPENAI_BASE_URL")
    agentrouter_openai_api_key: SecretStr | None = Field(None, alias="AGENTROUTER_OPENAI_API_KEY")
    agentrouter_openai_model: str = Field("gpt-5.6-sol", alias="AGENTROUTER_OPENAI_MODEL")
    agentrouter_openai_timeout_seconds: float = Field(30.0, alias="AGENTROUTER_OPENAI_TIMEOUT_SECONDS")
    agentrouter_openai_streaming_enabled: bool = Field(True, alias="AGENTROUTER_OPENAI_STREAMING_ENABLED")

    # AgentRouter Anthropic Compatible Profile
    agentrouter_anthropic_enabled: bool = Field(False, alias="AGENTROUTER_ANTHROPIC_ENABLED")
    agentrouter_anthropic_base_url: str = Field("https://co.agentrouter.org", alias="AGENTROUTER_ANTHROPIC_BASE_URL")
    agentrouter_anthropic_api_key: SecretStr | None = Field(None, alias="AGENTROUTER_ANTHROPIC_API_KEY")
    agentrouter_anthropic_model: str = Field("claude-3-5-sonnet-20241022", alias="AGENTROUTER_ANTHROPIC_MODEL")
    agentrouter_anthropic_timeout_seconds: float = Field(30.0, alias="AGENTROUTER_ANTHROPIC_TIMEOUT_SECONDS")
    agentrouter_anthropic_streaming_enabled: bool = Field(True, alias="AGENTROUTER_ANTHROPIC_STREAMING_ENABLED")
'''

content = old_agent_router_pattern.sub(new_agent_router_fields, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Replaced old agent router fields")
