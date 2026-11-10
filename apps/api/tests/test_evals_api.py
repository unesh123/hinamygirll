"""
API tests for HINAA OS Agent Evaluation & Benchmarks (/api/evals/*).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hinaa_api.main import create_app
from hinaa_api.config import get_settings


@pytest.fixture
def client():
    app = create_app(get_settings())
    with TestClient(app) as test_client:
        yield test_client


def test_evals_api_endpoints(client):
    # Test GET /api/evals/latest
    res = client.get("/api/evals/latest")
    assert res.status_code == 200
    data = res.json()
    assert "total_cases" in data
    assert "pass_rate" in data
    assert data["pass_rate"] >= 90.0

    # Test POST /api/evals/run
    res_run = client.post("/api/evals/run")
    assert res_run.status_code == 200
    run_data = res_run.json()
    assert run_data["total_cases"] == data["total_cases"]
    assert run_data["overall_score"] >= 90.0
