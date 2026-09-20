from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.types import Command

from .graph import build_workflow_graph
from .models import AgentRun, PlanStep
from .observer import Observer
from .policy_gate import PolicyGate
from .state import RunStatus, StepStatus

# AgentRun/PlanStep and their enum fields are plain dataclasses/enums, not one of
# msgpack's built-in types, so the checkpointer's serializer must be told they're
# safe to round-trip (otherwise it warns now and will refuse to deserialize them
# once LangGraph's strict msgpack mode becomes the default).
_CHECKPOINT_SERDE = JsonPlusSerializer(
    allowed_msgpack_modules=[
        ('app.workflow.models', 'AgentRun'),
        ('app.workflow.models', 'PlanStep'),
        ('app.workflow.state', 'RunStatus'),
        ('app.workflow.state', 'StepStatus'),
        ('app.workflow.state', 'RiskClass'),
        ('app.workflow.state', 'PolicyDecision'),
    ]
)


def _default_agent_resolver(name: str):
    # Deferred import: agents/*.py import from workflow.models/state, so importing
    # the agents package at module load time here would create a circular import.
    from ..agents import get_agent

    return get_agent(name)


class WorkflowEngine:
    """Runs the Planner -> PolicyGate -> Executor -> Observer loop (ADD §8) as a

    compiled LangGraph StateGraph (see graph.py). One instance holds a single
    in-memory checkpointer covering every in-flight run (MVP scaffold — see the
    durability note on AgentRun); each run gets its own graph thread keyed by
    run_id, so a step waiting on approval genuinely pauses (via `interrupt()`)
    between the `start`/`approve_step` HTTP calls instead of being re-simulated
    by hand. Orchestration is expected to be the one calling this, the same way
    it calls the Model Gateway endpoints.
    """

    def __init__(self, agent_resolver: Callable[[str], object] | None = None) -> None:
        self._runs: dict[str, AgentRun] = {}
        self._policy_gate = PolicyGate()
        self._observer = Observer()
        self._resolve_agent = agent_resolver or _default_agent_resolver
        graph = build_workflow_graph(self._resolve_agent, self._policy_gate, self._observer)
        self._app = graph.compile(checkpointer=MemorySaver(serde=_CHECKPOINT_SERDE))

    def create_run(self, agent_name: str, user_id: str, goal: str) -> AgentRun:
        self._resolve_agent(agent_name)  # raises KeyError early if the agent name is unknown
        run = AgentRun(user_id=user_id, agent_name=agent_name, goal=goal)
        self._runs[run.run_id] = run
        self._observer.record(run, f"run created for agent '{agent_name}'")
        return run

    def start(self, run_id: str) -> AgentRun:
        run = self._get_run(run_id)
        result = self._app.invoke({'run': run}, config=self._thread_config(run_id))
        return self._apply_result(run_id, result)

    def approve_step(self, run_id: str, step_id: str) -> AgentRun:
        run = self._get_run(run_id)
        if run.status != RunStatus.WAITING_APPROVAL:
            raise KeyError(f'Run {run_id} is not waiting for approval')
        step = self._find_step(run, step_id)
        if step.status != StepStatus.WAITING_APPROVAL:
            raise KeyError(f'Step {step_id} on run {run_id} is not waiting for approval')

        result = self._app.invoke(Command(resume=True), config=self._thread_config(run_id))
        return self._apply_result(run_id, result)

    def cancel(self, run_id: str) -> AgentRun:
        run = self._get_run(run_id)
        if run.status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED):
            return run
        run.status = RunStatus.CANCELLED
        run.completed_at = datetime.now(timezone.utc)
        self._observer.record(run, 'run cancelled by user')
        return run

    def get_run(self, run_id: str) -> AgentRun:
        return self._get_run(run_id)

    def _apply_result(self, run_id: str, result: dict[str, Any]) -> AgentRun:
        run: AgentRun = result['run']

        interrupts = result.get('__interrupt__')
        if interrupts:
            payload = interrupts[0].value
            step = self._find_step(run, payload['step_id'])
            step.status = StepStatus.WAITING_APPROVAL
            run.status = RunStatus.WAITING_APPROVAL
            self._observer.record(run, f'step {step.step_id} waiting for approval')

        self._runs[run_id] = run
        return run

    @staticmethod
    def _thread_config(run_id: str) -> dict[str, Any]:
        # One LangGraph thread per run, so its paused/resumed state lives in the
        # checkpointer keyed by run_id, matching the run_id the HTTP API already uses.
        return {'configurable': {'thread_id': run_id}}

    def _get_run(self, run_id: str) -> AgentRun:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(f'Unknown run {run_id}')
        return run

    @staticmethod
    def _find_step(run: AgentRun, step_id: str) -> PlanStep:
        for step in run.steps:
            if step.step_id == step_id:
                return step
        raise KeyError(f'Unknown step {step_id} on run {run.run_id}')
