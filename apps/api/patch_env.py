import re

env_file = "apps/api/.env.local"
with open(env_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the old API key safely
match = re.search(r'AGENT_ROUTER_API_KEY=(.+)', content)
if match:
    api_key = match.group(1)
    
    new_vars = f"""
AGENTROUTER_OPENAI_ENABLED=true
AGENTROUTER_OPENAI_BASE_URL=https://co.agentrouter.org/v1
AGENTROUTER_OPENAI_API_KEY={api_key}
AGENTROUTER_OPENAI_MODEL=gpt-5.6-sol
AGENTROUTER_OPENAI_TIMEOUT_SECONDS=30.0
AGENTROUTER_OPENAI_STREAMING_ENABLED=true

AGENTROUTER_ANTHROPIC_ENABLED=true
AGENTROUTER_ANTHROPIC_BASE_URL=https://co.agentrouter.org
AGENTROUTER_ANTHROPIC_API_KEY={api_key}
AGENTROUTER_ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
AGENTROUTER_ANTHROPIC_TIMEOUT_SECONDS=30.0
AGENTROUTER_ANTHROPIC_STREAMING_ENABLED=true
"""
    with open(env_file, 'a', encoding='utf-8') as f:
        f.write("\n" + new_vars)
    print("Added new AgentRouter variables to .env.local")
else:
    print("Could not find AGENT_ROUTER_API_KEY")
