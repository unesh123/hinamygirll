import sys
import re

file_path = "apps/api/hinaa_api/config.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Just remove the rest of the old agent router methods
content = re.sub(r'    def agent_router_allowed_models\(self\) -> list\[str\]:.*?def resolve_agent_router_model.*?def missing_agent_router_voice_configuration\(self\) -> list\[str\]:.*?missing\.append\("AGENT_ROUTER_API_KEY"\)\n        return missing\n', '', content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
