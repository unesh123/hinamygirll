from __future__ import annotations

import pytest

from hinaa_api.evaluation.offline_suite import run_offline_mock_eval


@pytest.mark.asyncio
async def test_offline_eval_corpus_passes_on_mock() -> None:
    report = await run_offline_mock_eval()
    assert report["passed"] is True
    assert report["count"] >= 10
