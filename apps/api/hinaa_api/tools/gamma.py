from pydantic import BaseModel, Field
from hinaa_api.tools.registry import registry, ToolDefinition

class CreateGammaPresentationParams(BaseModel):
    topic: str = Field(..., description="The topic for the presentation.")

async def create_gamma_presentation(params: CreateGammaPresentationParams) -> str:
    # Prototype stub: In a real implementation, this would call the Gamma AI API.
    return f"Created a draft Gamma presentation about '{params.topic}'. Opening Gamma workspace... (Prototype)"

create_gamma_presentation_def = ToolDefinition(
    name="create_gamma_presentation",
    display_name="Create Gamma Presentation",
    description="Creates a beautiful, AI-generated presentation using Gamma AI based on a topic.",
    parameters={
        "topic": {"type": "string", "description": "The topic for the presentation."}
    },
    required_parameters=["topic"],
    voice_aliases=["create presentation", "make a slide deck", "gamma"],
    requires_confirmation=True
)

registry.register(create_gamma_presentation_def, create_gamma_presentation)
