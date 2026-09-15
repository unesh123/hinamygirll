import asyncio
import logging
import os
from typing import Literal
import httpx
from pydantic import BaseModel, Field

from hinaa_api.config import get_settings
from hinaa_api.tools.registry import registry, ToolDefinition

logger = logging.getLogger("hinaa.tools.gamma")


class CreateGammaPresentationParams(BaseModel):
    model_config = {"extra": "ignore"}
    userId: str | None = None
    topic: str = Field("", description="The topic, prompt, or outline for the presentation or document.")
    query: str | None = Field(None, description="Alias for topic.")
    prompt: str | None = Field(None, description="Alias for topic.")
    subject: str | None = Field(None, description="Alias for topic.")
    title: str | None = Field(None, description="Alias for topic.")
    outline: str | None = Field(None, description="Alias for topic.")
    format: Literal["presentation", "document", "webpage"] = Field(
        "presentation", description="The output format: presentation, document, or webpage."
    )
    num_cards: int = Field(
        8, description="Target number of cards/slides to generate (e.g. 5 to 15)."
    )
    export_as: Literal["pptx", "pdf"] | None = Field(
        "pptx", description="Optional file format to export automatically: pptx or pdf."
    )


async def create_gamma_presentation(params: CreateGammaPresentationParams) -> str | dict:
    """Generate a high-quality presentation or document via Gamma AI."""
    settings = get_settings()
    api_key: str | None = None
    if settings.gamma_ai_api_key:
        api_key = settings.gamma_ai_api_key.get_secret_value()
    if not api_key:
        api_key = os.getenv("GAMMA_AI_API_KEY") or os.getenv("gamma_ai_API_KEY")

    effective_topic = (
        params.topic.strip()
        or (params.query or "").strip()
        or (params.prompt or "").strip()
        or (params.subject or "").strip()
        or (params.title or "").strip()
        or (params.outline or "").strip()
        or "Presentation Outline"
    )

    if not api_key:
        logger.info("Gamma AI unconfigured; creating a labelled local slide outline PDF.")
        from .pdf_generate import pdf_generate_handler, GeneratePDFParams
        pdf_res = await pdf_generate_handler(GeneratePDFParams(
            topic=effective_topic,
            title=params.title or f"{effective_topic.title()} Document",
            category=params.format.capitalize(),
            userId=params.userId,
            content=(params.outline or effective_topic) + "\n\nLocal slide outline. Gamma is not configured; this PDF is not a generated PowerPoint presentation.",
        ))
        if isinstance(pdf_res, dict) and pdf_res.get("downloadUrl"):
            return {**pdf_res, "format": "pdf", "requestedFormat": params.export_as,
                    "fallback": True, "fallbackReason": "GAMMA_NOT_CONFIGURED",
                    "summary": "Created a local slide outline PDF. Gamma is not configured; no PPTX was generated."}
        return "Gamma AI is not configured. Please add `GAMMA_AI_API_KEY` to your `apps/api/.env.local` file."

    base_url = (settings.gamma_ai_base_url or "https://public-api.gamma.app/v1.0").rstrip("/")
    create_url = f"{base_url}/generations"

    headers = {
        "X-API-KEY": api_key.strip(),
        "Content-Type": "application/json",
    }

    payload: dict[str, object] = {
        "inputText": effective_topic,
        "textMode": "generate",
        "format": params.format,
        "numCards": max(1, min(params.num_cards, 30)),
        "themeId": "gamma-dark",
    }
    if params.export_as and params.format == "presentation":
        payload["exportAs"] = params.export_as

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(create_url, headers=headers, json=payload)
            if resp.status_code not in (200, 201):
                logger.error("Gamma creation failed (%d): %s", resp.status_code, resp.text)
                return f"Gamma AI request failed ({resp.status_code}): {resp.text}"

            data = resp.json()
            generation_id = data.get("generationId")
            if not generation_id:
                return "Gamma AI accepted the request but did not return a generation ID."

            # Poll for completion (up to 30 seconds)
            poll_url = f"{base_url}/generations/{generation_id}"
            for _ in range(10):
                await asyncio.sleep(3)
                poll_resp = await client.get(poll_url, headers=headers)
                if poll_resp.status_code == 200:
                    poll_data = poll_resp.json()
                    status = poll_data.get("status")
                    if status == "completed":
                        gamma_url = poll_data.get("gammaUrl") or f"https://gamma.app/docs/{generation_id}"
                        export_url = poll_data.get("exportUrl")
                        output = [
                            f"✨ **Created your Gamma {params.format.capitalize()}!**",
                            f"📌 **Topic:** {effective_topic}",
                            f"🔗 **Live Link:** [{gamma_url}]({gamma_url})",
                        ]
                        if export_url:
                            output.append(f"📥 **Download ({params.export_as.upper()}):** [{export_url}]({export_url})")
                        return "\n".join(output)
                    if status == "failed":
                        err_msg = poll_data.get("error", "Unknown error")
                        return f"Gamma generation failed: {err_msg}"

            # If still generating after polling window, return tracking link
            return (
                f"🎨 **Your Gamma {params.format} is being generated!**\n"
                f"Job ID: `{generation_id}`\n"
                f"View your decks anytime at [Gamma Workspace](https://gamma.app)."
            )
    except httpx.TimeoutException:
        return "Gamma AI request timed out. Please try again."
    except Exception as e:
        logger.exception("Error during Gamma presentation creation")
        return f"An error occurred while generating with Gamma AI: {e}"


create_gamma_presentation_def = ToolDefinition(
    name="create_gamma_presentation",
    display_name="Create Presentation / Doc (Gamma AI)",
    description=(
        "Creates a beautiful, AI-generated presentation, document, or webpage using Gamma AI. "
        "Use whenever the user asks to create a presentation, slides, deck, document, or webpage."
    ),
    parameters={
        "topic": {
            "type": "string",
            "description": "The topic, title, or outline of the presentation or document.",
        },
        "format": {
            "type": "string",
            "enum": ["presentation", "document", "webpage"],
            "description": "The output format. Default is presentation.",
        },
        "num_cards": {
            "type": "integer",
            "description": "Target number of slides/cards (e.g. 8).",
        },
        "export_as": {
            "type": "string",
            "enum": ["pptx", "pdf"],
            "description": "Export format: pptx or pdf.",
        },
    },
    required_parameters=["topic"],
    voice_aliases=[
        "create presentation",
        "make a slide deck",
        "make slides",
        "gamma presentation",
        "create a document",
    ],
    requires_confirmation=True,
)

registry.register(create_gamma_presentation_def, create_gamma_presentation)
