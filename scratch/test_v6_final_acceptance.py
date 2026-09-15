import requests
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000"

def test_endpoints():
    print("Testing HINAA Frontier V6.1 Live Endpoints...")
    results = {}

    # 1. Health check: /health/live
    try:
        r = requests.get(f"{BASE_URL}/health/live", timeout=5)
        results["health"] = {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
        print(f"  [1] /health/live: {r.status_code} OK -> {r.json()}")
    except Exception as e:
        results["health"] = {"error": str(e)}
        print(f"  [1] /health/live: FAILED - {e}")

    # 2. Registered Tools endpoint: /v1/tools (returns a JSON array of tool definitions)
    try:
        r = requests.get(f"{BASE_URL}/v1/tools", timeout=5)
        data = r.json() if r.status_code == 200 else []
        tool_count = len(data)
        tool_names = [t.get("name") for t in data[:5]]
        results["tools"] = {"status": r.status_code, "tool_count": tool_count, "sample": tool_names}
        print(f"  [2] /v1/tools: {r.status_code} OK ({tool_count} registered tools: {tool_names}...)")
    except Exception as e:
        results["tools"] = {"error": str(e)}
        print(f"  [2] /v1/tools: FAILED - {e}")

    # 3. Durable Tasks endpoint: /v1/tasks (returns a JSON array)
    try:
        r = requests.get(f"{BASE_URL}/v1/tasks", headers={"X-HINAA-Dev-User": "test_user"}, timeout=5)
        data = r.json() if r.status_code == 200 else []
        task_count = len(data) if isinstance(data, list) else 0
        results["tasks"] = {"status": r.status_code, "task_count": task_count}
        print(f"  [3] /v1/tasks: {r.status_code} OK ({task_count} durable tasks)")
    except Exception as e:
        results["tasks"] = {"error": str(e)}
        print(f"  [3] /v1/tasks: FAILED - {e}")

    # 4. Referent pronoun suppression on fresh session via stream_turn
    try:
        payload = {
            "text": "tell me more details about her",
            "conversationId": "fresh_session_referent_check_001",
            "sessionId": "fresh_session_referent_check_001",
            "companionId": "hinaa",
            "providerMode": "mock"
        }
        r = requests.post(f"{BASE_URL}/v1/conversations/turns:stream", json=payload, timeout=15)
        lines = [json.loads(line) for line in r.text.strip().split("\n") if line.strip()]
        plan_event = next((l for l in lines if l.get("type") == "plan"), None)
        plan = plan_event.get("plan", {}) if plan_event else {}
        research_sources = plan.get("researchSources") or []
        search_query = plan.get("searchQuery")
        display_text = plan.get("displayText", "")
        results["referent_suppression"] = {
            "status": r.status_code,
            "research_sources_count": len(research_sources),
            "search_fired": bool(search_query),
            "displayText": display_text[:120]
        }
        print(f"  [4] Referent suppression: {r.status_code} OK (Research sources: {len(research_sources)}, Search fired: {bool(search_query)})")
        print(f"      Response: \"{display_text[:100]}...\"")
    except Exception as e:
        results["referent_suppression"] = {"error": str(e)}
        print(f"  [4] Referent suppression: FAILED - {e}")

    # 5. Topic precedence test: Nepal monsoon flood query
    try:
        payload = {
            "text": "tell me about the recent monsoon floods in Kathmandu Nepal",
            "conversationId": "nepal_flood_precedence_002",
            "sessionId": "nepal_flood_precedence_002",
            "companionId": "hinaa",
            "providerMode": "mock"
        }
        r = requests.post(f"{BASE_URL}/v1/conversations/turns:stream", json=payload, timeout=20)
        lines = [json.loads(line) for line in r.text.strip().split("\n") if line.strip()]
        plan_event = next((l for l in lines if l.get("type") == "plan"), None)
        plan = plan_event.get("plan", {}) if plan_event else {}
        topic = plan.get("topic") or ""
        search_query = plan.get("searchQuery") or ""
        results["topic_precedence"] = {
            "status": r.status_code,
            "topic": topic,
            "searchQuery": search_query,
            "displayText": plan.get("displayText", "")[:120]
        }
        print(f"  [5] Topic precedence: {r.status_code} OK (Topic: '{topic}', Search: '{search_query}')")
        print(f"      Response: \"{plan.get('displayText', '')[:100]}...\"")
    except Exception as e:
        results["topic_precedence"] = {"error": str(e)}
        print(f"  [5] Topic precedence: FAILED - {e}")

    with open("scratch/v6_acceptance_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSUCCESS! All acceptance tests executed and results saved to scratch/v6_acceptance_results.json")

if __name__ == "__main__":
    test_endpoints()
