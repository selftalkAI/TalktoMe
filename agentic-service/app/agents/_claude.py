from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..config import settings
from ..model_gateway import ModelProviderUnavailable

# Claude engine for Brain 2's actions. When AGENT_ENGINE=claude, every agent's
# `execute_step` still goes through `_graph.run` exactly as before — same
# PlanStep, same PolicyGate, same HTTP contract to Orchestration — but instead
# of running the LangGraph node (which calls Ollama/Bedrock), `run` hands the
# SAME input payload to the matching Claude agent in `.claude/agents/` and
# returns the SAME result shape. Nothing above this function knows which
# engine answered.
#
# It runs the Claude Code CLI headless (`claude -p --agent <name>`), so it uses
# whatever account `claude` is signed in with — a Claude subscription works,
# no API key needed. Each agent has no tools (`--tools ""`): these are pure
# language actions over the payload they're given.

AGENT_FILES: dict[str, str] = {
    'thalamus': 'brain2-thalamus',
    'sensory_cortex': 'brain2-sensory-cortex',
    'hippocampus': 'brain2-hippocampus',
    'prefrontal_cortex': 'brain2-prefrontal-cortex',
    'amygdala': 'brain2-amygdala',
    'broca': 'brain2-broca',
    'world_knowledge': 'brain2-world-knowledge',
    'brain_one': 'brain1-simulator',
}

# The exact keys (and fallback values) each Python agent has always returned —
# Orchestration reads these, so a Claude answer is coerced to the same shape.
_RESULT_SHAPES: dict[str, dict[str, Any]] = {
    'thalamus': {'opening_message': ''},
    'sensory_cortex': {'mood_summary': '', 'context_notes': '', 'narrative_focus': ''},
    'hippocampus': {'candidates': []},
    'prefrontal_cortex:reflect_moment': {'reflection': ''},
    'prefrontal_cortex:evolution_narrative': {'narrative': ''},
    'prefrontal_cortex:suggest_next_step': {'welcome_message': '', 'suggested_first_action': ''},
    'amygdala': {'message': '', 'suggested_target_minutes': None},
    'broca': {'content': ''},
    'world_knowledge': {'benchmark': ''},
    'brain_one': {'user_message': ''},
}


def supports(agent: str | None) -> bool:
    return bool(agent) and agent in AGENT_FILES


def run_agent(agent: str, args: dict[str, Any]) -> dict[str, Any]:
    """Runs one Brain 2 action on Claude and returns the Python agent's result shape."""
    early = _deterministic_shortcut(agent, args)
    if early is not None:
        return early

    raw = _invoke_cli(AGENT_FILES[agent], json.dumps(args, default=str))
    parsed = _extract_json(raw)
    return _normalize(agent, args, parsed, raw)


def _deterministic_shortcut(agent: str, args: dict[str, Any]) -> dict[str, Any] | None:
    """The same no-model early returns the Python agents make — no point
    spending a Claude call on an empty input."""
    if agent == 'hippocampus' and not (args.get('source_text') or '').strip():
        return {'candidates': []}
    if agent == 'world_knowledge' and not (args.get('context') or '').strip():
        return {'benchmark': ''}
    if agent == 'prefrontal_cortex' and _operation(args) == 'evolution_narrative' and len(args.get('moments') or []) < 2:
        return {
            'narrative': (
                "There isn't enough history yet to see a pattern — keep capturing moments "
                'and this will fill in.'
            )
        }
    return None


def _operation(args: dict[str, Any]) -> str:
    return args.get('operation') or args.get('mode') or 'reflect_moment'


def _invoke_cli(agent_file: str, payload: str) -> str:
    cli = settings.claude_cli or 'claude'
    if shutil.which(cli) is None and not Path(cli).exists():
        raise ModelProviderUnavailable(
            f"AGENT_ENGINE=claude but the Claude Code CLI ('{cli}') isn't installed or on PATH. "
            'Install Claude Code and run `claude` once to sign in, or set AGENT_ENGINE=langgraph.'
        )
    cmd = [
        cli, '-p',
        '--agent', agent_file,
        '--output-format', 'json',
        '--tools', '',
        '--no-session-persistence',
        '--max-turns', '2',
    ]
    if settings.claude_model:
        cmd += ['--model', settings.claude_model]
    cmd.append('Input JSON:\n' + payload)

    try:
        proc = subprocess.run(
            cmd,
            cwd=settings.claude_project_dir,
            capture_output=True,
            text=True,
            timeout=settings.claude_timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise ModelProviderUnavailable(f'Claude agent {agent_file} timed out after {settings.claude_timeout_seconds}s') from exc

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or '').strip()[:400]
        raise ModelProviderUnavailable(f'Claude agent {agent_file} failed: {detail or "exit " + str(proc.returncode)}')

    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.stdout  # older CLI or text output — parse what we got
    if envelope.get('is_error'):
        raise ModelProviderUnavailable(f"Claude agent {agent_file} returned an error: {str(envelope.get('result'))[:400]}")
    return str(envelope.get('result') or '')


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    fenced = re.match(r'^```(?:json)?\s*(.*?)\s*```$', text, re.S)
    if fenced:
        text = fenced.group(1)
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        start, end = text.find('{'), text.rfind('}')
        if start != -1 and end > start:
            try:
                value = json.loads(text[start:end + 1])
                return value if isinstance(value, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def _normalize(agent: str, args: dict[str, Any], parsed: dict[str, Any] | None, raw: str) -> dict[str, Any]:
    key = f'{agent}:{_operation(args)}' if agent == 'prefrontal_cortex' else agent
    shape = _RESULT_SHAPES[key]
    if parsed is None:
        # Same fallback the Python agents use: keep the text in the main field.
        first = next(iter(shape))
        parsed = {first: raw.strip()} if isinstance(shape[first], str) else {}

    result = {k: parsed.get(k, default) for k, default in shape.items()}

    if agent == 'hippocampus' and not isinstance(result['candidates'], list):
        result['candidates'] = []
    if agent == 'amygdala' and not isinstance(result['suggested_target_minutes'], int):
        result['suggested_target_minutes'] = None
    if key == 'prefrontal_cortex:reflect_moment':
        result['referenced_past_count'] = len(args.get('past_moments') or [])
    for k, v in result.items():
        if isinstance(v, str):
            result[k] = v.strip()
    return result
