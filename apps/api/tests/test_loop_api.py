"""
API tests for HINAA OS Loop Engineering endpoints (/api/loop/*).
"""

import sys
import time

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


def test_loop_pause_unknown_task(client):
    res = client.post("/api/loop/pause/loop_does_not_exist")
    assert res.status_code == 200
    assert res.json()["ok"] is False


def test_loop_pause_running_task_publishes_event(client):
    from hinaa_api.harness.loop_events import EVENT_BUS

    payload = {
        "goal_title": "Slow gate to pause",
        "verification_command": [sys.executable, "-c", "import time; time.sleep(1.5)"],
        "max_turns": 5,
    }
    res = client.post("/api/loop/start", json=payload)
    assert res.status_code == 200
    task_id = res.json()["task_id"]

    res = client.post(f"/api/loop/pause/{task_id}")
    assert res.status_code == 200
    assert res.json() == {"ok": True, "task_id": task_id, "status": "PAUSED"}

    # The terminal event is published from the cancelled task on the server loop.
    events: list[str] = []
    for _ in range(50):
        events = [e["event_type"] for e in EVENT_BUS.history(task_id)]
        if "loop_paused" in events:
            break
        time.sleep(0.1)
    assert "loop_paused" in events


def test_loop_turn_verified_events_in_history(client, tmp_path):
    from hinaa_api.harness.loop_events import EVENT_BUS

    payload = {
        "goal_title": "Gate history",
        "verification_command": [sys.executable, "-c", "import sys; sys.exit(0)"],
        "max_turns": 1,
    }
    res = client.post("/api/loop/start", json=payload)
    assert res.status_code == 200
    task_id = res.json()["task_id"]

    events: list[str] = []
    for _ in range(50):
        events = [e["event_type"] for e in EVENT_BUS.history(task_id)]
        if events and events[-1] in {"loop_finished", "loop_failed"}:
            break
        time.sleep(0.1)
    assert "turn_verified" in events
    assert events[-1] == "loop_finished"
