from __future__ import annotations

import logging
import re
from typing import Any
from .state import AgentGoal, GoalType, PlanStep, StepStatus, VerificationReport

logger = logging.getLogger("hinaa.agent.planner")


def normalized_web_query(text: str) -> str:
    """Ask the search provider his question, not his whole sentence.

    The utterance still carries the addressee and the command verb — "hinaa
    please search who is Mikasa Ackerman" — and a relevance engine treats every
    one of those words as a term to match. If the compile cannot improve the
    query, the plan keeps the text he typed rather than losing the request.
    """
    try:
        from ..media.search_intelligence import compiled_web_query_parameters

        compiled = compiled_web_query_parameters({"query": text})
        return str(compiled.get("query") or text)
    except Exception:
        logger.warning("web_search query normalization failed; using the raw goal text", exc_info=True)
        return text


class AgentPlanner:
    """Plans multi-step execution graphs and adapts plans dynamically

    when step results fail or new information is discovered.
    """

    def create_plan(self, goal: AgentGoal, context: dict[str, Any] | None = None) -> list[PlanStep]:
        """Creates an initial plan (DAG of steps) to fulfill the user's goal."""
        ctx = context or {}
        text = goal.text.strip()
        steps: list[PlanStep] = []

        # 1. Detect multi-step comparison/research workflows
        is_comparison_research = bool(
            re.search(r"\b(compare|versus|vs|best\s+\w+\s+(?:under|below|for)|recommend\s+and\s+compare)\b", text, re.I)
            and re.search(r"\b(laptop|pc|phone|gpu|car|product|monitor|camera|headphone)\b", text, re.I)
        )

        is_deep_research_report = bool(
            re.search(r"\b(deep\s+research|comprehensive\s+report|market\s+analysis|investigate\s+and\s+report)\b", text, re.I)
            or (re.search(r"\b(research|investigate)\b", text, re.I) and re.search(r"\b(report|pdf|document|save)\b", text, re.I))
        )

        if is_comparison_research or is_deep_research_report:
            goal.goal_type = GoalType.MULTI_STEP_RESEARCH
            search_query = normalized_web_query(text)
            # Step 1: Search market candidates
            step1 = PlanStep(
                title=f"Market Search: {search_query[:40]}...",
                skill_id="web_search",
                parameters={"query": search_query},
                risk_tier=0,
                depends_on=[],
            )
            # Step 2: Extract & compare specifications
            step2 = PlanStep(
                title="Synthesize and Rank Options",
                skill_id="web_answer",
                parameters={"query": f"Compare and rank options found for: {text}"},
                risk_tier=0,
                depends_on=[step1.step_id],
            )
            steps = [step1, step2]

            # If user explicitly asked to save or document
            if re.search(r"\b(pdf|document|save|report|file)\b", text, re.I):
                step3 = PlanStep(
                    title="Compile Summary Document",
                    skill_id="pdf_generate",
                    parameters={"topic": text, "title": f"Analysis: {text[:30]}"},
                    risk_tier=1,
                    depends_on=[step2.step_id],
                )
                steps.append(step3)

            return steps

        # 2. Image generation workflow
        is_image_gen = bool(re.search(r"\b(generate|create|make|draw|paint)\b.*\b(image|picture|photo|portrait|art)\b", text, re.I))
        if is_image_gen:
            goal.goal_type = GoalType.CREATIVE_GENERATION
            clean_prompt = re.sub(r"(?i)^\s*(?:please\s+)?(?:generate|create|make|draw|paint)\s+(?:an?\s+)?(?:image|picture|photo|portrait)?\s*(?:of\s+)?", "", text).strip()
            steps.append(PlanStep(
                title=f"Generate Image: {clean_prompt[:30]}",
                skill_id="image_generate",
                parameters={"prompt": clean_prompt or text, "count": 1, "mode": "quality"},
                risk_tier=1,
            ))
            return steps

        # 3. Image search workflow
        is_image_search = bool(
            re.search(r"\b(images?|pictures?|photos?|pics?|wallpaper)\b", text, re.I)
            and re.search(r"\b(show|find|search|fetch|get|see)\b", text, re.I)
        )
        if is_image_search:
            goal.goal_type = GoalType.INFORMATIONAL
            clean_query = re.sub(r"(?i)\b(images?|pictures?|photos?|pics?|wallpaper|show\s+me|fetch|find|search)\b", "", text).strip()
            clean_query = re.sub(r"\s+", " ", clean_query).strip()
            steps.append(PlanStep(
                title=f"Search Visuals: {clean_query or text}",
                skill_id="image_search",
                parameters={"query": clean_query or text, "count": 6},
                risk_tier=0,
            ))
            return steps

        # 4. Standard informational web research
        is_web_query = bool(
            re.search(r"\b(search|research|lookup|current|latest|news|what\s+is|who\s+is|how\s+to|why\s+is)\b", text, re.I)
        )
        if is_web_query:
            goal.goal_type = GoalType.INFORMATIONAL
            search_query = normalized_web_query(text)
            steps.append(PlanStep(
                title=f"Web Knowledge Retrieval: {search_query[:35]}",
                skill_id="web_search",
                parameters={"query": search_query},
                risk_tier=0,
            ))
            return steps

        # Default fast conversational step (direct LLM synthesis)
        steps.append(PlanStep(
            title="Conversational Synthesis",
            skill_id="conversational_synthesis",
            parameters={"prompt": text},
            risk_tier=0,
        ))
        return steps

    def replan(
        self,
        goal: AgentGoal,
        failed_step: PlanStep,
        verification: VerificationReport,
        current_steps: list[PlanStep],
    ) -> list[PlanStep]:
        """Dynamically adapts the step graph after a failure or verification deficiency."""
        updated_steps: list[PlanStep] = []

        for step in current_steps:
            if step.step_id == failed_step.step_id:
                # If retries remain on this step, retry with altered parameters
                if step.retry_count < step.max_retries:
                    step.retry_count += 1
                    step.status = StepStatus.PENDING
                    step.error = None

                    # Apply replan guidance to parameters if available
                    if step.skill_id == "web_search":
                        orig_q = step.parameters.get("query", "")
                        # Broaden or simplify query
                        step.parameters["query"] = re.sub(r"\b(please|latest|best|current|today)\b", "", orig_q, flags=re.I).strip()
                    elif step.skill_id == "image_search":
                        orig_q = step.parameters.get("query", "")
                        step.parameters["query"] = f"{orig_q} aesthetic wallpaper"

                    updated_steps.append(step)
                else:
                    # Retries exhausted - mark failed and inject fallback step
                    step.status = StepStatus.FAILED
                    updated_steps.append(step)

                    # Inject fallback alternative
                    if step.skill_id == "web_research":
                        fallback_step = PlanStep(
                            title=f"Fallback Search: {step.title}",
                            skill_id="web_search",
                            parameters=step.parameters,
                            risk_tier=0,
                            depends_on=step.depends_on,
                        )
                        updated_steps.append(fallback_step)
            else:
                updated_steps.append(step)

        return updated_steps
