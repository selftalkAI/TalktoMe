from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from .models import AgentRun, PlanStep
from .observer import Observer
from .policy_gate import PolicyGate
from .state import PolicyDecision, RunStatus, StepStatus

_TERMINAL_STEP_STATUSES = {StepStatus.COMPLETED, StepStatus.DENIED, StepStatus.FAILED}


class GraphState(TypedDict):
    """LangGraph channel schema. `run` is the same mutable AgentRun the

    WorkflowEngine hands back to callers — nodes mutate it in place and
    return it unchanged so a paused (interrupted) invoke still carries
    every already-completed step's result.
    """

    run: AgentRun


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_workflow_graph(
    resolve_agent: Callable[[str], object],
    policy_gate: PolicyGate,
    observer: Observer,
):
    """Builds the Planner -> PolicyGate -> Executor -> Observer loop (ADD §8) as a

    LangGraph StateGraph. The four roles map onto graph nodes: `plan` is the
    Planner, `execute_step` runs the PolicyGate check then the Executor (using
    LangGraph's `interrupt()` to pause on CONSEQUENTIAL_WRITE/HIGH_IMPACT steps
    pending approval), and `observer.record(...)` calls from every node are the
    Observer. A compiled graph is returned; the caller supplies the checkpointer
    so each run's thread (keyed by run_id) can pause and resume across separate
    HTTP requests.
    """

    def plan_node(state: GraphState) -> GraphState:
        run = state['run']
        agent = resolve_agent(run.agent_name)
        run.status = RunStatus.PLANNING
        run.steps = agent.plan(run.goal)
        run.status = RunStatus.RUNNING
        observer.record(run, f'planned {len(run.steps)} step(s)')
        return {'run': run}

    def execute_step_node(state: GraphState) -> GraphState:
        run = state['run']
        agent = resolve_agent(run.agent_name)
        step = _next_pending_step(run)
        if step is None:
            return {'run': run}

        decision = policy_gate.evaluate(step)

        if decision == PolicyDecision.DENY:
            step.status = StepStatus.DENIED
            observer.record(run, f'step {step.step_id} denied by policy')
            return {'run': run}

        if decision == PolicyDecision.REQUIRE_APPROVAL and not step.approved:
            # Pauses here; code above this point re-runs (side-effect-free) on
            # resume, then step.approved below picks up the resume value.
            interrupt(
                {
                    'step_id': step.step_id,
                    'tool': step.tool,
                    'operation': step.operation,
                    'risk_class': step.risk_class,
                }
            )
            step.approved = True

        try:
            step.result = agent.execute_step(step)
        except Exception as exc:  # noqa: BLE001 - a tool failure must become a failed step, never a raw 500 (FR-AGT-007)
            step.status = StepStatus.FAILED
            step.result = {'error': str(exc)}
            observer.record(run, f'step {step.step_id} failed: {exc}')
            return {'run': run}

        step.status = StepStatus.COMPLETED
        observer.record(run, f'step {step.step_id} completed')
        return {'run': run}

    def route_after_execute(state: GraphState) -> str:
        run = state['run']
        if any(s.status in (StepStatus.FAILED, StepStatus.DENIED) for s in run.steps):
            return 'finalize'
        if _next_pending_step(run) is not None:
            return 'execute_step'
        return 'finalize'

    def finalize_node(state: GraphState) -> GraphState:
        run = state['run']
        failed = any(s.status in (StepStatus.FAILED, StepStatus.DENIED) for s in run.steps)
        run.status = RunStatus.FAILED if failed else RunStatus.COMPLETED
        run.completed_at = _utcnow()
        observer.record(run, 'run failed' if failed else 'run completed')
        return {'run': run}

    graph = StateGraph(GraphState)
    graph.add_node('plan', plan_node)
    graph.add_node('execute_step', execute_step_node)
    graph.add_node('finalize', finalize_node)

    graph.set_entry_point('plan')
    graph.add_edge('plan', 'execute_step')
    graph.add_conditional_edges(
        'execute_step', route_after_execute, {'execute_step': 'execute_step', 'finalize': 'finalize'}
    )
    graph.add_edge('finalize', END)

    return graph


def _next_pending_step(run: AgentRun) -> PlanStep | None:
    for step in run.steps:
        if step.status not in _TERMINAL_STEP_STATUSES:
            return step
    return None
