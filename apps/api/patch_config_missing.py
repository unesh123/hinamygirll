import sys

file_path = "apps/api/hinaa_api/config.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# I will add the missing_agent_router_voice_configuration method
new_method = '''
    def missing_agent_router_voice_configuration(self) -> list[str]:
        missing: list[str] = []
        if not self.agentrouter_openai_is_configured and not self.agentrouter_anthropic_is_configured:
            missing.append("AGENTROUTER_OPENAI_API_KEY or AGENTROUTER_ANTHROPIC_API_KEY")
        if not self.azure_configured:
            missing.append("AZURE_SPEECH_KEY or AZURE_SPEECH_REGION")
        return missing
'''

content += new_method

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
