"""
API tests for HINAA OS Loop Engineering endpoints (/api/loop/*).
"""

import sys
import pytest
from fastapi.testclient import TestClient

from hinaa_api.main import create_app
from hinaa_api.config import get_settings


@pytest.fixture
def client():
    app = create_app(get_settings())
    with TestClient(app) as test_client:
        yield test_client


def test_loop_api_start_and_status(client, tmp_path):
    # Start a quick loop task
    payload = {
        "goal_title": "Test Gate Execution",
        "description": "Verifies exit code 0 gate",
        "verification_command": [sys.executable, "-c", "import sys; sys.exit(0)"],
        "max_turns": 2,
    }
    res = client.post("/api/loop/start", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    task_id = data["task_id"]
    assert task_id.startswith("loop_")

    # Check tasks list
    res_tasks = client.get("/api/loop/tasks")
    assert res_tasks.status_code == 200
    tasks_data = res_tasks.json()
    assert "tasks" in tasks_data
    task_ids = [t["task_id"] for t in tasks_data["tasks"]]
    assert task_id in task_ids

    # Query status
    res_status = client.get(f"/api/loop/status/{task_id}")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["task_id"] == task_id
    assert status_data["status"] in ("RUNNING", "COMPLETED")
