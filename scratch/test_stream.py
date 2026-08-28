import asyncio
import json
import httpx
import traceback

async def main():
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "sessionId": "test-session-123",
                "text": "Explain how React Server Components work in detail.",
                "companionId": "hinaa",
                "providerMode": "cx-gateway",
                "language": "mixed"
            }
            print(f"Requesting: {payload['text']}")
            async with client.stream("POST", "http://127.0.0.1:8000/v1/conversations/turns:stream", json=payload, timeout=30.0) as response:
                print("Status:", response.status_code)
                async for line in response.aiter_lines():
                    if line:
                        print("LINE:", line[:100])
                        data = json.loads(line)
                        if data.get("type") == "plan":
                            print("Spoken Text:", data["plan"]["spokenText"])
                            print("Display Text length:", len(data["plan"]["displayText"]))
                            print("Response Mode:", data["plan"].get("responseMode", "UNKNOWN"))
                        elif data.get("type") == "error":
                            print("ERROR:", data)
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
