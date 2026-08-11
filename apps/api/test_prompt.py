import asyncio
from hinaa_api.config import Settings
from hinaa_api.models import TurnRequest
from hinaa_api.prompts.turn_prompt import build_turn_prompt

request = TurnRequest(
    sessionId='test-session-123',
    text='How do I integrate ComfyUI into HINAA?',
    companionId='hinaa',
    language='en-US',
    providerMode='local',
    responseMode='professional'
)

settings = Settings()

prompt = build_turn_prompt(
    request=request,
    history=(),
    settings=settings,
    interaction_mode='rest'
)

with open('output_prompt.txt', 'w', encoding='utf-8') as f:
    f.write(prompt.system_instruction)
