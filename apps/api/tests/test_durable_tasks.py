from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hinaa_api.persistence.db import get_session_factory
from hinaa_api.persistence.task_service import TaskService


def test_durable_task_lifecycle_and_checkpoints(client: TestClient):
    alice_headers = {"X-HINAA-Dev-User": "alice"}

    # 1. Create a task with custom steps
    create_body = {
        "goal": "Build full stack authentication with Clerk",
        "taskType": "feature",
        "priority": 10,
        "reasoningMode": "deep",
        "steps": [
            {"title": "Setup Clerk config", "description": "Add keys to env"},
            {"title": "Implement middleware", "description": "Protect routes"},
            {"title": "Test auth flow", "description": "Verify sign-in/out"},
        ],
        "metadata": {"environment": "staging"},
    }
    create_resp = client.post("/v1/tasks", json=create_body, headers=alice_headers)
    assert create_resp.status_code == 200, create_resp.text
    task = create_resp.json()
    task_id = task["id"]
    assert task["goal"] == "Build full stack authentication with Clerk"
    assert task["status"] == "active"
    assert len(task["steps"]) == 3
    assert task["checkpointVersion"] >= 1
    assert task["currentStepId"] == task["steps"][0]["id"]

    # 2. Get task detail
    get_resp = client.get(f"/v1/tasks/{task_id}", headers=alice_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == task_id

    # 3. List checkpoints
    cp_resp = client.get(f"/v1/tasks/{task_id}/checkpoints", headers=alice_headers)
    assert cp_resp.status_code == 200
    checkpoints = cp_resp.json()
    assert len(checkpoints) >= 1
    assert checkpoints[0]["version"] >= 1

    # 4. Complete step 0
    step0_id = task["steps"][0]["id"]
    comp_resp = client.post(
        f"/v1/tasks/{task_id}/steps/{step0_id}/complete",
        json={"outputArtifactIds": ["art-001"]},
        headers=alice_headers,
    )
    assert comp_resp.status_code == 200
    updated_task = comp_resp.json()
    assert updated_task["steps"][0]["status"] == "completed"
    assert updated_task["currentStepId"] == task["steps"][1]["id"]
    assert updated_task["checkpointVersion"] > task["checkpointVersion"]

    # 5. Steer the task
    steer_resp = client.post(
        f"/v1/tasks/{task_id}/steer",
        json={"instruction": "Ensure SSR compatibility for Clerk components"},
        headers=alice_headers,
    )
    assert steer_resp.status_code == 200
    steered_task = steer_resp.json()
    assert "Ensure SSR compatibility for Clerk components" in str(steered_task["metadata"].get("constraints"))

    # 6. Events check
    events_resp = client.get(f"/v1/tasks/{task_id}/events", headers=alice_headers)
    assert events_resp.status_code == 200
    events_data = events_resp.json()
    event_types = [e["eventType"] for e in events_data["events"]]
    assert "TASK_CREATED" in event_types
    assert "STEP_COMPLETED" in event_types
    assert "USER_STEERED" in event_types

    # 7. Cancel task
    cancel_resp = client.post(
        f"/v1/tasks/{task_id}/cancel",
        json={"reason": "User changed requirements"},
        headers=alice_headers,
    )
    assert cancel_resp.status_code == 200
    cancelled_task = cancel_resp.json()
    assert cancelled_task["status"] == "cancelled"
    assert cancelled_task["steps"][1]["status"] == "cancelled"


def test_continue_task_resumes_without_repeating_completed_steps(client: TestClient):
    alice_headers = {"X-HINAA-Dev-User": "alice"}
    create_body = {
        "goal": "Multi-step database migration and data seeding",
        "steps": [
            {"title": "Run schema migration"},
            {"title": "Seed baseline accounts"},
            {"title": "Verify constraints"},
        ],
    }
    task = client.post("/v1/tasks", json=create_body, headers=alice_headers).json()
    task_id = task["id"]
    step1_id = task["steps"][0]["id"]
    step2_id = task["steps"][1]["id"]
    step3_id = task["steps"][2]["id"]

    # Complete step 1
    client.post(f"/v1/tasks/{task_id}/steps/{step1_id}/complete", headers=alice_headers)

    # Call continue
    cont_resp = client.post(f"/v1/tasks/{task_id}/continue", headers=alice_headers)
    assert cont_resp.status_code == 200
    continued = cont_resp.json()
    # Step 1 should remain completed, currentStepId must be Step 2
    assert continued["steps"][0]["status"] == "completed"
    assert continued["currentStepId"] == step2_id
    assert continued["steps"][1]["status"] == "active"

    # Complete remaining steps
    client.post(f"/v1/tasks/{task_id}/steps/{step2_id}/complete", headers=alice_headers)
    client.post(f"/v1/tasks/{task_id}/steps/{step3_id}/complete", headers=alice_headers)

    final_task = client.get(f"/v1/tasks/{task_id}", headers=alice_headers).json()
    assert final_task["status"] == "completed"
    assert all(s["status"] == "completed" for s in final_task["steps"])


def test_active_task_resolution(client: TestClient):
    alice_headers = {"X-HINAA-Dev-User": "alice"}

    # No task active -> resolve returns no candidate
    res1 = client.post("/v1/tasks/resolve", json={"text": "continue please"}, headers=alice_headers).json()
    assert res1["intent"] == "continue_task"
    assert res1["task"] is None

    # Irrelevant text -> intent is new_request
    res_irr = client.post("/v1/tasks/resolve", json={"text": "what is the weather today"}, headers=alice_headers).json()
    assert res_irr["intent"] == "new_request"

    # Create task
    task = client.post(
        "/v1/tasks",
        json={"goal": "Implement webhook listener", "conversationId": "conv-123"},
        headers=alice_headers,
    ).json()

    # Resolve with conversation match
    res2 = client.post(
        "/v1/tasks/resolve",
        json={"text": "keep going", "conversationId": "conv-123"},
        headers=alice_headers,
    ).json()
    assert res2["intent"] == "continue_task"
    assert res2["task"]["id"] == task["id"]
    assert res2["confidence"] >= 0.7


def test_task_owner_isolation(client: TestClient):
    alice_headers = {"X-HINAA-Dev-User": "alice"}
    bob_headers = {"X-HINAA-Dev-User": "bob"}

    # Alice creates a task
    alice_task = client.post(
        "/v1/tasks",
        json={"goal": "Alice secret task"},
        headers=alice_headers,
    ).json()
    task_id = alice_task["id"]

    # Bob lists tasks: Alice task should not appear
    bob_tasks = client.get("/v1/tasks", headers=bob_headers).json()
    assert all(t["id"] != task_id for t in bob_tasks)

    # Bob gets Alice task: 404
    assert client.get(f"/v1/tasks/{task_id}", headers=bob_headers).status_code == 404

    # Bob tries to complete step or cancel: 404
    assert client.post(f"/v1/tasks/{task_id}/cancel", headers=bob_headers).status_code == 404
    assert client.post(f"/v1/tasks/{task_id}/steer", json={"instruction": "hack"}, headers=bob_headers).status_code == 404


def test_task_service_recovery_across_instances(client: TestClient):
    settings = client.app.state.settings
    factory = get_session_factory(settings)

    service1 = TaskService(factory)
    task = service1.create_task(
        "alice",
        "Resilient background computation",
        steps=[
            {"title": "Phase 1: Ingestion"},
            {"title": "Phase 2: Processing"},
            {"title": "Phase 3: Export"},
        ],
    )
    task_id = task["id"]
    step1_id = task["steps"][0]["id"]

    # Step 1 is started (active)
    service1.continue_task("alice", task_id)
    t1 = service1.get_task("alice", task_id)
    assert t1["steps"][0]["status"] == "active"

    # Simulate server reboot: new TaskService instance without in-memory state
    service2 = TaskService(factory)
    recovered = service2.recover_interrupted_tasks("alice")
    assert len(recovered) >= 1
    rec_task = next(t for t in recovered if t["id"] == task_id)
    assert rec_task["status"] == "waiting_user"
    # Interrupted active step was reset to pending with failure recorded
    rec_step = next(s for s in rec_task["steps"] if s["id"] == step1_id)
    assert rec_step["status"] == "pending"
    assert rec_step["failureReason"] == "interrupted_by_server_restart"

    # Now resume work with service2
    resumed = service2.continue_task("alice", task_id)
    assert resumed["status"] == "active"
    assert resumed["currentStepId"] == step1_id
    assert resumed["steps"][0]["status"] == "active"


def test_task_checkpoint_rollback(client: TestClient):
    alice_headers = {"X-HINAA-Dev-User": "alice"}
    task = client.post(
        "/v1/tasks",
        json={
            "goal": "Verify rollback integrity",
            "steps": [
                {"title": "Initial Step"},
                {"title": "Second Step"},
                {"title": "Third Step"},
            ],
        },
        headers=alice_headers,
    ).json()
    task_id = task["id"]
    step1_id = task["steps"][0]["id"]
    step2_id = task["steps"][1]["id"]

    # Complete step 1
    cp1_task = client.post(f"/v1/tasks/{task_id}/steps/{step1_id}/complete", headers=alice_headers).json()
    version_after_step1 = cp1_task["checkpointVersion"]

    # Complete step 2
    cp2_task = client.post(f"/v1/tasks/{task_id}/steps/{step2_id}/complete", headers=alice_headers).json()
    assert cp2_task["checkpointVersion"] > version_after_step1
    assert cp2_task["steps"][1]["status"] == "completed"

    # Rollback to version_after_step1
    rb_resp = client.post(
        f"/v1/tasks/{task_id}/rollback",
        json={"version": version_after_step1},
        headers=alice_headers,
    )
    assert rb_resp.status_code == 200
    rolled_back = rb_resp.json()
    # Step 1 completed, Step 2 reset to pending
    assert rolled_back["steps"][0]["status"] == "completed"
    assert rolled_back["steps"][1]["status"] == "pending"


def test_task_runtime_hardening_lease_fencing_and_stale_worker_rejection(client: TestClient):
    alice_headers = {"X-HINAA-Dev-User": "alice"}
    task = client.post(
        "/v1/tasks",
        json={"goal": "Run fenced background work", "steps": [{"title": "External action"}]},
        headers=alice_headers,
    ).json()

    claim_a = client.post(
        "/v1/tasks/claim",
        json={"workerId": "worker-a", "leaseSeconds": 60},
        headers=alice_headers,
    )
    assert claim_a.status_code == 200, claim_a.text
    leased = claim_a.json()
    assert leased["id"] == task["id"]
    assert leased["lease"]["workerId"] == "worker-a"
    assert leased["lease"]["leaseId"]
    assert leased["lease"]["fencingToken"] >= 1

    claim_b = client.post(
        "/v1/tasks/claim",
        json={"workerId": "worker-b", "leaseSeconds": 60},
        headers=alice_headers,
    )
    assert claim_b.status_code == 200
    assert claim_b.json() is None

    step_id = leased["steps"][0]["id"]
    stale = client.post(
        f"/v1/tasks/{task['id']}/steps/{step_id}/complete-with-lease",
        json={"leaseId": "wrong-lease", "fencingToken": leased["lease"]["fencingToken"]},
        headers=alice_headers,
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_WORKER_FENCE"

    ok = client.post(
        f"/v1/tasks/{task['id']}/steps/{step_id}/complete-with-lease",
        json={
            "leaseId": leased["lease"]["leaseId"],
            "fencingToken": leased["lease"]["fencingToken"],
            "outputArtifactIds": ["artifact-lease-ok"],
        },
        headers=alice_headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "completed"


def test_task_runtime_hardening_rejects_dag_cycle(client: TestClient):
    alice_headers = {"X-HINAA-Dev-User": "alice"}
    response = client.post(
        "/v1/tasks",
        json={
            "goal": "Invalid cyclic plan",
            "steps": [
                {"id": "A", "title": "A", "dependencies": ["B"]},
                {"id": "B", "title": "B", "dependencies": ["A"]},
            ],
        },
        headers=alice_headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "TASK_DAG_CYCLE"


def test_task_runtime_hardening_side_effect_journal_is_idempotent(client: TestClient):
    alice_headers = {"X-HINAA-Dev-User": "alice"}
    task = client.post(
        "/v1/tasks",
        json={"goal": "Generate image exactly once", "steps": [{"title": "Call provider"}]},
        headers=alice_headers,
    ).json()
    step_id = task["steps"][0]["id"]
    payload = {
        "stepId": step_id,
        "idempotencyKey": f"{task['id']}:{step_id}:magnific",
        "provider": "magnific",
        "operationType": "image_upscale",
        "requestPayload": {"assetId": "asset-123", "scale": 2},
    }
    first = client.post(f"/v1/tasks/{task['id']}/side-effects", json=payload, headers=alice_headers)
    assert first.status_code == 200, first.text
    journal = first.json()
    assert journal["status"] == "PLANNED"
    assert journal["metadata"]["atLeastOnce"] is True
    assert journal["metadata"]["exactlyOnce"] is False

    duplicate = client.post(f"/v1/tasks/{task['id']}/side-effects", json=payload, headers=alice_headers)
    assert duplicate.status_code == 200
    assert duplicate.json()["operationId"] == journal["operationId"]

    accepted = client.post(
        f"/v1/tasks/side-effects/{journal['operationId']}/provider-accepted",
        json={"providerOperationId": "provider-job-1", "responsePayload": {"status": "accepted"}},
        headers=alice_headers,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "PROVIDER_ACCEPTED"
    assert accepted.json()["providerOperationId"] == "provider-job-1"


def test_task_runtime_hardening_checkpoint_has_schema_metadata(client: TestClient):
    alice_headers = {"X-HINAA-Dev-User": "alice"}
    task = client.post(
        "/v1/tasks",
        json={"goal": "Checkpoint schema metadata", "steps": [{"title": "One"}]},
        headers=alice_headers,
    ).json()

    checkpoint = task["checkpoint"]
    assert checkpoint["schemaVersion"] == 1
    assert checkpoint["runtimeVersion"] == "task-runtime-hardening-v1"
    assert checkpoint["planRevision"] >= 1

    pause = client.post(
        f"/v1/tasks/{task['id']}/pause",
        json={"reason": "waiting on operator"},
        headers=alice_headers,
    )
    assert pause.status_code == 200
    assert pause.json()["status"] == "paused"

    resume = client.post(f"/v1/tasks/{task['id']}/resume", headers=alice_headers)
    assert resume.status_code == 200
    assert resume.json()["status"] == "active"
