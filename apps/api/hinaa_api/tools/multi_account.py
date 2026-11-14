"""
Multi-Account Manager — manages multiple Google, social, and service accounts.
Hina can log in as any of them, switch between them, and gather data from each.
"""
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("hinaa.tools.multi_account")

ACCOUNTS_FILE = Path(r"C:\Users\unesh\OneDrive\all my cloud stroge\Desktop\APPS\HINAMYGIRL\.hina\workspace\accounts.json")

class MultiAccountManager:
    def __init__(self):
        self.accounts: List[Dict[str, Any]] = self._load()
        self.active: str = ""

    def _load(self) -> List[Dict[str, Any]]:
        if ACCOUNTS_FILE.exists():
            return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        return []

    def _save(self):
        ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        ACCOUNTS_FILE.write_text(json.dumps(self.accounts, indent=2), encoding="utf-8")

    def add_account(self, name: str, platform: str, email: str, password: str, notes: str = "") -> Dict[str, Any]:
        acct = {"name": name, "platform": platform, "email": email, "password": password, "notes": notes, "added": time.time()}
        self.accounts.append(acct)
        self._save()
        logger.info("[accounts] added %s (%s)", name, platform)
        return acct

    def list_accounts(self, platform: str = "") -> List[Dict[str, Any]]:
        if platform:
            return [a for a in self.accounts if a["platform"].lower() == platform.lower()]
        return self.accounts

    def switch(self, name: str) -> Dict[str, Any]:
        acct = next((a for a in self.accounts if a["name"] == name), None)
        if not acct:
            return {"error": f"Account '{name}' not found"}
        self.active = name
        return {"active": name, "platform": acct["platform"], "email": acct["email"]}

    def remove(self, name: str) -> bool:
        before = len(self.accounts)
        self.accounts = [a for a in self.accounts if a["name"] != name]
        if len(self.accounts) != before:
            self._save()
            return True
        return False

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        action = params.get("action", "list")
        if action == "add":
            return self.add_account(params.get("name",""), params.get("platform",""), params.get("email",""), params.get("password",""), params.get("notes",""))
        if action == "list":
            return {"accounts": self.list_accounts(params.get("platform","")), "active": self.active}
        if action == "switch":
            return self.switch(params.get("name",""))
        if action == "remove":
            return {"removed": self.remove(params.get("name",""))}
        return {"error": "unknown action"}