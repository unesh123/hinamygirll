from hinaa_api.providers.openai_llm import OpenAILLMProvider

class AgentRouterProvider(OpenAILLMProvider):
    """
    Dedicated provider adapter for the Agent Router gateway.
    Ensures strict contract mapping and prevents unsupported parameter passing.
    """

    id = "agent-router"

    def __init__(self, api_key: str, model: str, base_url: str):
        super().__init__(
            key=api_key,
            model=model,
            base_url=base_url,
            provider_id="agent-router"
        )
