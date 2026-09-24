import asyncio
import httpx
import time

async def main():
    async with httpx.AsyncClient() as client:
        print("Executing image_generate...")
        res = await client.post("http://127.0.0.1:8000/v1/tools/execute", json={
            "toolName": "image_generate",
            "parameters": {
                "prompt": "one anime image of an original white-haired sorceress in a moonlit fantasy city",
                "count": 1,
                "mode": "fast",
                "strategy": "VARIATIONS"
            }
        }, timeout=10.0)
        
        data = res.json()
        print("Execute Response status:", data.get("status"))
        if data.get("status") == "error":
            print("Error:", data.get("error"))
            print("Details:", str(data.get("details"))[:1000])
        
        job_id = data.get("data", {}).get("job_id") or data.get("job_id")
        
        if not job_id:
            print("No job ID returned!")
            return
            
        print(f"Polling job {job_id}...")
        while True:
            poll = await client.get(f"http://127.0.0.1:8000/v1/tools/poll?job_id={job_id}")
            poll_data = poll.json()
            print(f"Status: {poll_data.get('status')} | Total: {poll_data.get('total')} | Images: {len(poll_data.get('images', []))}")
            if poll_data.get('status') in ['success', 'error']:
                print("Final data:", poll_data)
                break
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
