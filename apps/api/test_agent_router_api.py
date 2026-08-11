import asyncio
from httpx import AsyncClient
import time
import json
import uuid

async def test_agent_router_api():
    print("Testing /v1/conversations/turns:stream with AgentRouter...")
    async with AsyncClient(timeout=60.0) as client:
        # Note: the backend must have provider_mode="agent-router" or we pass it
        payload = {
            "sessionId": str(uuid.uuid4()),
            "text": "Call diagnostic_echo with message 'Hello AgentRouter'",
            "companionId": "hinaa",
            "language": "en-US",
            "providerMode": "agent-router",
            "brainModel": "gpt-5.6-sol"
        }
        
        async with client.stream("POST", "http://127.0.0.1:8000/v1/conversations/turns:stream", json=payload, headers={"X-HINAA-Dev-User": "testuser"}) as response:
            if response.status_code != 200:
                print(f"Error {response.status_code}: {await response.aread()}")
                return
            
            async for line in response.aiter_lines():
                if line:
                    print(line)

asyncio.run(test_agent_router_api())
