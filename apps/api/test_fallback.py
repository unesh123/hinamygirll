import asyncio
from hinaa_api.services import ConversationService
from hinaa_api.config import get_settings

async def test_fallback():
    settings = get_settings()
    service = ConversationService(settings)
    
    # We will pass a bad API key or just let it time out to test fallback
    # Wait, we need to temporarily corrupt deepgram key or url
    old_key = settings.deepgram_api_key
    settings.deepgram_base_url = "https://invalid.api.deepgram.com"
    
    res = await service.synthesize_text("Hello there, testing fallback", companion_id="hiro", mode="cloud")
    print(f"Synthesize size: {len(res.value)}")

asyncio.run(test_fallback())
