from __future__ import annotations

from typing import Any, Callable, TypedDict

from langgraph.graph import END, StateGraph

# Shared LangGraph scaffolding for every cognitive agent in this package —
# Thalamus, Sensory Cortex, Hippocampus, Prefrontal Cortex, Amygdala, and
# Broca's Area (ADD §8; the body/brain-region naming carries over from the
# rest of this codebase's Brain 1/Brain 2/Eyes/Ears/Mouth/Spinal Cord
# metaphor). Each agent module defines its own node function(s) — the actual
# prompt-building and model calls — and hands them to one of the two
# builders below. The agent CLASS in that same module, which implements the
# shared `Agent` protocol (`plan`/`execute_step`, what `workflow/graph.py`'s
# outer StateGraph calls), does almost nothing itself: it plans one
# PlanStep and invokes this compiled graph. The graph — not the class — is
# where an agent's actual workflow and reasoning live, and this per-agent
# graph is what `execute_step` calls into: the connection from the outer,
# shared workflow down to this agent's own one.


class NodeState(TypedDict):
    args: dict[str, Any]
    result: dict[str, Any]


NodeFn = Callable[[dict[str, Any]], dict[str, Any]]


def single_node_graph(node_name: str, fn: NodeFn):
    """One node, one job — for an agent with exactly one operation."""

    def _node(state: NodeState) -> NodeState:
        return {'args': state['args'], 'result': fn(state['args'])}

    graph = StateGraph(NodeState)
    graph.add_node(node_name, _node)
    graph.set_entry_point(node_name)
    graph.add_edge(node_name, END)
    return graph.compile()


def router_graph(nodes: dict[str, NodeFn], default: str, route_key: str = 'operation'):
    """Several operations, one agent — routes on `args[route_key]` to the

    matching node. For an agent whose job genuinely branches (Prefrontal
    Cortex: reflect on a moment vs. summarize a period vs. decide a next
    step) this is a real conditional edge over real nodes, not an if/elif
    chain buried inside one Python method.
    """

    def _wrap(fn: NodeFn) -> Callable[[NodeState], NodeState]:
        def _node(state: NodeState) -> NodeState:
            return {'args': state['args'], 'result': fn(state['args'])}

        return _node

    def _route(state: NodeState) -> str:
        operation = state['args'].get(route_key) or default
        return operation if operation in nodes else default

    graph = StateGraph(NodeState)
    for name, fn in nodes.items():
        graph.add_node(name, _wrap(fn))
        graph.add_edge(name, END)

    graph.set_conditional_entry_point(_route, {name: name for name in nodes})
    return graph.compile()


def run(graph, args: dict[str, Any]) -> dict[str, Any]:
    """Invokes a compiled agent graph and hands back just its `result` —

    what every agent's `execute_step` calls, matching the `Agent` protocol's
    `execute_step(step) -> dict[str, Any]` return shape.
    """
    final_state: NodeState = graph.invoke({'args': args, 'result': {}})
    return final_state['result']
