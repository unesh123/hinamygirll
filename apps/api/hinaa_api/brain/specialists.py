"""Specialist agent implementations for HinaBrainCoordinator."""

import asyncio

class ResearchSpecialist:
    async def run(self, user_text: str, tool_executor, available_tools: list[str], timeout: float = 45.0) -> dict:
        """Execute web/Exa research. Returns {sources: [...], synthesis: str, source_count: int}"""
        try:
            async with asyncio.timeout(timeout):
                if available_tools and "exa_search" in available_tools:
                    try:
                        result = await tool_executor("exa_search", {"query": user_text})
                        sources = result.get("results", [])
                        return {
                            "sources": sources,
                            "synthesis": "Found results using Exa search.",
                            "source_count": len(sources)
                        }
                    except Exception:
                        pass
                
                # Fallback to web_search
                try:
                    result = await tool_executor("web_search", {"query": user_text})
                    sources = result.get("results", [])
                    return {
                        "sources": sources,
                        "synthesis": "Found results using Web search.",
                        "source_count": len(sources)
                    }
                except Exception:
                    return {"sources": [], "synthesis": "Search failed.", "source_count": 0}
        except TimeoutError:
            return {"sources": [], "synthesis": "Search timed out.", "source_count": 0}

class MemorySpecialist:
    async def run(self, user_text: str, conversation_history: list[dict] | None, session_id: str | None, timeout: float = 10.0) -> dict:
        """Extract relevant context from history. Returns {context_snippets: [...], key_facts: [...]}"""
        try:
            async with asyncio.timeout(timeout):
                history_str = str(conversation_history) if conversation_history else ""
                return {
                    "context_snippets": [history_str[-200:]] if history_str else [],
                    "key_facts": []
                }
        except TimeoutError:
            return {"context_snippets": [], "key_facts": []}

class PlanningSpecialist:
    async def run(self, user_text: str, intent_route: list[str], research_output: dict | None, timeout: float = 20.0) -> dict:
        """Create execution plan. Returns {steps: [...], strategy: str, complexity: 'simple'|'medium'|'complex'}"""
        try:
            async with asyncio.timeout(timeout):
                complexity = "complex" if len(intent_route) > 2 else "simple"
                return {
                    "steps": intent_route,
                    "strategy": "Sequential execution based on intent.",
                    "complexity": complexity
                }
        except TimeoutError:
            return {"steps": [], "strategy": "Timeout", "complexity": "simple"}

class CodingSpecialist:
    async def run(self, user_text: str, tool_executor, timeout: float = 60.0) -> dict:
        """Handle code generation. Returns {code: str, language: str, explanation: str}"""
        try:
            async with asyncio.timeout(timeout):
                # Placeholder for actual coding agent logic. We assume it might use tools or just return simple stuff.
                return {
                    "code": "# Generated code",
                    "language": "python",
                    "explanation": "Simple placeholder code."
                }
        except TimeoutError:
            return {"code": "", "language": "", "explanation": "Timeout"}

class SynthesisSpecialist:
    async def run(self, user_text: str, specialist_outputs: dict, timeout: float = 30.0) -> dict:
        """Synthesize all outputs into final response. Returns {response_text: str, sources: [...], artifact: dict|None}"""
        try:
            async with asyncio.timeout(timeout):
                sources = []
                if "researcher" in specialist_outputs:
                    sources = specialist_outputs["researcher"].get("sources", [])
                
                response_parts = ["Synthesis complete."]
                for sp, out in specialist_outputs.items():
                    response_parts.append(f"[{sp}] ran.")
                    
                return {
                    "response_text": " ".join(response_parts),
                    "sources": sources,
                    "artifact": None
                }
        except TimeoutError:
            return {"response_text": "Synthesis timed out.", "sources": [], "artifact": None}
