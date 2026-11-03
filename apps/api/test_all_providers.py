import os, sys, httpx
from dotenv import dotenv_values

env = dotenv_values(".env.local")

providers = [
    {
        "name": "Gemini",
        "url": f"https://generativelanguage.googleapis.com/v1beta/models/{env.get('GEMINI_MODEL', 'gemini-2.0-flash')}:generateContent?key={env.get('GEMINI_API_KEY')}",
        "method": "POST",
        "json": {"contents": [{"parts": [{"text": "Say ok"}]}]},
        "headers": {"Content-Type": "application/json"}
    },
    {
        "name": "AgentRouter (Bynara)",
        "url": f"{env.get('AGENT_ROUTER_BASE_URL', 'https://api.bynara.com/v1')}/chat/completions",
        "method": "POST",
        "json": {"model": env.get("AGENT_ROUTER_MODEL", "agnes-2.5-flash"), "messages": [{"role": "user", "content": "Say ok"}], "max_tokens": 5},
        "headers": {"Authorization": f"Bearer {env.get('AGENT_ROUTER_API_KEY')}"}
    },
    {
        "name": "CodeCraft",
        "url": f"{env.get('CODE_CRAFTAI_BASE_URL', 'https://codecraftapi.com/v1')}/chat/completions",
        "method": "POST",
        "json": {"model": env.get("CODECRAFT_MODEL", "claude-fable-5"), "messages": [{"role": "user", "content": "Say ok"}], "max_tokens": 5},
        "headers": {"Authorization": f"Bearer {env.get('CODE_CRAFT_API_KEY')}"}
    },
    {
        "name": "PGSGrove",
        "url": f"{env.get('PGSGROVE_BASE_URL', 'https://api.pgsgrove.com/v1')}/chat/completions",
        "method": "POST",
        "json": {"model": env.get("PGSGROVE_MODEL", "glm-5.3-flash"), "messages": [{"role": "user", "content": "Say ok"}], "max_tokens": 5},
        "headers": {"Authorization": f"Bearer {env.get('PGSGROVE_API_KEY')}"}
    },
    {
        "name": "TokenTable",
        "url": f"{env.get('TOKENTABLE_BASE_URL', 'https://tokentable.asia/v1')}/chat/completions",
        "method": "POST",
        "json": {"model": env.get("TOKENTABLE_MODEL", "auto"), "messages": [{"role": "user", "content": "Say ok"}], "max_tokens": 5},
        "headers": {"Authorization": f"Bearer {env.get('TOKENTABLE_API_KEY')}"}
    },
    {
        "name": "SeekAI",
        "url": f"{env.get('SEEKAI_BASE_URL', 'https://seekai.cc/v1')}/chat/completions",
        "method": "POST",
        "json": {"model": env.get("SEEKAI_MODEL", "glm-5.3-flash"), "messages": [{"role": "user", "content": "Say ok"}], "max_tokens": 5},
        "headers": {"Authorization": f"Bearer {env.get('SEEKAI_API_KEY')}"}
    },
    {
        "name": "Cavoti",
        "url": f"{env.get('CAVOTI_AI_BASE_URL', 'https://cavoti.com/v1')}/chat/completions",
        "method": "POST",
        "json": {"model": env.get("CAVOTI_AI_MODEL", "claude-fable-5"), "messages": [{"role": "user", "content": "Say ok"}], "max_tokens": 5},
        "headers": {"Authorization": f"Bearer {env.get('CAVOTI_AI_API_KEY')}"}
    },
    {
        "name": "XKiro (Mistral Free)",
        "url": f"{env.get('XKIRO_BASE_URL', 'https://api.xkiro.com/v1')}/chat/completions",
        "method": "POST",
        "json": {"model": "mistralai/ministral-14b", "messages": [{"role": "user", "content": "Say ok"}], "max_tokens": 5},
        "headers": {"Authorization": f"Bearer {env.get('XKIRO_API_KEY')}"}
    },
    {
        "name": "XKiro (Cohere Free)",
        "url": f"{env.get('XKIRO_BASE_URL', 'https://api.xkiro.com/v1')}/chat/completions",
        "method": "POST",
        "json": {"model": "cohere/command-a", "messages": [{"role": "user", "content": "Say ok"}], "max_tokens": 5},
        "headers": {"Authorization": f"Bearer {env.get('XKIRO_API_KEY')}"}
    },
    {
        "name": "XKiro (Qwen Free)",
        "url": f"{env.get('XKIRO_BASE_URL', 'https://api.xkiro.com/v1')}/chat/completions",
        "method": "POST",
        "json": {"model": env.get("XKIRO_MODEL", "qwen/qwen3.8-max:free"), "messages": [{"role": "user", "content": "Say ok"}], "max_tokens": 5},
        "headers": {"Authorization": f"Bearer {env.get('XKIRO_API_KEY')}"}
    }
]

for p in providers:
    name = p["name"]
    try:
        r = httpx.request(p["method"], p["url"], headers=p["headers"], json=p.get("json"), timeout=10.0)
        status = r.status_code
        if status == 200:
            print(f"[{name}] SUCCESS 200", flush=True)
        else:
            msg = r.text[:80].replace("\n", " ")
            print(f"[{name}] FAIL {status}: {msg}", flush=True)
    except Exception as e:
        print(f"[{name}] ERROR: {e}", flush=True)
