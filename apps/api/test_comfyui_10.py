import asyncio
from httpx import AsyncClient
import time

async def test_job(client: AsyncClient, count: int):
    print(f"Testing generation of {count} image(s)...")
    execute_response = await client.post(
        "http://127.0.0.1:8000/v1/tools/execute",
        json={
            "tool_name": "image_generate",
            "parameters": {
                "prompt": f"A beautiful test image for {count} generations, masterpiece, highres",
                "count": count,
                "mode": "fast"
            }
        },
        timeout=30.0
    )
    job_id = execute_response.json().get("job_id")
    print(f"Job started: {job_id}")
    
    start_time = time.time()
    while True:
        poll_response = await client.get(f"http://127.0.0.1:8000/v1/tools/poll?job_id={job_id}")
        data = poll_response.json()
        print(f"[{time.time()-start_time:.1f}s] Status: {data.get('status')} | Total: {data.get('total')} | Images: {len(data.get('images', []))}")
        if data.get('status') in ['success', 'error']:
            print(f"Final Output for {count}: {data}")
            break
        await asyncio.sleep(2)

async def main():
    async with AsyncClient() as client:
        await test_job(client, 10)

asyncio.run(main())
