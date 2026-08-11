import sys

file_path = "apps/api/hinaa_api/config.py"
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

settings_end_idx = 0
for i, line in enumerate(lines):
    if "@lru_cache" in line:
        settings_end_idx = i
        break

new_methods = '''
    @property
    def local_stt_configured(self) -> bool:
        return bool(self.local_stt_command)

    @property
    def local_tts_configured(self) -> bool:
        return bool(self.local_tts_command)

    def missing_agent_router_voice_configuration(self) -> list[str]:
        missing: list[str] = []
        if not self.agentrouter_openai_is_configured and not self.agentrouter_anthropic_is_configured:
            missing.append("AGENTROUTER_OPENAI_API_KEY or AGENTROUTER_ANTHROPIC_API_KEY")
        if not self.azure_configured:
            missing.append("AZURE_SPEECH_KEY or AZURE_SPEECH_REGION")
        return missing
'''

# insert before settings_end_idx
new_lines = lines[:settings_end_idx] + [new_methods] + lines[settings_end_idx:]

with open(file_path, 'w', encoding='utf-8') as f:
    f.write("".join(new_lines))
