import sys
import re

file_path = "apps/api/hinaa_api/config.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the methods!
# Let's just find and replace the agent_router_configured and other methods.
old_methods = re.compile(r'    def agent_router_configured\(self\) -> bool:.*?def active_agent_router_base_url\(self\) -> str \| None:.*?return value', re.DOTALL)

new_methods = '''    def agentrouter_openai_is_configured(self) -> bool:
        return bool(self.agentrouter_openai_enabled and self.agentrouter_openai_api_key and self.agentrouter_openai_api_key.get_secret_value())

    def agentrouter_anthropic_is_configured(self) -> bool:
        return bool(self.agentrouter_anthropic_enabled and self.agentrouter_anthropic_api_key and self.agentrouter_anthropic_api_key.get_secret_value())'''

content = old_methods.sub(new_methods, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
