from __future__ import annotations

from pydantic import BaseModel

from hinaa_api.tools.registry import registry


class _FutureAnnotatedParams(BaseModel):
    query: str


async def _future_annotated_handler(params: _FutureAnnotatedParams) -> dict[str, object]:
    # Accessing .query intentionally reproduces the prior raw-dict crash when
    # postponed annotations were not resolved by the shared dispatcher.
    return {"status": "success", "data": {"received": params.query}}


def test_execute_tool_resolves_postponed_pydantic_annotation(client, monkeypatch) -> None:
    monkeypatch.setitem(registry._handlers, "youtube_playback_request", _future_annotated_handler)

    response = client.post(
        "/v1/tools/execute",
        json={
            "toolName": "youtube_playback_request",
            "parameters": {"query": "Heavenly Phonk"},
            "confirmed": True,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success", "data": {"received": "Heavenly Phonk"}}
