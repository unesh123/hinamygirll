import asyncio
from hinaa_api.config import get_settings
from hinaa_api.providers.agent_router import AgentRouterOpenAIProvider, AgentRouterAnthropicProvider

cfg = get_settings()

class MockPrompt:
    def __init__(self, system_instruction, user_contents):
        self.system_instruction = system_instruction
        self.user_contents = user_contents
        self.tools = {}

async def test_openai():
    print("Testing OpenAI...")
    provider = AgentRouterOpenAIProvider(
        api_key=cfg.agentrouter_openai_api_key.get_secret_value(),
        model=cfg.agentrouter_openai_model,
        base_url=cfg.agentrouter_openai_base_url
    )
    prompt = MockPrompt("You are a helpful assistant.", ["Reply with exactly: AGENTROUTER_OPENAI_OK"])
    
    try:
        async for chunk in provider._stream_text(prompt):
            print(chunk, end="")
        print("\nOpenAI Stream successful.")
    except Exception as e:
        print(f"\nOpenAI Error: {getattr(e, 'code', type(e).__name__)} - {getattr(e, 'message', str(e))}")

async def test_anthropic():
    print("\nTesting Anthropic...")
    provider = AgentRouterAnthropicProvider(
        api_key=cfg.agentrouter_anthropic_api_key.get_secret_value(),
        model=cfg.agentrouter_anthropic_model,
        base_url=cfg.agentrouter_anthropic_base_url
    )
    prompt = MockPrompt("You are a helpful assistant.", ["Reply with exactly: AGENTROUTER_ANTHROPIC_OK"])
    
    try:
        async for chunk in provider._stream_text(prompt):
            print(chunk, end="")
        print("\nAnthropic Stream successful.")
    except Exception as e:
        print(f"\nAnthropic Error: {getattr(e, 'code', type(e).__name__)} - {getattr(e, 'message', str(e))}")

async def main():
    await test_openai()
    await test_anthropic()

asyncio.run(main())
