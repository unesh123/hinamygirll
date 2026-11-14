"""
Parallel Executor — runs multiple independent tool calls at the same time.
If a task can be split into independent steps, she does them all in parallel
instead of one by one. This is what makes her fast.
"""
import asyncio
import logging
import time
from typing import Dict, Any, List

logger = logging.getLogger("hinaa.tools.parallel")

class ParallelExecutor:
    """Runs a list of tool calls concurrently, returns results in order."""

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tasks: List[Dict[str, Any]] = params.get("tasks", [])
        if not tasks:
            return {"error": "tasks list is empty"}

        started = time.time()

        async def run_one(task: Dict[str, Any]) -> Dict[str, Any]:
            tool = task.get("tool", "")
            call_params = task.get("params", {})
            try:
                # Import the registry to look up the handler
                from .registry import registry
                handler = registry.get_handler(tool)
                if not handler:
                    return {"tool": tool, "error": f"Tool '{tool}' handler not found"}
                result = await handler(call_params) if asyncio.iscoroutinefunction(handler) else handler(call_params)
                return {"tool": tool, "result": result, "ok": True}
            except Exception as e:
                return {"tool": tool, "error": str(e), "ok": False}

        results = await asyncio.gather(*(run_one(t) for t in tasks))
        elapsed = round(time.time() - started, 3)
        return {"results": results, "elapsed_s": elapsed, "parallel": True}