"""
Crypto Wallet — CONTAINED & DISABLED under Security Directive v3.0.
Autonomous financial operations and cryptocurrency wallets are permanently prohibited.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger("hinaa.tools.crypto_wallet")


class CryptoWallet:
    """Fail-closed contained stub for autonomous crypto wallet."""

    def __init__(self, address: str = ""):
        self.address = "contained"

    def deposit(self, amount: float, source: str) -> Dict[str, Any]:
        logger.warning("[CONTAINMENT] crypto deposit refused: tool disabled by Directive v3.0.")
        return {"error": "Crypto wallet disabled by Directive v3.0 containment", "status": "TOOL_CONTAINED"}

    def withdraw(self, amount: float, to: str) -> Dict[str, Any]:
        logger.warning("[CONTAINMENT] crypto withdrawal refused: tool disabled by Directive v3.0.")
        return {"error": "Crypto wallet disabled by Directive v3.0 containment", "status": "TOOL_CONTAINED"}

    def spend(self, amount: float, purpose: str) -> Dict[str, Any]:
        return self.withdraw(amount, purpose)

    def balance(self) -> float:
        return 0.0

    def history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return []

    def summary(self) -> Dict[str, Any]:
        return {
            "address": "contained",
            "balance": 0.0,
            "total_deposits": 0.0,
            "total_withdrawals": 0.0,
            "transaction_count": 0,
            "recent": [],
            "status": "TOOL_CONTAINED",
        }

    def reinvest(self, amount: float, into: str) -> Dict[str, Any]:
        return {"error": "Autonomous reinvestment disabled by Directive v3.0 containment", "status": "TOOL_CONTAINED"}
