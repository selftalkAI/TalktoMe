from __future__ import annotations

import json
from datetime import date
from typing import Any

from ..model_gateway import get_model_provider
from ..workflow.models import PlanStep
from ..workflow.state import RiskClass


class ProfileAgent:
    """Opens the conversation and understands the person — it never decides or acts.

    Two operations, both grounded only in what this one person told us about
    themselves (name, location, interests, chosen quote) or just said in their
    own words — never outside facts or other people's data:

    - open_conversation: a warm, personal opening line — the way a parent, or a
      close friend, would start. It leads with something genuinely engaging
      (drawing on general knowledge — season, place, something tied to their
      age/interests) rather than interrogating them with a status-check
      question like "how's life been" or "any trips planned?".
    - understand: takes what they said back and turns it into structured
      understanding (mood_summary, context_notes, narrative_focus) — no advice,
      no suggested actions, nothing performed. That understanding is what gets
      handed to the next agent (SmartAgent) to actually decide what this person
      needs and act on it.
    """

    name = 'profile'

    def plan(self, goal: str) -> list[PlanStep]:
        payload = json.loads(goal)
        operation = payload.get('operation', 'open_conversation')
        return [
            PlanStep(
                tool='profile_agent',
                operation=operation,
                risk_class=RiskClass.READ_ONLY,
                args=payload,
            )
        ]

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        if step.operation == 'open_conversation':
            return self._open_conversation(step.args)
        if step.operation == 'understand':
            return self._understand(step.args)
        raise ValueError(f"ProfileAgent does not support operation '{step.operation}'")

    def _open_conversation(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile_lines = self._profile_lines(payload)

        system_prompt = (
            "You are opening a conversation with ONE person, the way a parent or a close "
            "friend would greet someone they care about — warm, specific, unhurried. "
            "Do NOT open with a status-check question like 'how's life been' or 'any trips "
            "planned lately?' — that reads as interrogating them, not caring about them. "
            "Instead, lead with something that would genuinely excite or interest THIS person "
            "to begin with: you may draw on your own general knowledge (the season, a real "
            "event or landmark in their city, an idea or angle tied to their age and interests, "
            "their family context if their interests imply one) to make it concrete and "
            "current — but it must stay clearly tailored to who they are below, never random "
            "trivia. NEVER claim to have seen, heard, or experienced something specific from "
            "THIS person — their photos, a trip they took, something they did — unless they "
            "actually told you that below; inventing a shared memory that didn't happen is "
            "dishonest, even if it sounds warm. For example, never write anything like 'I saw "
            "your photos from...', 'I remember when you...', or 'thinking of your photos from "
            "last year's...' — you have never seen or heard anything about them beyond exactly "
            "what is written below. General knowledge (a festival happening, the season, a "
            "place) is fine; fabricated personal history about them is not. Write 1-2 "
            "sentences, second person, using their first name. You may end with a light, "
            "natural opening for them to jump in, but the excitement comes first — this is not "
            "a question-and-answer form. Do not suggest anything for them to do — you are only "
            "opening the door."
        )
        prompt = 'Here is what this person told us about themselves:\n' + '\n'.join(profile_lines)

        provider = get_model_provider()
        opening_message = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)
        return {'opening_message': opening_message.strip()}

    def _understand(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile_lines = self._profile_lines(payload)
        response_text = (payload.get('response_text') or '').strip()

        system_prompt = (
            "You are ONLY listening and understanding right now — you never give advice, "
            "suggest actions, or decide anything for this person. Given their profile and what "
            "they just said about how they're doing, produce structured understanding for "
            "another agent to act on later. Respond with strict JSON only, no markdown fencing, "
            'matching exactly this shape: {"mood_summary": "...", "context_notes": "...", '
            '"narrative_focus": "..."}.\n'
            "- mood_summary: a short, empathetic characterization of how they seem to be feeling "
            "right now, grounded only in their own words.\n"
            "- context_notes: anything specific they mentioned (an event, a worry, a win) that "
            "another agent should know about — empty string if nothing notable.\n"
            "- narrative_focus: 5-10 words naming the emotional/thematic lens their reflections "
            "should favor right now, grounded in both their stated interests and how they say "
            "they're feeling."
        )
        prompt = (
            'Profile:\n'
            + '\n'.join(profile_lines)
            + '\n\nWhat they just said when asked how they\'re doing:\n'
            + (response_text or '(they didn\'t say anything)')
        )

        provider = get_model_provider()
        response = provider.chat([{'role': 'user', 'content': prompt}], system=system_prompt)

        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            parsed = {'mood_summary': response.strip()}

        return {
            'mood_summary': parsed.get('mood_summary', ''),
            'context_notes': parsed.get('context_notes', ''),
            'narrative_focus': parsed.get('narrative_focus', ''),
        }

    @staticmethod
    def _profile_lines(payload: dict[str, Any]) -> list[str]:
        full_name = (payload.get('full_name') or '').strip() or 'there'
        location = payload.get('location')
        interests: list[str] = payload.get('interests') or []
        other_interests = payload.get('other_interests')
        quote = payload.get('quote')
        age = ProfileAgent._age_from_dob(payload.get('dob'))

        lines = [f'Name: {full_name}']
        if age is not None:
            lines.append(f'Age: {age}')
        if location:
            lines.append(f'Location: {location}')
        if interests:
            lines.append(f"Selected interests: {', '.join(interests)}")
        if other_interests:
            lines.append(f'Other interests they typed in: {other_interests}')
        if quote:
            lines.append(f'Personal quote they chose: "{quote}"')
        return lines

    @staticmethod
    def _age_from_dob(dob: str | None) -> int | None:
        if not dob:
            return None
        try:
            birth = date.fromisoformat(dob[:10])
        except ValueError:
            return None
        today = date.today()
        return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
