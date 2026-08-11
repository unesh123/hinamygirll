import asyncio
from hinaa_api.config import get_settings
from hinaa_api.providers.agent_router import AgentRouterOpenAIProvider
from hinaa_api.prompts import PromptPackage

cfg = get_settings()

async def test_diagnostic_echo():
    print("Testing OpenAI diagnostic_echo...")
    provider = AgentRouterOpenAIProvider(
        api_key=cfg.agentrouter_openai_api_key.get_secret_value(),
        model="gpt-5.6-sol",
        base_url=cfg.agentrouter_openai_base_url
    )
    
    # We test create_live_plan to verify the full parser works with tools!
    from hinaa_api.models import CompanionId, Language
    from hinaa_api.prompts.turn_prompt import build_turn_prompt
    
    # The build_turn_prompt usually needs the tools passed in to the context.
    # For a diagnostic_echo test, let's just use raw _chat_text and mock the prompt.
    prompt = PromptPackage(
        system_instruction="You are a helpful assistant.",
        user_contents=["Please call the diagnostic_echo tool with message 'Hello World'"],
        tools={
            "diagnostic_echo": lambda message: f"Echo: {message}"
        },
        layers={}, prompt_version=1, safety_policy_version=1, companion_profile_version=1,
        fingerprint="", response_depth="short", language="en", personality={}, mood={}
    )
    
    try:
        response = await provider._chat_text(prompt)
        print("Response:", response)
    except Exception as e:
        print(f"Error: {getattr(e, 'code', type(e).__name__)} - {getattr(e, 'message', str(e))}")

asyncio.run(test_diagnostic_echo())
