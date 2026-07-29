from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    retryable: bool
    userActionRequired: bool
    correlationId: str


@dataclass(slots=True)
class HinaaError(Exception):
    code: str
    message: str
    status_code: int = 500
    retryable: bool = False
    user_action_required: bool = False


async def hinaa_error_handler(request: Request, error: HinaaError) -> JSONResponse:
    body = ErrorBody(
        code=error.code,
        message=error.message,
        retryable=error.retryable,
        userActionRequired=error.user_action_required,
        correlationId=request.state.correlation_id,
    )
    return JSONResponse(
        status_code=error.status_code,
        content=body.model_dump(),
        media_type="application/problem+json",
        headers={"X-Correlation-ID": request.state.correlation_id},
    )


async def unhandled_error_handler(request: Request, _error: Exception) -> JSONResponse:
    body = ErrorBody(
        code="INTERNAL_ERROR",
        message="The request failed safely. Try mock mode or retry.",
        retryable=True,
        userActionRequired=False,
        correlationId=request.state.correlation_id,
    )
    return JSONResponse(
        status_code=500,
        content=body.model_dump(),
        media_type="application/problem+json",
        headers={"X-Correlation-ID": request.state.correlation_id},
    )


def safe_error_text(value: Any, secrets: list[str]) -> str:
    text = str(value)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text[:500]
