import httpx
from dotenv import dotenv_values

env = dotenv_values(".env.local")

# 1. EXPLABS
try:
    r = httpx.post(
        "https://api.experientiallabs.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {env.get('EXPLABS_API_KEY')}"},
        json={"model": env.get("EXPLABS_MODEL", "claude-opus-5.5"), "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5},
        timeout=8.0
    )
    print("EXPLABS:", r.status_code, r.text[:80])
except Exception as e:
    print("EXPLABS error:", e)

# 2. DEEPSEEK_PKAY
try:
    r = httpx.post(
        f"{env.get('DEEPSEEK_PKAY_BASE_URL')}/chat/completions",
        headers={"Authorization": f"Bearer {env.get('DEEPSEEK_PKAY_API_KEY')}"},
        json={"model": env.get("DEEPSEEK_PKAY_MODEL", "deepseek-v4-flash"), "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5},
        timeout=8.0
    )
    print("DEEPSEEK_PKAY:", r.status_code, r.text[:80])
except Exception as e:
    print("DEEPSEEK_PKAY error:", e)

# 3. APMIX
try:
    r = httpx.post(
        f"{env.get('APMIX_AI_BASE_URL')}/chat/completions",
        headers={"Authorization": f"Bearer {env.get('APMIX_AI_API_KEY')}"},
        json={"model": env.get("APMIX_AI_MODEL", "claude-sonnet-4-6-free"), "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5},
        timeout=8.0
    )
    print("APMIX:", r.status_code, r.text[:80])
except Exception as e:
    print("APMIX error:", e)
