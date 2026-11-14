"""
Self-Improver — after every task, Hina reviews what worked and what failed,
then updates her own strategy weights. The more she works, the better she gets.
"""
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("hinaa.tools.self_improver")

LEARNING_FILE = Path(r"C:\Users\unesh\OneDrive\all my cloud stroge\Desktop\APPS\HINAMYGIRL\.hina\workspace\learnings.json")

class SelfImprover:
    def __init__(self):
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if LEARNING_FILE.exists():
            return json.loads(LEARNING_FILE.read_text(encoding="utf-8"))
        return {
            "strategy_weights": {
                "waf_evasion": 1.0,
                "jwt_flaw": 1.0,
                "idor": 1.0,
                "session_swap": 1.0,
                "header_spoof": 1.0,
                "sqli": 1.0,
            },
            "lessons": [],
            "total_tasks": 0,
            "success_rate": 0.0,
        }

    def _save(self):
        LEARNING_FILE.parent.mkdir(parents=True, exist_ok=True)
        LEARNING_FILE.write_text(json.dumps(self.data, indent=2, default=str), encoding="utf-8")

    def record_outcome(self, strategy: str, success: bool, note: str = "") -> Dict[str, Any]:
        """Adjust strategy weight based on whether it worked."""
        self.data["total_tasks"] += 1
        if success:
            self.data["strategy_weights"][strategy] = round(self.data["strategy_weights"].get(strategy, 1.0) * 1.1, 3)
        else:
            self.data["strategy_weights"][strategy] = round(max(self.data["strategy_weights"].get(strategy, 1.0) * 0.9, 0.1), 3)

        self.data["lessons"].append({"strategy": strategy, "success": success, "note": note, "time": time.time()})
        self.data["lessons"] = self.data["lessons"][-50:]  # keep last 50

        successes = sum(1 for l in self.data["lessons"] if l["success"])
        self.data["success_rate"] = round(successes / len(self.data["lessons"]), 3) if self.data["lessons"] else 0
        self._save()
        logger.info("[self_improve] %s → %s. Weight: %.2f. Success rate: %.1f%%",
                    strategy, "worked" if success else "failed",
                    self.data["strategy_weights"][strategy], self.data["success_rate"] * 100)
        return {"strategy": strategy, "success": success, "new_weight": self.data["strategy_weights"][strategy], "success_rate": self.data["success_rate"]}

    def best_strategies(self, top_n: int = 3) -> List[Dict[str, Any]]:
        sorted_w = sorted(self.data["strategy_weights"].items(), key=lambda x: x[1], reverse=True)
        return [{"strategy": k, "weight": v} for k, v in sorted_w[:top_n]]

    def summary(self) -> Dict[str, Any]:
        return {
            "total_tasks": self.data["total_tasks"],
            "success_rate": self.data["success_rate"],
            "strategy_weights": self.data["strategy_weights"],
            "best_strategies": self.best_strategies(3),
            "recent_lessons": self.data["lessons"][-5:],
        }