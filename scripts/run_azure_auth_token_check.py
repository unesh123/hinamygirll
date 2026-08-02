#!/usr/bin/env python3
"""One-call Azure Speech authorization-token check.

DISABLED BY DEFAULT. Makes exactly one HTTPS token request when gated.

Uses the Speech resource STS endpoint:
  POST https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken
  Header: Ocp-Apim-Subscription-Key: <AZURE_SPEECH_KEY>

Never prints the key or returned token. Never saves the token.
Never runs from ordinary pytest.

Required in the SAME shell:
  set HINAA_ALLOW_AZURE_AUTH_CHECK=1
  set HINAA_AZURE_AUTH_CHECK_CONFIRM=I_UNDERSTAND_ONE_AUTH_CALL

Then:
  apps\\api\\.venv\\Scripts\\python.exe scripts\\run_azure_auth_token_check.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

CONFIRM = "I_UNDERSTAND_ONE_AUTH_CALL"


def _gate_or_exit() -> None:
    if os.environ.get("HINAA_ALLOW_AZURE_AUTH_CHECK") != "1":
        print("Refusing to run: set HINAA_ALLOW_AZURE_AUTH_CHECK=1")
        raise SystemExit(2)
    if os.environ.get("HINAA_AZURE_AUTH_CHECK_CONFIRM") != CONFIRM:
        print(f"Refusing to run: set HINAA_AZURE_AUTH_CHECK_CONFIRM={CONFIRM}")
        raise SystemExit(2)


def main() -> None:
    _gate_or_exit()
    # One-shot gate clear before network call completes in this process.
    os.environ.pop("HINAA_ALLOW_AZURE_AUTH_CHECK", None)
    os.environ.pop("HINAA_AZURE_AUTH_CHECK_CONFIRM", None)

    from hinaa_api.config import Settings

    settings = Settings()  # type: ignore[call-arg]
    key = (
        settings.azure_speech_key.get_secret_value()
        if settings.azure_speech_key
        else ""
    )
    region = (settings.azure_speech_region or "").strip()
    if not key:
        print(
            {
                "success": False,
                "category": "AZURE_KEY_MISSING",
                "configuredRegion": region or None,
                "elapsedMs": 0,
            }
        )
        raise SystemExit(3)
    if not region:
        print(
            {
                "success": False,
                "category": "AZURE_REGION_MISSING",
                "configuredRegion": None,
                "elapsedMs": 0,
            }
        )
        raise SystemExit(3)

    # Metadata only — never print key/token.
    print(
        {
            "keyPresent": True,
            "keyLength": len(key),
            "configuredRegion": region,
            "endpointHost": f"{region}.api.cognitive.microsoft.com",
            "path": "/sts/v1.0/issueToken",
            "method": "POST",
        }
    )

    url = f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    request = Request(
        url,
        data=b"",
        method="POST",
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Length": "0",
        },
    )
    started = perf_counter()
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - owner-gated HTTPS
            status = int(getattr(response, "status", 200) or 200)
            token = response.read()
        elapsed = int((perf_counter() - started) * 1000)
        # Discard token immediately; never print/save.
        token_ok = bool(token) and status == 200
        del token
        print(
            {
                "success": token_ok,
                "httpStatus": status,
                "category": "AZURE_AUTH_OK" if token_ok else "AZURE_AUTH_FAILED",
                "configuredRegion": region,
                "elapsedMs": elapsed,
            }
        )
        raise SystemExit(0 if token_ok else 4)
    except HTTPError as error:
        elapsed = int((perf_counter() - started) * 1000)
        status = int(error.code)
        if status in {401, 403}:
            category = "AZURE_AUTH_FAILED"
        elif status == 404:
            category = "AZURE_KEY_REGION_MISMATCH"
        elif status == 429:
            category = "AZURE_QUOTA_OR_BILLING"
        else:
            category = "AZURE_NETWORK_FAILED"
        print(
            {
                "success": False,
                "httpStatus": status,
                "category": category,
                "configuredRegion": region,
                "elapsedMs": elapsed,
            }
        )
        raise SystemExit(4)
    except URLError:
        elapsed = int((perf_counter() - started) * 1000)
        print(
            {
                "success": False,
                "httpStatus": None,
                "category": "AZURE_NETWORK_FAILED",
                "configuredRegion": region,
                "elapsedMs": elapsed,
            }
        )
        raise SystemExit(4)


if __name__ == "__main__":
    main()
