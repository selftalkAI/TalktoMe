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
        if step.operation == 'suggest_next_step':
            return self._suggest_next_step(step.args)
        if step.operation == 'extract_memories':
            return self._extract_memories(step.args)
        raise ValueError(f"SmartAgent does not support operation '{step.operation}'")

    def _reflect_moment(self, payload: dict[str, Any]) -> dict[str, Any]:
        moment = payload['moment']
        past_moments: list[dict[str, Any]] = payload.get('past_moments', [])
        relevant_memories: list[dict[str, Any]] = payload.get('relevant_memories', [])
        context_lines = [self._format_moment(m) for m in past_moments]
        memory_lines = [f"- ({m.get('type')}) {m.get('content')}" for m in relevant_memories]

        system_prompt = (
            "You are reflecting ONE person's own thoughts back to them. Everything you say must be "
            "grounded ONLY in the moments and durable memories listed below, which are all authored "
            "by or true of this same person. You must NEVER introduce outside facts, other people's "
            "opinions, general knowledge, or generic advice that isn't grounded in their own words. "
            "If nothing in their past connects to today's moment, say plainly that this feels new "
            "rather than inventing a connection. Write directly to them, in second person ('you'). "
            "Structure your reflection in three short parts, no headers, just flowing text: "
            "(1) what this moment seems to be about, in their own terms; "
            "(2) how it connects to or differs from their own past moments or known preferences/goals, "
            "citing specifics when relevant; "
            "(3) one gentle, specific observation or question — grounded only in patterns in their own "
            "data — to help them build on this thought."
            + self._narrative_focus_clause(payload)
        )
        prompt = (
            'Your past moments (oldest to newest):\n'
            + ('\n'.join(context_lines) if context_lines else '(no earlier moments yet — this is your first.)')
            + ('\n\nWhat we durably know about them:\n' + '\n'.join(memory_lines) if memory_lines else '')
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
            + self._narrative_focus_clause(payload)
        )
        prompt = 'Moments from this period (oldest to newest):\n' + '\n'.join(context_lines)

        provider = get_model_provider()
        response_text = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)
        return {'narrative': response_text}

    def _suggest_next_step(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Acts on the ProfileAgent's understanding — this is the "next agent" it hands off

        to. ProfileAgent only listens and interprets; deciding what this person actually
        needs right now, and turning that into a concrete welcome + suggestion, is this
        agent's job, same as reflecting on a moment is.
        """
        full_name = (payload.get('full_name') or '').strip() or 'there'
        interests: list[str] = payload.get('interests') or []
        mood_summary = (payload.get('mood_summary') or '').strip()
        context_notes = (payload.get('context_notes') or '').strip()
        recent_moments: list[dict[str, Any]] = payload.get('recent_moments') or []

        lines = [f'Name: {full_name}']
        if interests:
            lines.append(f"Interests: {', '.join(interests)}")
        if mood_summary:
            lines.append(f'How they seem to be feeling right now: {mood_summary}')
        if context_notes:
            lines.append(f'Specific things they mentioned: {context_notes}')
        if recent_moments:
            lines.append('Their own recent moments (oldest to newest):')
            lines.extend(self._format_moment(m) for m in recent_moments)

        system_prompt = (
            "You are deciding what ONE person needs right now, using ONLY what another agent "
            "already understood about them below — their profile, how they currently seem to "
            "be feeling, and their own past moments if any. Never introduce outside facts, "
            "other people, or generic self-help language; if they seem to be struggling, be "
            "gentle and specific rather than falsely upbeat. Respond with strict JSON only, no "
            'markdown fencing, matching exactly this shape: {"welcome_message": "...", '
            '"suggested_first_action": "..."}.\n'
            '- welcome_message: 1-2 sentences, second person, using their first name, that '
            "acknowledge how they say they're feeling right now (not a generic greeting).\n"
            '- suggested_first_action: one concrete, specific thing to capture as a moment '
            "today, grounded in their interests and current mood/context — never generic advice."
        )
        prompt = 'What is understood about this person right now:\n' + '\n'.join(lines)

        provider = get_model_provider()
        response = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)

        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            parsed = {'welcome_message': response.strip()}

        return {
            'welcome_message': parsed.get('welcome_message', ''),
            'suggested_first_action': parsed.get('suggested_first_action', ''),
        }

    def _extract_memories(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Proposes candidate durable memories from a piece of text (TDD §5 step 2).

        This only proposes — it never decides what actually becomes durable. That
        write-gate decision (confidence/sensitivity thresholds, dedup) is
        deterministic logic in Orchestration's memory_manager, kept outside the
        model per ADR-007: the model proposes, it never authorizes a write.
        """
        source_text = (payload.get('source_text') or '').strip()
        existing: list[str] = payload.get('existing_active_memories') or []
        full_name = (payload.get('full_name') or '').strip() or 'this person'

        if not source_text:
            return {'candidates': []}

        existing_block = (
            (
                '\n\nThings already remembered about them (do not repeat these, propose only '
                'genuinely new information):\n' + '\n'.join(f'- {m}' for m in existing)
            )
            if existing
            else ''
        )

        system_prompt = (
            "You extract durable, reusable personal facts about ONE person from something they "
            "just said, for a personal memory system. Favor precision over volume: it is safer to "
            "propose nothing than to invent or overreach. Only propose a candidate if it would "
            "genuinely be useful to recall in a FUTURE, unrelated conversation — not one-off "
            "conversational filler. Never propose anything about a third party (someone other than "
            "the person speaking) as if it were their own memory. Respond with strict JSON only, no "
            'markdown fencing, matching exactly this shape: {"candidates": [{"type": "...", '
            '"content": "...", "explicitness": "...", "confidence": 0.0, "sensitivity_tier": "...", '
            '"rationale_code": "..."}]}. Return {"candidates": []} if nothing qualifies.\n'
            "- type: one of fact, preference, goal, relationship, event, routine, constraint, "
            "project_context, user_instruction.\n"
            "- content: a short, self-contained statement written in third person about them "
            '(e.g. "Prefers concise, direct communication.").\n'
            "- explicitness: 'explicit' if they stated it directly, 'inferred' if you are reading "
            "between the lines.\n"
            "- confidence: 0.0-1.0, how sure you are this is true and durable.\n"
            "- sensitivity_tier: T2 for ordinary preferences/goals/routines; T3 for health, "
            "financial account detail, government ID, sexual orientation, immigration status, or "
            "legal matters — when in doubt between T2 and T3, choose T3.\n"
            "- rationale_code: one of USER_EXPLICIT, REPEATED_PREFERENCE, INFERRED_FROM_OUTCOME."
        )
        prompt = f'Person: {full_name}\n\nWhat they just said:\n{source_text}' + existing_block

        provider = get_model_provider()
        response = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)

        try:
            parsed = json.loads(response)
            candidates = parsed.get('candidates', [])
            if not isinstance(candidates, list):
                candidates = []
        except json.JSONDecodeError:
            candidates = []

        return {'candidates': candidates}

    @staticmethod
    def _narrative_focus_clause(payload: dict[str, Any]) -> str:
        focus = (payload.get('narrative_focus') or '').strip()
        mood_summary = (payload.get('mood_summary') or '').strip()
        context_notes = (payload.get('context_notes') or '').strip()
        if not focus and not mood_summary and not context_notes:
            return ''

        clause = (
            ' Another agent has already gathered some understanding of this person that you '
            'should let shape your tone and emphasis — but keep grounding everything only in '
            'their actual moments above, never invent detail to fit it:'
        )
        if focus:
            clause += f' their reflections should favor this focus: "{focus}";'
        if mood_summary:
            clause += f' how they seemed to be feeling recently: "{mood_summary}";'
        if context_notes:
            clause += f' specific things they mentioned: "{context_notes}";'
        return clause

    @staticmethod
    def _format_moment(moment: dict[str, Any]) -> str:
        date = str(moment.get('created_at', ''))[:10]
        mood = moment.get('mood') or 'unspecified'
        return f"- ({date}, felt: {mood}) {moment['content']}"
