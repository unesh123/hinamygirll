from fastapi.testclient import TestClient

from hinaa_api.tools.browser_agent import approval_events


def test_browser_agent_approval_records_decision_without_hidden_resume(client: TestClient) -> None:
    approval_id = "browser-agent-test-approval"
    approval_events[approval_id] = {
        "approved": None,
        "status": "pending",
        "action": "type",
        "args": {"selector": "#search", "text": "safe test", "submit": False},
    }
    try:
        response = client.post("/v1/tools/approve", json={"approval_id": approval_id, "approved": True})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["approved"] is True
        assert body["action"] == "type"
        assert body["resumeSupported"] is False
        assert "no browser input was performed automatically" in body["nextStep"]
        assert approval_events[approval_id]["status"] == "approved"
    finally:
        approval_events.pop(approval_id, None)
