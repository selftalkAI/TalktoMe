"""Serves an interactive Brain 1 <-> Brain 2 conversation for one test profile.

  1. The person types a message. It is routed to its life area (fitness,
     cooking, ...), and Hippocampus remembers what is durable in it.
  2. Brain 1 compiles a Context Pack and picks Brain 2's persona (voice x
     expertise); "talk to me like my sister" sets the voice until changed.
  3. Brain 2 understands, plans, speaks, and checks its reply before it is
     shown (Building_Brain2.md §6). Chat replies are just chat.
  4. Rarely — a goal milestone, or enough new durable facts in an area —
     Brain 2 also offers a separate profile proposal card; only "Yes, save
     it" makes it durable (ADR-014, ADR-022).
  5. If the person goes quiet past the idle window, Brain 2 checks in
     gently on conversations awaiting a reply — never inventing their words
     or numbers.
  For the fitness area, logged minutes drive the deterministic shortfall
  streak and support message, until the 60 min/day goal is reached.

Uses a dedicated profile (`user1.interactive@example.com`), separate from
`simulate_brain1_brain2_hour.py`'s fully-autonomous profile, so the two never
collide.

Usage (from orchestration-service/, with its venv active; agentic-service
must be running on :8001 for real LLM-composed language, else this falls
back to plain deterministic text, same contract as orchestrator.py):

    python3 scripts/serve_interactive_brain2_ui.py [--port 8767] [--idle-seconds 45]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import brain1, memory_manager, memory_repo  # noqa: E402
from app import conversations_repo  # noqa: E402
from app.brain1 import proactive, safety  # noqa: E402
from app.brain2 import intentions_repo, orchestrator  # noqa: E402
from app.spinal_cord import AgenticServiceClient, AgenticServiceError  # noqa: E402

PROFILE_EMAIL = 'user1.interactive@example.com'
GOAL_DOMAIN = 'fitness'  # the one domain with an actual tracked numeric goal
ORIGINAL_TARGET_MINUTES = 60
PROFILE_FACTS = {
    'full_name': 'User One',
    'dob': '1991-04-12',
    'location': 'Austin, TX',
    'interests': ['healthy_living', 'mindfulness'],
    'other_interests': 'cycling on weekends',
    'quote': 'Small steps still move you forward.',
}
# Seeded as an explicit, ACTIVE memory (not a `profiles` column — no schema
# change needed, and this is exactly what the memory layer is for) so Broca
# and Amygdala have real material for personalized benefit-framing in
# check-in mode, the same way the quote/interests do. Sensitivity T3 per
# Hippocampus's own tiering rule for health facts (see hippocampus.py).
HEALTH_CONTEXT = (
    'Early in a fitness journey, currently carrying excess weight; main motivation is '
    'long-term health and energy rather than appearance.'
)

_MINUTES_RE = re.compile(r'(\d+)\s*(?:min\b|mins\b|minutes\b)', re.IGNORECASE)
_DOMAIN_WORD_RE = re.compile(r'[a-z]+')

LOCK = threading.Lock()
THREAD: list[dict] = []
CURRENT: dict[str, dict] = {}  # domain -> {'proposal_id', 'version', 'content'} for its pending profile proposal (rare, ADR-022)
AWAITING: set[str] = set()  # domains where Brain 2 spoke last and the person hasn't replied — what silence check-ins follow up
INTENTION: dict | None = None  # the fitness-domain intention only; no other domain has one in this script
LAST_ACTIVITY = time.monotonic()
GOAL_ACHIEVED = False  # fitness-only milestone
ESCALATION: dict[str, int] = {}  # domain -> consecutive re-engagement attempts with no real response
IDLE_SECONDS = 45  # set from CLI in main()


def _ensure_profile_and_intention() -> None:
    global INTENTION
    is_new = brain1.get(PROFILE_EMAIL) is None
    if is_new:
        brain1.create(
            email=PROFILE_EMAIL,
            full_name=PROFILE_FACTS['full_name'],
            password='interactive-only-123',
            dob=PROFILE_FACTS['dob'],
            location=PROFILE_FACTS['location'],
            interests=PROFILE_FACTS['interests'],
            other_interests=PROFILE_FACTS['other_interests'],
            photo_data_url=None,
            quote=PROFILE_FACTS['quote'],
        )
        memory_repo.create_memory(
            profile_email=PROFILE_EMAIL,
            memory_type='fact',
            domain=GOAL_DOMAIN,
            content=HEALTH_CONTEXT,
            explicitness='explicit',
            confidence=1.0,
            sensitivity_tier='T3',
            status=memory_repo.ACTIVE,
            rationale_code='USER_EXPLICIT',
            source_type='user',
        )
    active = intentions_repo.get_active_intention(PROFILE_EMAIL, GOAL_DOMAIN)
    INTENTION = active or orchestrator.set_intention(PROFILE_EMAIL, GOAL_DOMAIN, title='Gym', target_minutes=ORIGINAL_TARGET_MINUTES)


def _classify_domain(text: str) -> str:
    """Which life domain this message is actually about — e.g. 'cooking'

    vs. 'fitness' — so a message about dinner never gets forced through the
    gym intention's grounding just because that's the only domain this
    script used to know about. A real LLM call, not a keyword match, since
    Profile domains are an open set (ADD §6.1), not a fixed enum; falls back
    to 'general' if the call fails or returns something unusable, never
    blocking the message itself.
    """
    system_prompt = (
        "Classify which single life domain this message is mainly about. Respond with ONLY "
        "one lowercase word, nothing else — no punctuation, no explanation. Prefer one of: "
        "fitness, cooking, reading, career, finance, relationships, learning, emotion, home, "
        "travel — but if none of those genuinely fit, invent a short one-word domain that does."
    )
    try:
        client = AgenticServiceClient()
        result = client.complete(text, system_prompt)
        response = (result.get('response') or '').strip().lower()
        match = _DOMAIN_WORD_RE.search(response)
        return match.group(0) if match else 'general'
    except AgenticServiceError:
        return 'general'


def _append(kind: str, text: str, **extra) -> dict:
    entry = {'kind': kind, 'text': text, 'at': datetime.now(timezone.utc).isoformat(), **extra}
    THREAD.append(entry)
    return entry


def _extract_minutes(text: str) -> int | None:
    m = _MINUTES_RE.search(text or '')
    return int(m.group(1)) if m else None


def _domain_turns(domain: str) -> list[dict[str, str]]:
    """This domain's thread so far as real chat turns, oldest to newest —
    what makes a reply like "how do I do that?" ground-able, and what lets
    Brain 2's Check catch it repeating itself. Call this BEFORE appending the
    current turn, so it never includes itself.
    """
    turns: list[dict[str, str]] = []
    for entry in THREAD:
        if entry.get('domain') != domain:
            continue
        if entry['kind'] == 'user':
            turns.append({'role': 'user', 'content': entry['text']})
        elif entry['kind'] in ('brain2', 'brain2_support'):
            turns.append({'role': 'assistant', 'content': entry['text']})
    return turns


def _process_turn(text: str, domain: str) -> None:
    """A real message from User 1, already routed to its domain. The idle
    watchdog uses `_process_auto_nudge` instead, which never fabricates user
    input. Only the fitness domain's checkin/support machinery runs; every
    other domain gets the plain conversation path (ADD §6.1). Always ends
    with one checked Brain 2 reply; a profile proposal appears only when
    Brain 2's Remember step judged something lasting was learned (ADR-022).
    """
    global INTENTION, GOAL_ACHIEVED, LAST_ACTIVITY

    history = _domain_turns(domain)  # captured before this turn's own entry is appended

    _append('user', text, domain=domain)
    AWAITING.discard(domain)

    # This is the actual "remember the user" mechanism (US-002's memory
    # layer, not a bespoke one) — Hippocampus extracts candidate durable
    # facts from what was just said, the deterministic write-gate decides
    # what's durable enough to keep, and Brain 1's Context Pack below already
    # reads them back as `domain_memories`. Without this call that grounding
    # was always empty, no matter what the person revealed. Best-effort —
    # `remember_from_text` never raises, so this can't block the turn.

    minutes = None
    streak = None
    support_message = ''
    intention_for_broca = None
    checkin_mode = False
    escalation_level = 0
    if domain == GOAL_DOMAIN:
        minutes = _extract_minutes(text)
        if minutes is not None and minutes > 0:
            ESCALATION[domain] = 0  # real progress reported — the escalation ladder resets
        else:
            # No number given, or explicitly 0 — this reads as "didn't/couldn't do it" (or
            # it's the very first message, which is exactly where the benefit-framing +
            # direct-question check-in belongs too).
            checkin_mode = True
            escalation_level = ESCALATION.get(domain, 0)
            ESCALATION[domain] = escalation_level + 1

        if minutes is not None and INTENTION is not None:
            result = orchestrator.log_checkin(PROFILE_EMAIL, INTENTION['intention_id'], minutes, note=text[:200])
            INTENTION = result['intention']
            streak = result['streak']
            if result['needs_support']:
                support = orchestrator.offer_support(PROFILE_EMAIL, INTENTION, streak, result['checkins'])
                support_message = support['message']
                if support_message:  # empty when it failed Brain 2's Check — never shown
                    _append('brain2_support', support_message, domain=domain)
                suggested = support.get('suggested_target_minutes')
                new_target = suggested if isinstance(suggested, int) and suggested > 0 else max(10, round(INTENTION['target_minutes'] * 0.5))
                INTENTION = orchestrator.adjust_intention(PROFILE_EMAIL, INTENTION['intention_id'], new_target)
                _append('system', f"Brain 1: target adjusted to {new_target} min/day for now — a stepping stone back to {ORIGINAL_TARGET_MINUTES}.", domain=domain)
            intention_for_broca = INTENTION

    turn = orchestrator.converse(
        PROFILE_EMAIL,
        domain,
        text,
        conversation=history,
        intention=intention_for_broca,
        streak=streak,
        support_message=support_message,
        checkin_mode=checkin_mode,
        escalation_level=escalation_level,
    )
    _append('brain2', turn['reply'], persona=turn['persona'], domain=domain)
    AWAITING.add(domain)
    _offer_proposal(turn['proposal'], domain)
    if turn['safety'] != safety.CRISIS:  # crisis turns are never remembered (FR-SAFE-008)
        memory_manager.remember_from_text(
            profile_email=PROFILE_EMAIL,
            source_text=text,
            source_type='conversation',
            source_id=f'{domain}-{len(THREAD)}',
            full_name=PROFILE_FACTS['full_name'],
        )

    if (
        domain == GOAL_DOMAIN
        and not GOAL_ACHIEVED
        and minutes is not None
        and INTENTION is not None
        and INTENTION['target_minutes'] >= ORIGINAL_TARGET_MINUTES
        and minutes >= INTENTION['target_minutes']
    ):
        GOAL_ACHIEVED = True
        _append('milestone', f'GOAL ACHIEVED — sustaining the original {ORIGINAL_TARGET_MINUTES} min/day gym target.', domain=domain)
        # The whole point of the growth loop: this doesn't just end the thread, it becomes
        # durable memory Brain 2 can draw on in any future conversation — "reached this before,
        # here's what worked" — not just an accepted Profile entry nobody else ever reads.
        memory_repo.create_memory(
            profile_email=PROFILE_EMAIL,
            memory_type='event',
            domain=domain,
            content=f'Successfully built a sustained {ORIGINAL_TARGET_MINUTES} min/day gym habit after working through early setbacks.',
            explicitness='explicit',
            confidence=1.0,
            sensitivity_tier='T2',
            status=memory_repo.ACTIVE,
            rationale_code='USER_EXPLICIT',
            source_type='milestone',
            source_id=f'{domain}-goal-achieved',
        )

    LAST_ACTIVITY = time.monotonic()


def handle_send(message: str) -> dict:
    with LOCK:
        domain = _classify_domain(message)
        _process_turn(message, domain)
    return {'ok': True, 'domain': domain}


def handle_accept(domain: str) -> dict:
    global LAST_ACTIVITY
    with LOCK:
        pending = CURRENT.get(domain)
        if pending is None:
            return {'ok': False, 'error': f"Nothing pending in '{domain}' to accept."}
        accepted = orchestrator.accept_proposal(pending['proposal_id'], PROFILE_EMAIL)
        _append('system', f"Accepted — Profile '{domain}' now at v{accepted['version']}.", version=accepted['version'], domain=domain)
        del CURRENT[domain]
        LAST_ACTIVITY = time.monotonic()
    return {'ok': True}


def handle_reject(domain: str) -> dict:
    global LAST_ACTIVITY
    with LOCK:
        pending = CURRENT.pop(domain, None)
        if pending is None:
            return {'ok': False, 'error': f"Nothing pending in '{domain}'."}
        orchestrator.reject_proposal(pending['proposal_id'], PROFILE_EMAIL)
        _append('system', f"Not saved — Profile '{domain}' unchanged.", domain=domain)
        LAST_ACTIVITY = time.monotonic()
    return {'ok': True}


def _offer_proposal(proposal: dict | None, domain: str) -> None:
    """A profile proposal is its own card, separate from the chat (ADR-022)."""
    if proposal is None:
        return
    CURRENT[domain] = {'proposal_id': proposal['profile_entry_id'], 'version': proposal['version'], 'content': proposal['content']}
    _append('proposal', proposal['content'], proposal_id=proposal['profile_entry_id'], version=proposal['version'], domain=domain)


_LAST_NUDGED_DOMAIN: str | None = None


def _process_auto_nudge() -> bool:
    """Brain 1 nudging Brain 2 on its own because User 1 hasn't responded —

    the ONLY thing that happens automatically. Unlike a real turn, this
    never fabricates a user message or a number (no `_extract_minutes`, no
    invented minutes) — there IS no new ground truth while the real person
    is away, so none is invented. It only asks Brain 2 to follow up — same
    `checkin_mode` + escalating `escalation_level` as a real "didn't/couldn't
    do it" reply (`_process_turn`), on one shared counter per domain.

    Nudges exactly ONE domain per call, round-robin across whichever domains
    have something pending — never all of them in one go. With several
    domains pending at once, nudging every single one in a loop here would
    mean a real user click has to wait behind that whole stack (each nudge
    is a real, multi-second LLM call) before the server is free to handle
    it — this bounds each watchdog cycle to one LLM call, so a real request
    is never stuck behind more than one in-flight turn. Skips the fitness
    domain once its goal is achieved — every other domain has no such finish
    line, so it stays in rotation as long as something of its is pending.
    """
    global _LAST_NUDGED_DOMAIN
    candidates = sorted(d for d in AWAITING if not (d == GOAL_DOMAIN and GOAL_ACHIEVED))
    if not candidates:
        return False
    start = (candidates.index(_LAST_NUDGED_DOMAIN) + 1) % len(candidates) if _LAST_NUDGED_DOMAIN in candidates else 0
    domain = candidates[start]
    _LAST_NUDGED_DOMAIN = domain
    # Brain 1 decides whether reaching out helps (Building_Brain1.md §14.3). This demo uses its own
    # idle timer instead of the hours-long wait and daily cap, and ignores quiet hours so it works at night.
    waiting = next((w for w in conversations_repo.domains_awaiting_reply(PROFILE_EMAIL) if w['domain'] == domain), None)
    if waiting is not None:
        decision = proactive.decide(PROFILE_EMAIL, waiting, respect_timing=False, respect_quiet_hours=False)
        if not decision['reach_out']:
            AWAITING.discard(domain)
            _append('system', f"Brain 1 ({domain}): not checking in — {decision['reason']}.", domain=domain)
            return True

    history = _domain_turns(domain)
    escalation_level = ESCALATION.get(domain, 0)
    _append('system', f"Brain 1 ({domain}): no reply for a while — Brain 2 checks in gently (attempt #{escalation_level + 1}).", domain=domain)
    turn = orchestrator.converse(
        PROFILE_EMAIL,
        domain,
        '',
        trigger='silence',
        intention=INTENTION if domain == GOAL_DOMAIN else None,
        conversation=history,
        escalation_level=escalation_level,
    )
    ESCALATION[domain] = escalation_level + 1
    _append('brain2', turn['reply'], persona=turn['persona'], domain=domain)
    return True


def _watchdog_loop(idle_seconds: int) -> None:
    global LAST_ACTIVITY
    while True:
        time.sleep(5)
        with LOCK:
            if not THREAD:
                continue
            if time.monotonic() - LAST_ACTIVITY < idle_seconds:
                continue
            if _process_auto_nudge():
                LAST_ACTIVITY = time.monotonic()  # wait a fresh full window before the next auto-turn


_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Brain 1 &lt;-&gt; Brain 2 (interactive)</title>
<style>
  :root { --bg:#0f1115; --panel:#171a21; --you:#394150; --auto:#5a4a2c; --b2:#1c7c54; --support:#8a5a1c;
    --text:#e8eaed; --muted:#8b92a1; --accent:#2fbf71; }
  * { box-sizing: border-box; }
  body { margin:0; font-family:-apple-system,Segoe UI,Roboto,sans-serif; background:var(--bg); color:var(--text); }
  header { position:sticky; top:0; background:var(--panel); border-bottom:1px solid #262a33; padding:12px 20px; z-index:5; }
  h1 { margin:0 0 6px; font-size:16px; font-weight:600; }
  p.sub { margin:0 0 8px; font-size:12px; color:var(--muted); }
  .stats { display:flex; flex-wrap:wrap; gap:8px; font-size:12px; color:var(--muted); }
  .stats b { color:var(--text); }
  .stat { background:var(--bg); border:1px solid #262a33; border-radius:8px; padding:4px 10px; }
  #achieved { display:none; background:linear-gradient(90deg,#1c7c54,#2fbf71); color:#0b1a12; font-weight:700;
    padding:8px 20px; text-align:center; font-size:13px; }
  main { max-width:720px; margin:0 auto; padding:20px 20px 150px; }
  .row { display:flex; align-items:flex-end; gap:8px; margin:10px 0; }
  .row.you { justify-content:flex-end; } .row.brain2 { justify-content:flex-start; }
  .avatar { width:52px; height:52px; min-width:52px; border-radius:50%; display:flex; align-items:center;
    justify-content:center; font-size:30px; flex-shrink:0; background:var(--panel); border:2px solid #262a33; }
  .avatar.user1 { background:#394150; border-color:#5b6677; }
  .avatar.brain1 { background:#5a4a2c; border:2px dashed #8a7a4c; }
  .avatar.brain2 { background:#0f4a30; border-color:#2fbf71; }
  .bubble { max-width:72%; padding:10px 14px; border-radius:14px; font-size:14px; line-height:1.45; white-space:pre-wrap; }
  .you .bubble { background:var(--you); border-bottom-right-radius:4px; }
  .you.auto .bubble { background:var(--auto); border:1px dashed #8a7a4c; }
  .brain2 .bubble { background:var(--b2); border-bottom-left-radius:4px; }
  .brain2.support .bubble { background:var(--support); }
  .who { display:block; font-size:11px; opacity:.8; margin-bottom:3px; font-weight:600; }
  .system { text-align:center; color:var(--accent); font-size:12px; margin:14px 0; font-weight:600; }
  .milestone { text-align:center; margin:16px 0; padding:10px; border-radius:10px; background:#d1a62c; color:#221c07;
    font-weight:700; font-size:13px; }
  .proposal { margin:12px 0 4px 60px; padding:10px 14px; border-radius:12px; border:1px dashed var(--accent);
    background:var(--panel); font-size:13px; line-height:1.45; white-space:pre-wrap; max-width:72%; }
  .controls { margin:8px 0 18px 60px; display:flex; gap:8px; flex-wrap:wrap; align-items:flex-start; }
  .controls textarea { flex:1; min-width:220px; background:var(--panel); border:1px solid #262a33; border-radius:8px;
    color:var(--text); padding:8px 10px; font-size:13px; resize:vertical; min-height:36px; }
  button { background:var(--accent); color:#0b1a12; border:none; border-radius:8px; padding:8px 14px; font-weight:700;
    font-size:13px; cursor:pointer; white-space:nowrap; }
  button.secondary { background:#2c333f; color:var(--text); }
  button:disabled { opacity:.5; cursor:default; }
  #composer { position:fixed; bottom:0; left:0; right:0; background:var(--panel); border-top:1px solid #262a33;
    padding:10px 20px; display:flex; flex-direction:column; gap:6px; align-items:center; }
  #idle-note { font-size:11px; color:var(--muted); max-width:720px; width:100%; }
  #composer .inner { max-width:720px; width:100%; display:flex; gap:10px; }
  #composer textarea { flex:1; background:var(--bg); border:1px solid #262a33; border-radius:10px; color:var(--text);
    padding:10px 12px; font-size:14px; resize:none; min-height:44px; }
  #thinking { color:var(--muted); font-size:13px; font-style:italic; margin:10px 0; display:none; }
  #empty { color:var(--muted); text-align:center; margin-top:60px; font-size:14px; }
</style>
</head>
<body>
<div id="achieved">GOAL ACHIEVED — sustaining the original target</div>
<header>
  <h1>Brain 1 &lt;-&gt; Brain 2 — interactive</h1>
  <p class="sub">Type about anything — each message is classified into its own domain (fitness, cooking, work, ...) and gets its own thread. If you go quiet, Brain 1 follows up on whatever's still pending, on its own, until you're back.</p>
  <div class="stats">
    <div class="stat">Fitness target <b id="s-target">-</b> min/day</div>
    <div class="stat">Fitness goal <b id="s-goal">in progress</b></div>
    <div class="stat">👤 You (User 1)</div>
    <div class="stat">🤖 Brain 2 (the LLM)</div>
  </div>
</header>
<main id="feed"><div id="empty">Tell Brain 2 what's going on — any topic, e.g. "I'm struggling to do gym for one hour a day" or "I want to get better at cooking."</div></main>
<div id="thinking">Brain 1 &rarr; Brain 2 is thinking&hellip;</div>
<div id="composer">
  <div id="idle-note"></div>
  <div class="inner">
    <textarea id="input" placeholder="Type a message to Brain 2 — any topic…" rows="1"></textarea>
    <button id="send">Send</button>
  </div>
</div>
<script>
let idleDeadline = null;
let REQUEST_IN_FLIGHT = false;  // true for the whole duration of any POST — a turn can take several seconds

async function post(path, body) {
  REQUEST_IN_FLIGHT = true;
  try {
    const res = await fetch(path, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body || {}) });
    return await res.json();
  } finally {
    REQUEST_IN_FLIGHT = false;
  }
}
function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function setBusy(busy) {
  document.getElementById('thinking').style.display = busy ? 'block' : 'none';
  document.getElementById('send').disabled = busy;
}

async function refresh() {
  const res = await fetch('/api/thread');
  const data = await res.json();
  render(data);
}

function render(data) {
  const { thread, pending, awaiting, fitness_target_minutes, goal_achieved, idle_seconds_remaining } = data;
  const pendingDomains = awaiting || [];
  document.getElementById('s-target').textContent = fitness_target_minutes ?? '-';
  document.getElementById('s-goal').textContent = goal_achieved ? 'achieved' : 'in progress';
  document.getElementById('achieved').style.display = goal_achieved ? 'block' : 'none';
  if (idle_seconds_remaining != null && pendingDomains.length) {
    document.getElementById('idle-note').textContent =
      `If you don't reply, Brain 2 will check in on ${pendingDomains.length > 1 ? 'open topics' : `'${pendingDomains[0]}'`} in ~${idle_seconds_remaining}s.`;
  } else {
    document.getElementById('idle-note').textContent = '';
  }

  // The feed is fully rebuilt below, which would wipe out anything being
  // typed into the dynamically-created reply box on every 2s poll, AND
  // would replace a just-disabled Accept/Reply control with a fresh
  // (re-enabled) one while that same click's request is still in flight —
  // letting a second click queue up behind the first instead of being
  // blocked. Skip the rebuild for either case; the stats/idle-note above
  // still update live regardless.
  const active = document.activeElement;
  if (REQUEST_IN_FLIGHT) {
    return;
  }

  const feed = document.getElementById('feed');
  feed.innerHTML = '';
  if (!thread.length) {
    feed.innerHTML = '<div id="empty">Tell Brain 2 what\\'s going on — any topic, e.g. "I\\'m struggling to do gym for one hour a day" or "I want to get better at cooking."</div>';
    return;
  }

  thread.forEach((ev) => {
    const domainPending = pending && pending[ev.domain];
    const isLatestPending = ev.kind === 'proposal' && domainPending && ev.proposal_id === domainPending.proposal_id;
    if (ev.kind === 'user') {
      const row = document.createElement('div');
      row.className = 'row you';
      const who = 'You' + (ev.domain ? ` · ${ev.domain}` : '');
      row.innerHTML = `<div class="bubble"><span class="who">${esc(who)}</span>${esc(ev.text)}</div><div class="avatar user1">👤</div>`;
      feed.appendChild(row);
    } else if (ev.kind === 'brain2_support') {
      const row = document.createElement('div');
      row.className = 'row brain2 support';
      row.innerHTML = `<div class="avatar brain2">🤖</div><div class="bubble"><span class="who">Brain 2 · Amygdala (${esc(ev.domain)} — notices &amp; offers support)</span>${esc(ev.text)}</div>`;
      feed.appendChild(row);
    } else if (ev.kind === 'brain2') {
      const row = document.createElement('div');
      row.className = 'row brain2';
      const voice = ev.persona ? ` · ${esc(ev.persona.voice.replace('_', ' '))}${ev.persona.source === 'her_choice' ? ' (your choice)' : ''}` : '';
      row.innerHTML = `<div class="avatar brain2">🤖</div><div class="bubble"><span class="who">Brain 2${voice}</span>${esc(ev.text)}</div>`;
      feed.appendChild(row);
    } else if (ev.kind === 'proposal') {
      const card = document.createElement('div');
      card.className = 'proposal';
      card.innerHTML = `<span class="who">I've learned something about you · ${esc(ev.domain)} profile v${ev.version} — does this sound right?</span>${esc(ev.text)}`;
      feed.appendChild(card);
      if (isLatestPending) {
        const ctrl = document.createElement('div');
        ctrl.className = 'controls';
        ctrl.innerHTML = `<button class="accept-btn">Yes, save it</button><button class="secondary reject-btn">Not quite</button>`;
        feed.appendChild(ctrl);
        const acceptBtn = ctrl.querySelector('.accept-btn');
        const rejectBtn = ctrl.querySelector('.reject-btn');
        const setCtrlBusy = (busy) => { acceptBtn.disabled = busy; rejectBtn.disabled = busy; };
        acceptBtn.onclick = async () => {
          setCtrlBusy(true); setBusy(true);
          await post('/api/accept', { domain: ev.domain });
          setBusy(false); refresh();
        };
        rejectBtn.onclick = async () => {
          setCtrlBusy(true); setBusy(true);
          await post('/api/reject', { domain: ev.domain });
          setBusy(false); refresh();
        };
      }
    } else if (ev.kind === 'milestone') {
      const row = document.createElement('div'); row.className = 'milestone'; row.textContent = ev.text; feed.appendChild(row);
    } else {
      const row = document.createElement('div'); row.className = 'system'; row.textContent = ev.text; feed.appendChild(row);
    }
  });
  window.scrollTo(0, document.body.scrollHeight);
}

document.getElementById('send').onclick = async () => {
  const input = document.getElementById('input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  setBusy(true);
  await post('/api/send', { message: text });
  setBusy(false);
  refresh();
};
document.getElementById('input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); document.getElementById('send').click(); }
});

refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.startswith('/api/thread'):
            # Deliberately NOT holding LOCK here. A turn can take many
            # seconds (several sequential LLM calls) — if reading the thread
            # had to wait behind that same lock, the whole page would freeze
            # (can't even see current state) for the entire duration of any
            # in-flight write, which is exactly the bug this fixes. A read
            # racing a THREAD.append/dict-write is a momentarily-stale
            # snapshot at worst, never corruption — list/dict ops are atomic
            # under the GIL — and the next 2s poll catches up regardless.
            remaining = max(0, round(IDLE_SECONDS - (time.monotonic() - LAST_ACTIVITY))) if (THREAD and AWAITING) else None
            self._send_json(
                {
                    'thread': THREAD,
                    'pending': CURRENT,
                    'awaiting': sorted(AWAITING),
                    'fitness_target_minutes': INTENTION['target_minutes'] if INTENTION else None,
                    'goal_achieved': GOAL_ACHIEVED,
                    'idle_seconds_remaining': remaining,
                }
            )
            return
        body = _INDEX_HTML.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length) if length else b'{}'
        try:
            payload = json.loads(raw or b'{}')
        except json.JSONDecodeError:
            payload = {}

        try:
            if self.path.startswith('/api/send'):
                result = handle_send((payload.get('message') or '').strip())
            elif self.path.startswith('/api/accept'):
                result = handle_accept((payload.get('domain') or '').strip())
            elif self.path.startswith('/api/reject'):
                result = handle_reject((payload.get('domain') or '').strip())
            else:
                self._send_json({'ok': False, 'error': 'unknown endpoint'}, status=404)
                return
        except Exception as exc:  # noqa: BLE001 - surface the error to the page instead of a bare 500
            self._send_json({'ok': False, 'error': str(exc)}, status=500)
            return

        self._send_json(result)


def main() -> None:
    global IDLE_SECONDS, LAST_ACTIVITY
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--idle-seconds', type=int, default=45, help='How long User 1 can go quiet before Brain 1 continues on its own.')
    args = parser.parse_args()
    IDLE_SECONDS = args.idle_seconds

    _ensure_profile_and_intention()
    LAST_ACTIVITY = time.monotonic()

    watchdog = threading.Thread(target=_watchdog_loop, args=(IDLE_SECONDS,), daemon=True)
    watchdog.start()

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Serving interactive Brain1<->Brain2 UI at http://127.0.0.1:{args.port}  (profile: {PROFILE_EMAIL}, idle window: {IDLE_SECONDS}s)')
    server.serve_forever()


if __name__ == '__main__':
    main()
