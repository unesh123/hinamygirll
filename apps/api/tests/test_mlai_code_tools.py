"""Tests for ML AI Code (code.ml.ai) connector configuration and tools."""

from __future__ import annotations

import httpx
import pytest

from hinaa_api.tools import load_all_tools, registry
from hinaa_api.tools.mlai_code_tools import (
    MlaiListRoutinesParams,
    MlaiRunRoutineParams,
    mlai_list_routines_handler,
    mlai_run_routine_handler,
)


@pytest.mark.asyncio
async def test_mlai_missing_key_fails_closed(monkeypatch):
    monkeypatch.delenv("MLAI_CODE_API_KEY", raising=False)
    monkeypatch.delenv("MLAI_API_KEY", raising=False)
    # Prevent reading .env.local inside handler by monkeypatching Settings
    from hinaa_api.config import Settings
    monkeypatch.setattr("hinaa_api.tools.mlai_code_tools.Settings", lambda: Settings(_env_file=None))
    res = await mlai_list_routines_handler(MlaiListRoutinesParams())
    assert res["status"] == "error"
    assert res["code"] == "MLAI_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_mlai_list_and_run_routine_redacts_secrets(monkeypatch):
    secret = "mlai_sk_supersecret12345"
    from hinaa_api.config import Settings

    fake_settings = Settings(
        MLAI_CODE_API_KEY=secret,
        MLAI_CODE_BASE_URL="https://code.ml.ai",
        _env_file=None,
    )
    monkeypatch.setattr("hinaa_api.tools.mlai_code_tools.Settings", lambda: fake_settings)

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers=None):
            assert url == "https://code.ml.ai/api/routines"
            assert headers["Authorization"] == f"Bearer {secret}"
            return httpx.Response(200, json={"configured": True, "routines": [{"id": "rtn_1", "name": "CI"}]})

        async def post(self, url, headers=None, json=None):
            assert url == "https://code.ml.ai/api/routines/rtn_1/run"
            assert headers["Idempotency-Key"] == "k-123"
            assert json == {"input": "check PR"}
            return httpx.Response(202, json={"status": "started", "runId": "run_1", "jobId": "job_1"})

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    listed = await mlai_list_routines_handler(MlaiListRoutinesParams())
    assert listed["status"] == "success"
    assert listed["count"] == 1

    started = await mlai_run_routine_handler(
        MlaiRunRoutineParams(routine_id="rtn_1", input_text="check PR", idempotency_key="k-123")
    )
    assert started["status"] == "success"
    assert started["runStatus"] == "started"

    # Error path must never leak secret token
    class ErrClient(FakeClient):
        async def get(self, url, headers=None):
            return httpx.Response(500, text=f"Upstream rejected {secret}")

    monkeypatch.setattr(httpx, "AsyncClient", ErrClient)
    err = await mlai_list_routines_handler(MlaiListRoutinesParams())
    assert err["status"] == "error"
    assert secret not in str(err)


def test_mlai_tools_registered_and_policy_covered():
    load_all_tools()
    audit = registry.audit_registry()
    assert audit["unmapped_policy"] == []
    assert registry.get_tool("mlai_list_routines") is not None
    run_tool = registry.get_tool("mlai_run_routine")
    assert run_tool is not None
    assert run_tool.requires_confirmation is True
    assert run_tool.risk_tier == 4
