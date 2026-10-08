"""Connect the owner's Outlook using Microsoft device sign-in; never prints tokens."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import sys
import time
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
from hinaa_api.integrations.outlook_graph import SCOPES, save_credentials

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-id", default=os.getenv("OUTLOOK_CLIENT_ID"))
    parser.add_argument("--tenant", default=os.getenv("OUTLOOK_TENANT_ID", "organizations"))
    parser.add_argument("--allow-send", action="store_true", help="Request Mail.Send in addition to inbox reading and draft creation")
    args = parser.parse_args()
    if not args.client_id:
        parser.error("Set OUTLOOK_CLIENT_ID to your registered Microsoft public-client application ID.")
    if not re.fullmatch(r"[A-Za-z0-9.-]+", args.tenant):
        parser.error("Invalid tenant ID")
    scope = SCOPES + (" https://graph.microsoft.com/Mail.Send" if args.allow_send else "")
    base = f"https://login.microsoftonline.com/{args.tenant}/oauth2/v2.0"
    with httpx.Client(timeout=20) as client:
        response = client.post(base + "/devicecode", data={"client_id": args.client_id, "scope": scope})
        if response.status_code != 200:
            sys.exit("Microsoft could not start sign-in. Check the application ID, tenant, and public client flow setting.")
        flow = response.json()
        print(flow["message"], flush=True)
        deadline = time.monotonic() + flow["expires_in"]
        interval = flow.get("interval", 5)
        while time.monotonic() < deadline:
            time.sleep(interval)
            response = client.post(base + "/token", data={"grant_type": "urn:ietf:params:oauth:grant-type:device_code", "client_id": args.client_id, "device_code": flow["device_code"]})
            tokens = response.json()
            if response.status_code == 200:
                if not tokens.get("refresh_token"):
                    sys.exit("Microsoft did not grant offline access. Reconnect with offline_access consent.")
                # Verify the signed-in mailbox before keeping its credentials.
                identity = client.get("https://graph.microsoft.com/v1.0/me", headers={"Authorization": "Bearer " + tokens["access_token"]})
                if identity.status_code != 200:
                    sys.exit("Could not verify the signed-in Microsoft account.")
                save_credentials({**tokens, "client_id": args.client_id, "tenant": args.tenant, "scope": scope, "expires_at": time.time() + tokens.get("expires_in", 3600)})
                print("Outlook connected. Credentials are encrypted for your Windows account. No email was sent.")
                return
            error = tokens.get("error")
            if error == "authorization_pending":
                continue
            if error == "slow_down":
                interval += 5
                continue
            sys.exit("Microsoft sign-in was declined, expired, or blocked by your organization's policy.")
        sys.exit("Sign-in timed out. Run the connector again.")

if __name__ == "__main__":
    main()
