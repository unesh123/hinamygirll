import sys

file_path = "apps/api/hinaa_api/services.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("cfg.agentrouter_", "self.settings.agentrouter_")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
