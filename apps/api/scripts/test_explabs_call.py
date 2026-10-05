"""Verification script for Experiential Labs gateway test call.

Makes a test call to https://api.experientiallabs.ai/v1/chat/completions
with model 'claude-opus-5.5' using the EXPLABS_API_KEY environment variable.
"""

from __future__ import annotations

import os
import sys
import json
import httpx


def main() -> None:
    # Support loading from .env.local or hinaa_api settings
    try:
        from dotenv import load_dotenv
        load_dotenv(".env.local")
        load_dotenv(".env")

    except ImportError:
        pass

    api_key = os.getenv("EXPLABS_API_KEY", "").strip() or os.getenv("EXPERIMENTAL_LABS_API_KEY", "").strip()
    if not api_key:
        try:
            from hinaa_api.config import get_settings
            settings = get_settings()
            if settings.explabs_api_key:
                api_key = settings.explabs_api_key.get_secret_value()
        except Exception:
            pass

    if not api_key:
        print("\n[ERROR] EXPLABS_API_KEY environment variable is not set.", file=sys.stderr)
        print("Please create an API key under Settings -> API Keys and export it:\n", file=sys.stderr)
        print("  In PowerShell:", file=sys.stderr)
        print('    $env:EXPLABS_API_KEY = "your-api-key-here"\n', file=sys.stderr)
        print("  Or add it to apps/api/.env or .env.local:\n", file=sys.stderr)
        print('    EXPLABS_API_KEY="your-api-key-here"\n', file=sys.stderr)
        sys.exit(1)


    base_url = os.getenv("EXPLABS_BASE_URL", "https://api.experientiallabs.ai/v1").rstrip("/")
    model = "claude-opus-5.5"
    url = f"{base_url}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Hello! Reply with a brief 1-sentence confirmation that claude-opus-5.5 is active via Experiential Labs gateway.",
            }
        ],
        "temperature": 1.0,
        "max_tokens": 150,
    }


    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    print(f"Connecting to: {url}")
    print(f"Model ID: {model}")
    print("Sending test request...")

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        reply = ""
        choices = data.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            reply = msg.get("content") or msg.get("reasoning") or ""


        usage = data.get("usage", {})

        print("\n=== Experiential Gateway Test Succeeded! ===")
        print(f"Model: {data.get('model', model)}")
        print(f"Reply: {reply.strip()}")
        print("\nToken Usage:")
        print(f"  Prompt tokens:     {usage.get('prompt_tokens', 'N/A')}")
        print(f"  Completion tokens: {usage.get('completion_tokens', 'N/A')}")
        print(f"  Total tokens:      {usage.get('total_tokens', 'N/A')}")
        print("============================================\n")

    except httpx.HTTPStatusError as exc:
        print(f"\n[HTTP Error {exc.response.status_code}]: {exc.response.text}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"\n[Error]: {exc}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
