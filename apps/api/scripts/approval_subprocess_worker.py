"""Subprocess worker to test true OS-level process boundary survival for ActionApprovalGate."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hinaa_api.security.action_approvals import ActionApprovalGate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--step", required=True, choices=["initiate", "resolve_and_consume", "consume_again", "verify_signature"])
    parser.add_argument("--challenge-id", default="")
    parser.add_argument("--tenant-id", default="tenant_multi_proc")
    parser.add_argument("--actor-id", default="actor_proc")
    parser.add_argument("--device-id", default="device_proc")
    parser.add_argument("--key-hex", default="")
    args = parser.parse_args()

    key = bytes.fromhex(args.key_hex) if args.key_hex else None
    gate = ActionApprovalGate(db_path=Path(args.db_path), signing_key=key)

    if args.step == "initiate":
        async def run_init():
            params = {"command": "npm run build:prod", "runtime": "powershell"}
            asyncio.create_task(
                gate.request_approval(
                    "terminal_execute",
                    params,
                    tenant_id=args.tenant_id,
                    actor_id=args.actor_id,
                    device_id=args.device_id,
                    timeout_seconds=600.0,
                )
            )
            await asyncio.sleep(0.05)
            pending = gate.list_pending(tenant_id=args.tenant_id)
            cid = pending[0]["challenge_id"]
            print(json.dumps({"ok": True, "challenge_id": cid}))

        asyncio.run(run_init())
        sys.exit(0)

    elif args.step == "resolve_and_consume":
        res = gate.resolve_challenge(args.challenge_id, approved=True, tenant_id=args.tenant_id, reason="Subprocess approved")
        if not res:
            print(json.dumps({"ok": False, "error": "Failed to resolve"}))
            sys.exit(1)
        params = {"command": "npm run build:prod", "runtime": "powershell"}
        ok, msg = gate.verify_and_consume(args.challenge_id, params, tenant_id=args.tenant_id)
        print(json.dumps({"ok": ok, "message": msg}))
        sys.exit(0 if ok else 2)

    elif args.step == "consume_again":
        params = {"command": "npm run build:prod", "runtime": "powershell"}
        ok, msg = gate.verify_and_consume(args.challenge_id, params, tenant_id=args.tenant_id)
        print(json.dumps({"ok": ok, "message": msg}))
        sys.exit(0 if ok else 3)

    elif args.step == "verify_signature":
        params = {"command": "npm run build:prod", "runtime": "powershell"}
        ok, msg = gate.verify_and_consume(args.challenge_id, params, tenant_id=args.tenant_id)
        print(json.dumps({"ok": ok, "message": msg}))
        sys.exit(0 if ok else 4)


if __name__ == "__main__":
    main()
