import sys
import re

file_path = "apps/api/hinaa_api/services.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("from .providers.agent_router import AgentRouterProvider", "from .providers.agent_router import AgentRouterOpenAIProvider, AgentRouterAnthropicProvider")

# Update routing
old_router = '''            return AgentRouterProvider(
                active_agent_router_key.get_secret_value(),
                model,
                base_url=active_agent_router_base_url,
            )'''

new_router = '''            if cfg.agentrouter_anthropic_is_configured() and "claude" in model.lower():
                return AgentRouterAnthropicProvider(
                    api_key=cfg.agentrouter_anthropic_api_key.get_secret_value(),
                    model=model,
                    base_url=cfg.agentrouter_anthropic_base_url,
                )
            elif cfg.agentrouter_openai_is_configured():
                return AgentRouterOpenAIProvider(
                    api_key=cfg.agentrouter_openai_api_key.get_secret_value(),
                    model=model,
                    base_url=cfg.agentrouter_openai_base_url,
                )
            else:
                raise LLMConfigurationError("No AgentRouter protocol configured.")'''

content = content.replace(old_router, new_router)
content = content.replace(" | AgentRouterProvider)", " | AgentRouterOpenAIProvider | AgentRouterAnthropicProvider)")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Replaced AgentRouterProvider usage")
