from fastapi import APIRouter

from ..config import Settings
from ..providers.bivia import BiviaDecisionRequest, decide


def create_bivia_router(settings: Settings) -> APIRouter:
    router = APIRouter(tags=["decisions"])

    @router.post("/v1/decisions/bivia")
    @router.post("/api/v1/decisions/bivia")
    async def bivia_decision(body: BiviaDecisionRequest):
        return await decide(settings, body)

    return router
