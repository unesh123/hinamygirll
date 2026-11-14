"""
Auto Goal Decomposer — takes a vague instruction like "hack this" and breaks
it into concrete, ordered steps Hina can execute one by one. She figures out
the plan herself without being told every step.
"""
import logging
import re
from typing import Dict, Any, List

logger = logging.getLogger("hinaa.tools.decomposer")

class AutoGoalDecomposer:
    """Turns "hack this website" into [recon, scan, exploit, bypass, extract]."""

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        goal = params.get("goal", "").lower()
        target = params.get("target", "")
        steps: List[Dict[str, Any]] = []

        # Detect the type of target
        is_url = "http" in goal or "://" in goal or ".com" in goal or ".net" in goal or ".org" in goal
        is_ip = re.search(r"\d+\.\d+\.\d+\.\d+", goal)
        is_ssh = "ssh" in goal
        is_api = "api" in goal or "endpoint" in goal
        is_web = "web" in goal or "site" in goal or "app" in goal or "page" in goal or is_url

        # Step 1: Recon — always first
        if is_ip:
            steps.append({"step": 1, "action": "hacker_agent", "params": {"target": target, "goal": "scan ports and services"}, "reason": "IP target — start with nmap"})
        elif is_ssh:
            steps.append({"step": 1, "action": "hacker_agent", "params": {"target": target, "goal": "brute force SSH credentials"}, "reason": "SSH target — try rockyou wordlist"})
        else:
            steps.append({"step": 1, "action": "hacker_agent", "params": {"target": target, "goal": "scan ports and find open services"}, "reason": "Unknown target — recon first"})

        # Step 2: Web-specific if it's a URL
        if is_web or is_url:
            steps.append({"step": 2, "action": "bypass_engine", "params": {"target": target, "goal": "bypass auth and find admin panel"}, "reason": "Web target — try WAF, JWT, IDOR, SQLi"})
            steps.append({"step": 3, "action": "hacker_agent", "params": {"target": target, "goal": "find and exploit any open endpoints"}, "reason": "Look for hidden routes and APIs"})

        # Step 3: Data extraction
        if "extract" in goal or "dump" in goal or "data" in goal or "database" in goal or "users" in goal:
            steps.append({"step": len(steps)+1, "action": "hacker_agent", "params": {"target": target, "goal": "extract database and dump all tables"}, "reason": "Data extraction requested"})

        # Step 4: RCE / shell access
        if "rce" in goal or "shell" in goal or "root" in goal or "control" in goal or "access" in goal:
            steps.append({"step": len(steps)+1, "action": "hacker_agent", "params": {"target": target, "goal": "get remote code execution and a reverse shell"}, "reason": "RCE requested"})

        # Step 5: Persist — save what worked
        steps.append({"step": len(steps)+1, "action": "exploit_memory", "params": {"flaw_type": "all"}, "reason": "Save successful exploits for next time"})

        # Step 6: Log money if she spent anything
        steps.append({"step": len(steps)+1, "action": "money_guard", "params": {"action": "summary"}, "reason": "Check what this cost"})

        return {"steps": steps, "target": target, "total_steps": len(steps), "note": "Execute steps in order. If a step fails, skip to the next strategy."}