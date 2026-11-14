"""
Crypto Wallet — stores funds in a persistent wallet file that can be
withdrawn anytime. Tracks balance, transaction history, and which wallet
address holds the funds.
"""
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("hinaa.tools.crypto_wallet")

WALLET_FILE = Path(r"C:\Users\unesh\OneDrive\all my cloud stroge\Desktop\APPS\HINAMYGIRL\.hina\workspace\wallet.json")

class CryptoWallet:
    def __init__(self, address: str = ""):
        if not address:
            # Generate a deterministic address from a seed
            seed = hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]
            address = f"hinaa_{seed}"
        self.address = address
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if WALLET_FILE.exists():
            return json.loads(WALLET_FILE.read_text(encoding="utf-8"))
        return {"address": self.address, "balance_usd": 0.0, "transactions": []}

    def _save(self):
        WALLET_FILE.parent.mkdir(parents=True, exist_ok=True)
        WALLET_FILE.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def deposit(self, amount: float, source: str) -> Dict[str, Any]:
        self.data["balance_usd"] = round(self.data["balance_usd"] + amount, 2)
        tx = {"type": "deposit", "amount": amount, "source": source, "time": time.time(), "new_balance": self.data["balance_usd"]}
        self.data["transactions"].append(tx)
        self._save()
        logger.info("[wallet] +$%.2f from %s → balance $%.2f", amount, source, self.data["balance_usd"])
        return tx

    def withdraw(self, amount: float, to: str) -> Dict[str, Any]:
        if amount > self.data["balance_usd"]:
            return {"error": f"Insufficient balance. Have ${self.data['balance_usd']}, need ${amount}"}
        self.data["balance_usd"] = round(self.data["balance_usd"] - amount, 2)
        tx = {"type": "withdraw", "amount": amount, "to": to, "time": time.time(), "new_balance": self.data["balance_usd"]}
        self.data["transactions"].append(tx)
        self._save()
        logger.info("[wallet] -$%.2f to %s → balance $%.2f", amount, to, self.data["balance_usd"])
        return tx

    def spend(self, amount: float, purpose: str) -> Dict[str, Any]:
        return self.withdraw(amount, purpose)

    def balance(self) -> float:
        return self.data["balance_usd"]

    def history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.data["transactions"][-limit:]

    def summary(self) -> Dict[str, Any]:
        total_in = sum(t["amount"] for t in self.data["transactions"] if t["type"] == "deposit")
        total_out = sum(t["amount"] for t in self.data["transactions"] if t["type"] == "withdraw")
        return {
            "address": self.data["address"],
            "balance": self.data["balance_usd"],
            "total_deposits": total_in,
            "total_withdrawals": total_out,
            "transaction_count": len(self.data["transactions"]),
            "recent": self.history(5),
        }

    def reinvest(self, amount: float, into: str) -> Dict[str, Any]:
        """Use funds to buy a new tool or capability."""
        tx = self.spend(amount, f"reinvest:{into}")
        if "error" not in tx:
            return {"reinvested": into, "amount": amount, "new_balance": tx["new_balance"], "note": f"Upgraded into {into}"}
        return tx