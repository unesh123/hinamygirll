from dataclasses import dataclass, field
from typing import AsyncIterator, Any, Literal
import asyncio
import time
import uuid
import logging

from .specialists import (
    ResearchSpecialist,
    MemorySpecialist,
    PlanningSpecialist,
    CodingSpecialist,
    SynthesisSpecialist,
)

logger = logging.getLogger(__name__)

SpecialistType = Literal["planner", "researcher", "coder", "synthesizer", "memory"]

@dataclass
class BrainRunEvent:
    event_type: str  # brain.run.started | brain.specialist.started | brain.specialist.progress | brain.specialist.completed | brain.specialist.failed | brain.run.completed | brain.run.failed
    run_id: str
    specialist: SpecialistType | None = None
    step_id: str | None = None
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

class HinaBrainCoordinator:
    """Multi-specialist AI brain coordinator."""
    
    def __init__(
        self,
        *,
        tool_executor,  # Callable[[str, dict], Awaitable[Any]]
        ledger=None,    # RunLedger instance  
        max_parallel_specialists: int = 3,
        specialist_timeout: float = 60.0,
    ):
        self.tool_executor = tool_executor
        self.ledger = ledger
        self.semaphore = asyncio.Semaphore(max_parallel_specialists)
        self.specialist_timeout = specialist_timeout

        self.researcher = ResearchSpecialist()
        self.memory = MemorySpecialist()
        self.planner = PlanningSpecialist()
        self.coder = CodingSpecialist()
        self.synthesizer = SynthesisSpecialist()

    def _route_intent(self, user_text: str, available_tools: list[str]) -> list[SpecialistType]:
        """Determine which specialists are needed based on user intent signals."""
        text_lower = user_text.lower()
        specialists: list[SpecialistType] = ["planner"]  # always
        
        # Research needed?
        research_signals = ["search", "find", "look up", "research", "what is", "who is", "latest", "recent", "news", "analyze", "compare"]
        if any(s in text_lower for s in research_signals) or "/search" in user_text or "/deepresearch" in user_text:
            specialists.append("researcher")
        
        # Code needed?
        code_signals = ["code", "write", "build", "implement", "fix", "debug", "function", "class", "script", ".py", ".js", ".ts"]
        if any(s in text_lower for s in code_signals) or "/code" in user_text:
            specialists.append("coder")
        
        # Memory needed? (always useful for multi-turn)
        specialists.append("memory")
        
        # Synthesis always last
        specialists.append("synthesizer")
        
        return specialists

    async def _specialist_plan(self, user_text: str, intent_route: list[SpecialistType], run_id: str, turn_id: str, session_id: str | None, event_queue: asyncio.Queue) -> dict:
        start_time = time.time()
        await event_queue.put(BrainRunEvent(event_type="brain.specialist.started", run_id=run_id, specialist="planner"))
        try:
            result = await self.planner.run(user_text, intent_route, None, timeout=self.specialist_timeout)
            await event_queue.put(BrainRunEvent(event_type="brain.specialist.completed", run_id=run_id, specialist="planner", payload=result))
            
            if self.ledger:
                self.ledger.record_receipt(
                    turn_id=turn_id,
                    step_type="brain.planner",
                    step_name="PlanningSpecialist",
                    status="completed",
                    duration_ms=int((time.time() - start_time) * 1000),
                    input_summary=f"User intent route: {intent_route}",
                    output_summary=f"Plan strategy: {result.get('strategy')}",
                    session_id=session_id
                )
            return result
        except Exception as e:
            await event_queue.put(BrainRunEvent(event_type="brain.specialist.failed", run_id=run_id, specialist="planner", payload={"error": str(e)}))
            if self.ledger:
                self.ledger.record_receipt(
                    turn_id=turn_id,
                    step_type="brain.planner",
                    step_name="PlanningSpecialist",
                    status="failed",
                    duration_ms=int((time.time() - start_time) * 1000),
                    error=str(e),
                    session_id=session_id
                )
            return {"error": str(e)}

    async def _specialist_research(self, user_text: str, available_tools: list[str], run_id: str, turn_id: str, session_id: str | None, event_queue: asyncio.Queue) -> dict:
        start_time = time.time()
        await event_queue.put(BrainRunEvent(event_type="brain.specialist.started", run_id=run_id, specialist="researcher"))
        try:
            result = await self.researcher.run(user_text, self.tool_executor, available_tools, timeout=self.specialist_timeout)
            await event_queue.put(BrainRunEvent(event_type="brain.specialist.completed", run_id=run_id, specialist="researcher", payload=result))
            if self.ledger:
                self.ledger.record_receipt(
                    turn_id=turn_id,
                    step_type="brain.researcher",
                    step_name="ResearchSpecialist",
                    status="completed",
                    duration_ms=int((time.time() - start_time) * 1000),
                    input_summary=user_text,
                    output_summary=result.get("synthesis", ""),
                    source_count=result.get("source_count", 0),
                    session_id=session_id
                )
            return result
        except Exception as e:
            await event_queue.put(BrainRunEvent(event_type="brain.specialist.failed", run_id=run_id, specialist="researcher", payload={"error": str(e)}))
            if self.ledger:
                self.ledger.record_receipt(
                    turn_id=turn_id,
                    step_type="brain.researcher",
                    step_name="ResearchSpecialist",
                    status="failed",
                    duration_ms=int((time.time() - start_time) * 1000),
                    error=str(e),
                    session_id=session_id
                )
            return {"error": str(e)}

    async def _specialist_memory(self, user_text: str, conversation_history: list[dict] | None, run_id: str, turn_id: str, session_id: str | None, event_queue: asyncio.Queue) -> dict:
        start_time = time.time()
        await event_queue.put(BrainRunEvent(event_type="brain.specialist.started", run_id=run_id, specialist="memory"))
        try:
            result = await self.memory.run(user_text, conversation_history, session_id, timeout=self.specialist_timeout)
            await event_queue.put(BrainRunEvent(event_type="brain.specialist.completed", run_id=run_id, specialist="memory", payload=result))
            if self.ledger:
                self.ledger.record_receipt(
                    turn_id=turn_id,
                    step_type="brain.memory",
                    step_name="MemorySpecialist",
                    status="completed",
                    duration_ms=int((time.time() - start_time) * 1000),
                    input_summary=f"History items: {len(conversation_history or [])}",
                    output_summary=f"Context snippets: {len(result.get('context_snippets', []))}",
                    session_id=session_id
                )
            return result
        except Exception as e:
            await event_queue.put(BrainRunEvent(event_type="brain.specialist.failed", run_id=run_id, specialist="memory", payload={"error": str(e)}))
            if self.ledger:
                self.ledger.record_receipt(
                    turn_id=turn_id,
                    step_type="brain.memory",
                    step_name="MemorySpecialist",
                    status="failed",
                    duration_ms=int((time.time() - start_time) * 1000),
                    error=str(e),
                    session_id=session_id
                )
            return {"error": str(e)}

    async def _specialist_code(self, user_text: str, run_id: str, turn_id: str, session_id: str | None, event_queue: asyncio.Queue) -> dict:
        start_time = time.time()
        await event_queue.put(BrainRunEvent(event_type="brain.specialist.started", run_id=run_id, specialist="coder"))
        try:
            result = await self.coder.run(user_text, self.tool_executor, timeout=self.specialist_timeout)
            await event_queue.put(BrainRunEvent(event_type="brain.specialist.completed", run_id=run_id, specialist="coder", payload=result))
            if self.ledger:
                self.ledger.record_receipt(
                    turn_id=turn_id,
                    step_type="brain.coder",
                    step_name="CodingSpecialist",
                    status="completed",
                    duration_ms=int((time.time() - start_time) * 1000),
                    input_summary=user_text,
                    output_summary=result.get("explanation", ""),
                    session_id=session_id
                )
            return result
        except Exception as e:
            await event_queue.put(BrainRunEvent(event_type="brain.specialist.failed", run_id=run_id, specialist="coder", payload={"error": str(e)}))
            if self.ledger:
                self.ledger.record_receipt(
                    turn_id=turn_id,
                    step_type="brain.coder",
                    step_name="CodingSpecialist",
                    status="failed",
                    duration_ms=int((time.time() - start_time) * 1000),
                    error=str(e),
                    session_id=session_id
                )
            return {"error": str(e)}

    async def _specialist_synthesize(self, user_text: str, specialist_outputs: dict, run_id: str, turn_id: str, session_id: str | None, event_queue: asyncio.Queue) -> dict:
        start_time = time.time()
        await event_queue.put(BrainRunEvent(event_type="brain.specialist.started", run_id=run_id, specialist="synthesizer"))
        try:
            result = await self.synthesizer.run(user_text, specialist_outputs, timeout=self.specialist_timeout)
            await event_queue.put(BrainRunEvent(event_type="brain.specialist.completed", run_id=run_id, specialist="synthesizer", payload=result))
            if self.ledger:
                self.ledger.record_receipt(
                    turn_id=turn_id,
                    step_type="brain.synthesizer",
                    step_name="SynthesisSpecialist",
                    status="completed",
                    duration_ms=int((time.time() - start_time) * 1000),
                    input_summary=f"Specialist outputs: {list(specialist_outputs.keys())}",
                    output_summary="Synthesis completed.",
                    session_id=session_id
                )
            return result
        except Exception as e:
            await event_queue.put(BrainRunEvent(event_type="brain.specialist.failed", run_id=run_id, specialist="synthesizer", payload={"error": str(e)}))
            if self.ledger:
                self.ledger.record_receipt(
                    turn_id=turn_id,
                    step_type="brain.synthesizer",
                    step_name="SynthesisSpecialist",
                    status="failed",
                    duration_ms=int((time.time() - start_time) * 1000),
                    error=str(e),
                    session_id=session_id
                )
            return {"error": str(e)}

    async def run_stream(
        self,
        *,
        turn_id: str,
        user_text: str,
        session_id: str | None = None,
        conversation_history: list[dict] | None = None,
        available_tools: list[str] | None = None,
    ) -> AsyncIterator[BrainRunEvent]:
        """Stream brain events as specialists work. Each event is JSON-serializable."""
        run_id = uuid.uuid4().hex
        tools = available_tools or []
        
        event_queue: asyncio.Queue[BrainRunEvent | None] = asyncio.Queue()
        
        async def run_internal():
            try:
                await event_queue.put(BrainRunEvent(event_type="brain.run.started", run_id=run_id))
                
                route = self._route_intent(user_text, tools)
                
                outputs = {}
                
                # Planner is always first, blocking
                plan = await self._specialist_plan(user_text, route, run_id, turn_id, session_id, event_queue)
                outputs["planner"] = plan
                
                # Middle specialists run concurrently
                concurrent_tasks = []
                async def sem_run(coro):
                    async with self.semaphore:
                        return await coro
                        
                if "researcher" in route:
                    concurrent_tasks.append(
                        (sem_run(self._specialist_research(user_text, tools, run_id, turn_id, session_id, event_queue)), "researcher")
                    )
                if "memory" in route:
                    concurrent_tasks.append(
                        (sem_run(self._specialist_memory(user_text, conversation_history, run_id, turn_id, session_id, event_queue)), "memory")
                    )
                if "coder" in route:
                    concurrent_tasks.append(
                        (sem_run(self._specialist_code(user_text, run_id, turn_id, session_id, event_queue)), "coder")
                    )
                
                if concurrent_tasks:
                    results = await asyncio.gather(*(t[0] for t in concurrent_tasks), return_exceptions=True)
                    for (coro, spec_type), res in zip(concurrent_tasks, results):
                        if isinstance(res, Exception):
                            outputs[spec_type] = {"error": str(res)}
                        else:
                            outputs[spec_type] = res
                            
                # Synthesis always last
                final_res = await self._specialist_synthesize(user_text, outputs, run_id, turn_id, session_id, event_queue)
                outputs["synthesizer"] = final_res
                
                await event_queue.put(BrainRunEvent(event_type="brain.run.completed", run_id=run_id, payload={"final": final_res}))
            except Exception as e:
                logger.error(f"Brain run failed: {e}", exc_info=True)
                await event_queue.put(BrainRunEvent(event_type="brain.run.failed", run_id=run_id, payload={"error": str(e)}))
            finally:
                await event_queue.put(None)

        task = asyncio.create_task(run_internal())
        
        while True:
            event = await event_queue.get()
            if event is None:
                break
            yield event
