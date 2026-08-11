import sys

file_path = "apps/api/hinaa_api/config.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

bad_string = '''    def missing_agent_router_voice_configuration(self) -> list[str]:
        missing: list[str] = []
        if not self.agentrouter_openai_is_configured and not self.agentrouter_anthropic_is_configured:
            missing.append("AGENTROUTER_OPENAI_API_KEY or AGENTROUTER_ANTHROPIC_API_KEY")
        if not self.azure_configured:
            missing.append("AZURE_SPEECH_KEY or AZURE_SPEECH_REGION")
        return missing'''

content = content.replace(bad_string, "")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
