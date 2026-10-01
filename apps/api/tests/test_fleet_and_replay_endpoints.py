"""
Unit tests for Fleet Management and Canonical Event Bus Replay endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from hinaa_api.main import app
from hinaa_api.fleet.device_fleet import get_fleet_manager, DeviceNode
from hinaa_api.harness.canonical_event_bus import get_canonical_event_bus, HinaCanonicalEvent


@pytest.fixture
def client():
    return TestClient(app)


def test_fleet_list_devices(client):
    response = client.get("/v1/fleet/devices")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["totalOnline"] >= 1
    assert any(d["device_id"] == "dev_local_primary" for d in data["devices"])


def test_fleet_heartbeat(client):
    mgr = get_fleet_manager()
    mgr.register_device(
        DeviceNode(
            device_id="dev_test_node",
            name="Test Worker",
            os_platform="Ubuntu 24.04",
        )
    )

    response = client.post("/v1/fleet/devices/heartbeat", json={"device_id": "dev_test_node", "current_tasks_count": 2})
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Non-existent node
    bad_resp = client.post("/v1/fleet/devices/heartbeat", json={"device_id": "dev_unknown", "current_tasks_count": 0})
    assert bad_resp.status_code == 200
    assert bad_resp.json()["status"] == "not_found"


def test_harness_replay_endpoint(client):
    bus = get_canonical_event_bus()
    test_run_id = "run_test_replay_endpoint"

    ev1 = HinaCanonicalEvent(
        run_id=test_run_id,
        action="open_application",
        resource="chrome",
        policy_decision="allow",
        latency_ms=45.2,
    )
    ev2 = HinaCanonicalEvent(
        run_id=test_run_id,
        action="execute_script",
        resource="dom",
        policy_decision="allow",
        latency_ms=120.0,
    )
    bus.publish_event(ev1)
    bus.publish_event(ev2)

    # Replay
    replay_resp = client.get(f"/v1/harness/runs/{test_run_id}/replay")
    assert replay_resp.status_code == 200
    data = replay_resp.json()
    assert data["status"] == "success"
    assert data["runId"] == test_run_id
    assert data["totalSteps"] == 2
    assert data["timeline"][0]["action"] == "open_application"
    assert data["timeline"][1]["action"] == "execute_script"

    # Full Trace
    trace_resp = client.get(f"/v1/harness/runs/{test_run_id}/trace")
    assert trace_resp.status_code == 200
    t_data = trace_resp.json()
    assert t_data["status"] == "success"
    assert len(t_data["trace"]["events"]) == 2
