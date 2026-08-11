import asyncio, json, uuid, sys
from httpx import AsyncClient

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SESSION_ID = "test-session-" + uuid.uuid4().hex[:8]

async def test():
    async with AsyncClient(timeout=60) as client:
        # Test 1: Mock chat stream
        print("--- Test 1: Mock chat stream ---")
        r = await client.post("http://127.0.0.1:8000/v1/conversations/turns:stream", json={
            "text": "Hello Hinaa, how are you?",
            "providerMode": "mock",
            "companionId": "hinaa",
            "sessionId": SESSION_ID
        })
        print("Status:", r.status_code)
        lines = [l for l in r.text.splitlines() if l.strip()]
        for line in lines[:10]:
            print(" ", repr(line[:120]))
        print(f"  Total stream lines: {len(lines)}")
        types_found = set()
        for l in lines:
            try:
                obj = json.loads(l)
                types_found.add(obj.get("type", "?"))
            except Exception:
                pass
        print("  Event types:", sorted(types_found))
        # Correct check: mock stream uses text.delta and plan
        assert "text.delta" in types_found or "plan" in types_found, f"Expected text.delta or plan, got: {types_found}"
        print("  PASS: Mock stream contains expected events")

        # Test 2: Image generate job
        print()
        print("--- Test 2: Image generate job (count=1, fast) ---")
        r2 = await client.post("http://127.0.0.1:8000/v1/tools/execute", json={
            "toolName": "image_generate",
            "parameters": {
                "prompt": "a beautiful mountain landscape, anime style",
                "count": 1,
                "mode": "fast"
            },
            "userId": "test-user",
            "conversationId": "test-conv"
        })
        print("Execute status:", r2.status_code)
        data2 = r2.json()
        print("execute response:", str(data2)[:300])
        job_id = data2.get("job_id")
        if job_id:
            print(f"  job_id: {job_id}")
            for i in range(20):
                await asyncio.sleep(5)
                r3 = await client.get("http://127.0.0.1:8000/v1/tools/poll?job_id=" + job_id)
                d = r3.json()
                imgs = len(d.get("images", []))
                st = d.get("status")
                total = d.get("total")
                print(f"  [{(i+1)*5}s] poll: status={st} total={total} images={imgs}")
                if st in ("success", "error"):
                    if imgs:
                        print("  PASS: Image generated successfully")
                        for img in d.get("images", []):
                            print("  IMAGE URL:", img.get("url","?")[:100])
                    elif st == "error":
                        print("  ERROR:", d.get("error", "?"))
                    break
        else:
            print("No job_id returned — execute failed:", r2.status_code, data2)

asyncio.run(test())
