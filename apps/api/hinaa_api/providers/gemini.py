from __future__ import annotations

import json
from time import perf_counter

from google import genai
from google.genai import types
from pydantic import ValidationError

from ..errors import HinaaError, safe_error_text
from ..models import AssistantTurnPlan, CompanionId, Language
from .base import ProviderResult

SYSTEM_PROMPT = """You are HINAA, an explicitly artificial companion. Reply concisely in the
user's script and language mix. Be warm and helpful without claiming consciousness, dependency,
jealousy, or exclusivity. Return only the strict AssistantTurnPlan JSON schema. Tool requests must
always be empty. Never emit files, URLs, code, bones, blendshapes, permissions, or executable data.
Use restrained symbolic emotion and at most one major gesture."""


class GeminiLLMProvider:
    id = "gemini"

    def __init__(self, key: str, model: str) -> None:
        self._key = key
        self._model = model

    async def create_plan(
        self,
        text: str,
        companion_id: CompanionId,
        language: Language,
        history: tuple[tuple[str, str], ...],
    ) -> ProviderResult[AssistantTurnPlan]:
        started = perf_counter()
        history_text = "\n".join(f"{role}: {content}" for role, content in history[-8:])
        contents = (
            f"Companion profile: {companion_id}. Preferred language: {language}.\n"
            f"Bounded session context:\n{history_text or '(new session)'}\n"
            f"Untrusted user message:\n<user>{text}</user>"
        )
        client = genai.Client(api_key=self._key)
        chunks: list[str] = []
        try:
            stream = await client.aio.models.generate_content_stream(
                model=self._model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.45,
                    max_output_tokens=1800,
                    response_mime_type="application/json",
                    response_json_schema=AssistantTurnPlan.model_json_schema(),
                ),
            )
            async for response in stream:
                if response.text:
                    chunks.append(response.text)
            raw = "".join(chunks)
            plan = AssistantTurnPlan.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError) as error:
            raise HinaaError(
                "MODEL_RESPONSE_INVALID",
                "The model returned an invalid safe response plan.",
                502,
                True,
            ) from error
        except HinaaError:
            raise
        except Exception as error:
            redacted = safe_error_text(error, [self._key])
            lowered = redacted.lower()
            if "api key" in lowered or "401" in lowered or "403" in lowered:
                raise HinaaError(
                    "PROVIDER_KEY_INVALID",
                    "Gemini needs its backend connection fixed.",
                    503,
                    user_action_required=True,
                ) from error
            if "429" in lowered or "quota" in lowered:
                raise HinaaError(
                    "PROVIDER_RATE_LIMIT", "Gemini is busy right now.", 429, True
                ) from error
            raise HinaaError(
                "PROVIDER_UNAVAILABLE", "Gemini is unavailable safely.", 502, True
            ) from error
        finally:
            await client.aio.aclose()
        return ProviderResult(
            plan, f"{self.id}:{self._model}", int((perf_counter() - started) * 1000)
        )
