import httpx
from dotenv import dotenv_values

env = dotenv_values(".env.local")
key = env.get("XKIRO_API_KEY")
base_url = env.get("XKIRO_BASE_URL", "https://api.xkiro.com/v1")

r = httpx.get(f"{base_url}/models", headers={"Authorization": f"Bearer {key}"})
qwen_models = [m["id"] for m in r.json().get("data", []) if "qwen" in m["id"].lower()]

print(f"Testing {len(qwen_models)} Qwen models...")
working = []
for model in qwen_models:
    try:
        res = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": "Say 1"}], "max_tokens": 5},
            timeout=8.0,
        )
        if res.status_code == 200:
            content = res.json()["choices"][0]["message"]["content"]
            print(f"  [SUCCESS] {model}: {content.strip()}")
            working.append(model)
        else:
            err = res.json().get("error", {})
            print(f"  [FAIL] {model}: {res.status_code} ({err.get('message', res.text)[:80]})")
    except Exception as e:
        print(f"  [ERROR] {model}: {e}")

print("Working models:", working)
