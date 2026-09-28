import pytest
from starlette.testclient import TestClient
from hinaa_api.main import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_companion_briefing_endpoint(client):
    response = client.get("/v1/companion/briefing")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "greeting" in data
    assert "timeOfDay" in data
    assert "suggestions" in data
    assert len(data["suggestions"]) >= 1


def test_vision_observe_endpoint_invalid_data(client):
    # Missing or invalid payload
    response = client.post("/v1/vision/observe", json={"frame": "not_an_image", "query": "hello"})
    assert response.status_code == 200
    data = response.json()
    # LiveVisionService returns clean error dict instead of 500
    assert "ok" in data


def test_swarm_execution_endpoint_structure(client):
    response = client.post(
        "/v1/agents/swarm/execute",
        json={
            "mission": "Quantum Key Distribution",
            "tasks": ["research"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "deliverables" in data
    assert "research" in data["deliverables"]
