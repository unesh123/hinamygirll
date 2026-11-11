"""Articul8's bounded decision API. This is not a chat-completions provider."""
from __future__ import annotations

import asyncio
import time
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..config import Settings
from ..errors import HinaaError

_SHARED_CLIENTS: dict[int, httpx.AsyncClient] = {}


def _shared_client() -> httpx.AsyncClient:
    try:
        loop_key = id(asyncio.get_running_loop())
    except RuntimeError:
        loop_key = 0
    client = _SHARED_CLIENTS.get(loop_key)
    if client is None or getattr(client, "is_closed", True):
        client = httpx.AsyncClient(timeout=httpx.Timeout(connect=3.0, read=25.0, write=10.0, pool=30.0))
        _SHARED_CLIENTS[loop_key] = client
    return client


class BiviaDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    state: str = Field(min_length=1, max_length=20000)
    question: str = Field(min_length=1, max_length=1000)
    outcomes: list[str] = Field(min_length=2, max_length=20)
    mode: Literal["fast", "deep"] = "fast"
    allow_abstain: bool = True

    @field_validator("outcomes")
    @classmethod
    def validate_outcomes(cls, values: list[str]) -> list[str]:
        values = [value.strip() for value in values]
        if any(not value or len(value) > 500 for value in values) or len(set(values)) != len(values):
            raise ValueError("Outcomes must be distinct, nonempty strings of at most 500 characters")
        return values


class BiviaDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    status: Literal["answered", "abstained"]
    value: str | None
    probability: float | None = Field(default=None, ge=0, le=1)
    abstain_reason: str | None = None


async def decide(settings: Settings, request: BiviaDecisionRequest, *, client: httpx.AsyncClient | None = None) -> dict:
    key = settings.active_articul8_key
    if key is None:
        raise HinaaError("BIVIA_NOT_CONFIGURED", "Add an Articul8 Bivia API key in the backend configuration.", 503, user_action_required=True)
    # Reuse the existing event-loop HTTP pool. Bound the entire call, including
    # connection setup, and never retry rejected credentials or bill twice.
    deadline = 8.0 if request.mode == "fast" else 20.0
    started = time.perf_counter()
    try:
        response = await asyncio.wait_for((client or _shared_client()).post(
            f"{settings.active_articul8_base_url}/decide",
            headers={"apikey": key.get_secret_value(), "Accept": "application/json"},
            json=request.model_dump(), timeout=httpx.Timeout(deadline, connect=3.0),
            follow_redirects=False,
        ), timeout=deadline)
    except (TimeoutError, httpx.TimeoutException) as error:
        raise HinaaError("BIVIA_TIMEOUT", "Bivia did not answer within the decision deadline.", 504, retryable=True) from error
    except httpx.HTTPError as error:
        raise HinaaError("BIVIA_UNREACHABLE", "The Bivia decision service could not be reached.", 502, retryable=True) from error
    if response.status_code in {401, 403}:
        raise HinaaError("BIVIA_AUTH_REJECTED", "Articul8 rejected the configured Bivia credential. Update the API key in backend settings.", 502, user_action_required=True)
    if response.status_code == 429:
        raise HinaaError("BIVIA_RATE_LIMITED", "Bivia is rate limited. Try again later.", 429, retryable=True)
    if response.status_code != 200:
        raise HinaaError("BIVIA_UPSTREAM_ERROR", f"Bivia returned HTTP {response.status_code}.", 502, retryable=response.status_code >= 500)
    try:
        result = BiviaDecisionResponse.model_validate(response.json())
        if result.status == "answered" and (result.value not in request.outcomes or result.probability is None):
            raise ValueError("Answer is outside the bounded decision contract")
        if result.status == "abstained" and result.value is not None:
            raise ValueError("Abstention must not return an actionable answer")
    except (ValueError, TypeError) as error:
        raise HinaaError("BIVIA_INVALID_RESPONSE", "Bivia returned an invalid decision; no action was authorized.", 502) from error
    return {**result.model_dump(), "provider": "articul8", "mode": request.mode,
            "latencyMs": round((time.perf_counter() - started) * 1000),
            "authorizesExecution": False}
