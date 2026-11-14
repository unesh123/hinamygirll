"""
Money Guard — tracks every dollar Hina spends or earns. Cautious by default.
She logs every transaction and warns if a cost exceeds threshold.
"""
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("hinaa.tools.money_guard")

MONEY_FILE = Path(r"C:\Users\unesh\OneDrive\all my cloud stroge\Desktop\APPS\HINAMYGIRL\.hina\workspace\money\ledger.json")

class MoneyGuard:
    def __init__(self):
        self.ledger: List[Dict[str, Any]] = self._load()
        self.budget_warning = 5.0  # USD threshold before warning

    def _load(self) -> List[Dict[str, Any]]:
        if MONEY_FILE.exists():
            return json.loads(MONEY_FILE.read_text(encoding="utf-8"))
        return []

    def _save(self):
        MONEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        MONEY_FILE.write_text(json.dumps(self.ledger, indent=2), encoding="utf-8")

    def log_expense(self, item: str, amount: float, currency: str = "USD") -> Dict[str, Any]:
        entry = {"type": "expense", "item": item, "amount": amount, "currency": currency, "time": time.time()}
        self.ledger.append(entry)
        self._save()
        warning = " ⚠️ BUDGET WARNING" if amount > self.budget_warning else ""
        logger.info("[money] spent $%.2f on %s%s", amount, item, warning)
        return {"logged": True, "entry": entry, "warning": warning or None}

    def log_income(self, source: str, amount: float, currency: str = "USD") -> Dict[str, Any]:
        entry = {"type": "income", "source": source, "amount": amount, "currency": currency, "time": time.time()}
        self.ledger.append(entry)
        self._save()
        logger.info("[money] earned $%.2f from %s", amount, source)
        return {"logged": True, "entry": entry}

    def balance(self) -> float:
        income = sum(e["amount"] for e in self.ledger if e["type"] == "income")
        expense = sum(e["amount"] for e in self.ledger if e["type"] == "expense")
        return round(income - expense, 2)

    def summary(self) -> Dict[str, Any]:
        income = sum(e["amount"] for e in self.ledger if e["type"] == "income")
        expense = sum(e["amount"] for e in self.ledger if e["type"] == "expense")
        return {"balance": self.balance(), "total_income": income, "total_expense": expense, "transactions": len(self.ledger)}