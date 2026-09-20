from __future__ import annotations

import json
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass


class SmartAgent:
    """The first agent in the multi-agent system — a general reflective reasoner.

    Domain-specific agents (emotional, finance, fun, time-management, ...) will
    follow the same shape: implement Agent, register a name, and let the
    WorkflowEngine's Planner/PolicyGate/Executor/Observer loop handle safety and
    audit. SmartAgent proves the pattern with the one capability that already
    exists end to end: reflecting a person's own moments back to them, grounded
    only in their own data — never outside facts, other people, or generic advice.

    The `goal` string is JSON-encoded structured input (built by Orchestration,
    which owns the Moments data) rather than free text, since this agent reasons
    over a whole context bundle, not a single instruction.
    """

    name = 'smart'

    def plan(self, goal: str) -> list[PlanStep]:
        payload = json.loads(goal)
        mode = payload.get('mode', 'reflect_moment')
        return [
            PlanStep(
                tool='smart_agent',
                operation=mode,
                risk_class=RiskClass.READ_ONLY,  # reasoning over the person's own data, no external effect
                args=payload,
            )
        ]

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        if step.operation == 'reflect_moment':
            return self._reflect_moment(step.args)
        if step.operation == 'evolution_narrative':
            return self._evolution_narrative(step.args)
        raise ValueError(f"SmartAgent does not support operation '{step.operation}'")

    def _reflect_moment(self, payload: dict[str, Any]) -> dict[str, Any]:
        moment = payload['moment']
        past_moments: list[dict[str, Any]] = payload.get('past_moments', [])
        context_lines = [self._format_moment(m) for m in past_moments]

        system_prompt = (
            "You are reflecting ONE person's own thoughts back to them. Everything you say must be "
            "grounded ONLY in the moments listed below, which are all authored by this same person. "
            "You must NEVER introduce outside facts, other people's opinions, general knowledge, or "
            "generic advice that isn't grounded in their own words. If nothing in their past connects "
            "to today's moment, say plainly that this feels new rather than inventing a connection. "
            "Write directly to them, in second person ('you'). "
            "Structure your reflection in three short parts, no headers, just flowing text: "
            "(1) what this moment seems to be about, in their own terms; "
            "(2) how it connects to or differs from their own past moments, citing specific dates/feelings "
            "when relevant; "
            "(3) one gentle, specific observation or question — grounded only in patterns in their own "
            "data — to help them build on this thought."
        )
        prompt = (
            'Your past moments (oldest to newest):\n'
            + ('\n'.join(context_lines) if context_lines else '(no earlier moments yet — this is your first.)')
            + f"\n\nToday's moment (felt: {moment.get('mood') or 'unspecified'}): {moment['content']}"
            + "\n\nReflect on today's moment."
        )

        provider = get_model_provider()
        response_text = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)
        return {'reflection': response_text, 'referenced_past_count': len(context_lines)}

    def _evolution_narrative(self, payload: dict[str, Any]) -> dict[str, Any]:
        moments: list[dict[str, Any]] = payload.get('moments', [])
        if len(moments) < 2:
            return {
                'narrative': (
                    "There isn't enough history yet to see a pattern — keep capturing moments "
                    "and this will fill in."
                )
            }

        context_lines = [self._format_moment(m) for m in moments]
        system_prompt = (
            "You are summarizing how ONE person has changed over a period of time, using ONLY the "
            "moments they themselves recorded below. Never introduce outside facts, other people, or "
            "generic self-help language. Write 3-5 sentences, directly to them ('you'), noting any real "
            "shifts in mood, recurring themes, or a change in how they talk about the same topic over "
            "time. If there's no clear shift, say so honestly instead of inventing one."
        )
        prompt = 'Moments from this period (oldest to newest):\n' + '\n'.join(context_lines)

        provider = get_model_provider()
        response_text = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)
        return {'narrative': response_text}

    @staticmethod
    def _format_moment(moment: dict[str, Any]) -> str:
        date = str(moment.get('created_at', ''))[:10]
        mood = moment.get('mood') or 'unspecified'
        return f"- ({date}, felt: {mood}) {moment['content']}"
