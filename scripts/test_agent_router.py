import os
import sys
import asyncio
import argparse
from urllib.parse import urlparse
from pathlib import Path
from dotenv import load_dotenv
import time
import json

import httpx

# Force run from project root to find .env.local correctly
project_root = Path(__file__).resolve().parent.parent
env_path = project_root / "apps" / "api" / ".env.local"
load_dotenv(env_path)

def sanitize_headers(headers):
    return {k: ("***" if k.lower() == "authorization" else v) for k, v in headers.items()}

async def stage_a_config_validation():
    print("\n=== STAGE A: Configuration Validation ===")
    api_key = os.environ.get("AGENT_ROUTER_API_KEY")
    base_url = os.environ.get("AGENT_ROUTER_BASE_URL", "").rstrip("/")
    allowlist = os.environ.get("AGENT_ROUTER_ALLOWED_MODELS")
    
    if not api_key:
        print("[CONFIG_MISSING] AGENT_ROUTER_API_KEY is missing.")
        sys.exit(1)
    if not base_url:
        print("[CONFIG_MISSING] AGENT_ROUTER_BASE_URL is missing.")
        sys.exit(1)
    if not allowlist:
        print("[CONFIG_MISSING] AGENT_ROUTER_ALLOWED_MODELS is missing.")
        sys.exit(1)

    parsed = urlparse(base_url)
    if parsed.scheme != "https":
        print("[BASE_URL_INVALID] Base URL must use HTTPS.")
        sys.exit(1)
    if parsed.username or parsed.password:
        print("[BASE_URL_INVALID] Base URL must not contain embedded credentials.")
        sys.exit(1)
    if parsed.query or parsed.fragment:
        print("[BASE_URL_INVALID] Base URL must not contain query parameters or fragments.")
        sys.exit(1)
    
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    print("Configuration valid:")
    print(f"- Scheme: {parsed.scheme}")
    print(f"- Hostname: {parsed.hostname}")
    print(f"- API Key: {'present (hidden)' if api_key else 'missing'}")
    print(f"- Model Allowlist: {allowlist}")
    
    return api_key, base_url, allowlist.split(",")

async def stage_b_model_discovery(api_key, base_url):
    print("\n=== STAGE B: Model Discovery ===")
    models_endpoint = f"{base_url}/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    print(f"Requesting GET {models_endpoint}")
    models = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(models_endpoint, headers=headers)
            
            if resp.status_code in (401, 403):
                print(f"[AUTHENTICATION_FAILED] Status {resp.status_code}")
                sys.exit(1)
            elif resp.status_code == 404:
                print(f"[MODEL_DISCOVERY_UNSUPPORTED] Provider does not support /v1/models")
                return []
            elif resp.is_error:
                print(f"[DNS_OR_NETWORK_FAILED] Status {resp.status_code}")
                sys.exit(1)
            
            data = resp.json()
            models = [m.get("id") for m in data.get("data", [])]
            print(f"Discovered {len(models)} models.")
            print(f"Wire IDs (first 10): {models[:10]}")
    except httpx.TimeoutException:
        print("[PROVIDER_TIMEOUT] Timeout fetching models.")
        sys.exit(1)
    except Exception as e:
        print(f"[DNS_OR_NETWORK_FAILED] Exception: {type(e).__name__}")
        sys.exit(1)
    
    return models

async def stage_c_minimal_chat(api_key, base_url, model_id):
    print(f"\n=== STAGE C: Minimal Chat (Model: {model_id}) ===")
    chat_endpoint = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }
    
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Say 'hello' in plain text."}],
        "max_tokens": 10,
        "stream": True,
    }
    
    print(f"Sending stream request to {chat_endpoint}")
    start_time = time.time()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", chat_endpoint, headers=headers, json=payload) as resp:
                if resp.status_code in (401, 403):
                    print(f"[AUTHENTICATION_FAILED] Status {resp.status_code}")
                    sys.exit(1)
                elif resp.status_code == 404:
                    print(f"[MODEL_NOT_FOUND] Status {resp.status_code}")
                    sys.exit(1)
                elif resp.status_code == 400:
                    print(f"[PARAMETER_UNSUPPORTED] Status {resp.status_code}")
                    err = await resp.aread()
                    print(f"Sanitized Error: {err.decode('utf-8', errors='ignore')[:200]}")
                    sys.exit(1)
                elif resp.status_code == 429:
                    print(f"[QUOTA_OR_BILLING_FAILED] Status {resp.status_code}")
                    sys.exit(1)
                elif resp.is_error:
                    print(f"[DNS_OR_NETWORK_FAILED] Status {resp.status_code}")
                    sys.exit(1)
                
                first_event = None
                first_text_delta = None
                content_accum = []
                usage = None
                
                async for line in resp.aiter_lines():
                    line_str = line.strip()
                    if not line_str:
                        continue
                    if line_str.startswith("data:"):
                        data = line_str.removeprefix("data:").strip()
                        if data == "[DONE]":
                            break
                        if first_event is None:
                            first_event = time.time()
                            print(f"First event: +{first_event - start_time:.2f}s")
                        
                        try:
                            chunk = json.loads(data)
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    if first_text_delta is None:
                                        first_text_delta = time.time()
                                        print(f"First text: +{first_text_delta - start_time:.2f}s | Content: {repr(content)}")
                                    content_accum.append(content)
                            
                            if "usage" in chunk and chunk["usage"]:
                                usage = chunk["usage"]
                        except json.JSONDecodeError:
                            print(f"[STREAM_FORMAT_INVALID] Unparseable line: {data[:50]}")
                            sys.exit(1)
                
                completion = time.time()
                full_text = "".join(content_accum)
                
                if not full_text:
                    print(f"[RESPONSE_EMPTY] No text generated.")
                    sys.exit(1)
                    
                print(f"Completion: +{completion - start_time:.2f}s")
                print(f"Final output: {repr(full_text)}")
                if usage:
                    print(f"Usage: {usage}")
                else:
                    print("Usage: (not returned by provider)")
                
                print("\n[SUCCESS] Chat verified.")
                
    except httpx.TimeoutException:
        print("[PROVIDER_TIMEOUT] Request timed out.")
        sys.exit(1)
    except Exception as e:
        print(f"[DNS_OR_NETWORK_FAILED] Exception: {type(e).__name__}")
        sys.exit(1)

async def run_test(args):
    allow_test = os.environ.get("HINAA_ALLOW_AGENT_ROUTER_TEST")
    confirm = os.environ.get("HINAA_AGENT_ROUTER_TEST_CONFIRM")

    if allow_test != "1" or confirm != "I_UNDERSTAND_THIS_MAY_COST_MONEY":
        print("Test gated: Must set HINAA_ALLOW_AGENT_ROUTER_TEST=1 and HINAA_AGENT_ROUTER_TEST_CONFIRM=I_UNDERSTAND_THIS_MAY_COST_MONEY")
        sys.exit(0)

    # Clear gates from process environment
    del os.environ["HINAA_ALLOW_AGENT_ROUTER_TEST"]
    del os.environ["HINAA_AGENT_ROUTER_TEST_CONFIRM"]

    api_key, base_url, allowlist = await stage_a_config_validation()

    if not args.no_discovery:
        await stage_b_model_discovery(api_key, base_url)
    else:
        print("\n=== STAGE B: Model Discovery (SKIPPED via --no-discovery) ===")

    if not args.discovery_only:
        if args.model not in allowlist:
            print(f"\n[CONFIG_MISSING] Selected model '{args.model}' is not in AGENT_ROUTER_ALLOWED_MODELS.")
            sys.exit(1)
        await stage_c_minimal_chat(api_key, base_url, args.model)
    else:
        print("\n=== STAGE C: Minimal Chat (SKIPPED via --discovery-only) ===")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent Router Preflight Smoke Test")
    parser.add_argument("--model", type=str, required=True, help="Exact model ID to test")
    parser.add_argument("--discovery-only", action="store_true", help="Stop after discovery")
    parser.add_argument("--no-discovery", action="store_true", help="Skip discovery stage")
    args = parser.parse_args()
    
    asyncio.run(run_test(args))
