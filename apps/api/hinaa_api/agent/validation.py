from __future__ import annotations

from .contracts import AgentPlan, OperationType, StepState


class PlanValidationError(ValueError):
    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


class PlanValidator:
    def __init__(self, max_steps: int = 12, allowed_tools: set[str] | None = None):
        self.max_steps = max_steps
        self.allowed_tools = allowed_tools

    def validate(self, plan: AgentPlan) -> AgentPlan:
        issues: list[str] = []
        ids = [step.step_id for step in plan.steps]
        if len(ids) != len(set(ids)): issues.append("duplicate step id")
        if not plan.steps: issues.append("plan must contain at least one step")
        if len(plan.steps) > self.max_steps: issues.append("maximum step count exceeded")
        known = set(ids); idem: set[str] = set()
        for step in plan.steps:
            if any(dep not in known for dep in step.dependencies): issues.append(f"missing dependency for {step.step_id}")
            if step.idempotency_key in idem: issues.append("duplicate idempotency key")
            idem.add(step.idempotency_key)
            if step.status != StepState.PENDING: issues.append(f"step {step.step_id} must start pending")
            if step.operation_type == OperationType.TOOL and not step.tool_name: issues.append(f"tool step {step.step_id} missing tool")
            if step.operation_type == OperationType.TOOL and self.allowed_tools is not None and step.tool_name not in self.allowed_tools:
                issues.append(f"unknown tool: {step.tool_name}")
            if step.tool_name and "video" in step.tool_name.lower(): issues.append("video generation is forbidden")
            if "user_id" in step.tool_parameters or "userId" in step.tool_parameters: issues.append("identity override is forbidden")
            if any(k in step.tool_parameters for k in ("max_steps", "maximum_steps", "limit_override", "run_timeout")):
                issues.append("runtime limit override is forbidden")
        graph = {step.step_id: set(step.dependencies) for step in plan.steps}
        visiting: set[str] = set(); visited: set[str] = set()
        def visit(node: str) -> None:
            if node in visiting: issues.append("dependency cycle detected"); return
            if node in visited: return
            if node not in graph: return
            visiting.add(node)
            for dep in graph[node]: visit(dep)
            visiting.remove(node); visited.add(node)
        for node in graph: visit(node)
        if issues: raise PlanValidationError(issues)
        return plan
