"""Serves an interactive, continuous Brain 1 <-> Brain 2 <-> User 1 loop,

driven toward one deterministic goal: the user's fitness intention reaching
and sustaining its original target (60 min/day gym).

The shape, per the user's own description across several rounds of
refinement:
  1. User 1 types ONE message. Brain 1 relays it to Brain 2.
  2. Brain 2 (Amygdala, if a real shortfall pattern just fired; always
     Broca) composes a response — a Profile draft. Brain 1 hands it back to
     User 1.
  3. User 1 can Accept it (the only durable write, per ADR-014) or reply
     with feedback, which Brain 1 relays back to Brain 2 to re-analyse
     (`orchestrator.refine_proposal`) — a new draft comes back, and the loop
     continues. Fully iterative.
  4. If User 1 goes quiet past a stipulated idle window, Brain 1 nudges
     Brain 2 on its own — never pretending to be User 1 or inventing a
     number that was never reported, only asking Brain 2 to follow up
     without repeating its last (still-unanswered) message — until User 1
     responds again. This auto-nudge never accepts a proposal on the real
     user's behalf; only a real browser action does that.
  5. This keeps going — interactively when a human is present, autonomously
     when they're not — until the goal (60 min/day, sustained) is reached.
     Ground truth (today's actual minutes) is always a number that was
     actually stated in a message (parsed deterministically, never invented
     by a model) — same ADR-007 split used everywhere else in this codebase.

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

from app import brain1  # noqa: E402
from app.brain2 import intentions_repo, orchestrator  # noqa: E402

PROFILE_EMAIL = 'user1.interactive@example.com'
DOMAIN = 'fitness'
ORIGINAL_TARGET_MINUTES = 60
PROFILE_FACTS = {
    'full_name': 'User One',
    'dob': '1991-04-12',
    'location': 'Austin, TX',
    'interests': ['healthy_living', 'mindfulness'],
    'other_interests': 'cycling on weekends',
    'quote': 'Small steps still move you forward.',
}

_MINUTES_RE = re.compile(r'(\d+)\s*(?:min\b|mins\b|minutes\b)', re.IGNORECASE)

LOCK = threading.Lock()
THREAD: list[dict] = []
CURRENT: dict | None = None  # {'proposal_id', 'version'} of the latest un-accepted draft, or None
INTENTION: dict | None = None
LAST_ACTIVITY = time.monotonic()
GOAL_ACHIEVED = False
IDLE_SECONDS = 45  # set from CLI in main()


def _ensure_profile_and_intention() -> None:
    global INTENTION
    if brain1.get(PROFILE_EMAIL) is None:
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
    active = intentions_repo.get_active_intention(PROFILE_EMAIL, DOMAIN)
    INTENTION = active or orchestrator.set_intention(PROFILE_EMAIL, DOMAIN, title='Gym', target_minutes=ORIGINAL_TARGET_MINUTES)


def _append(kind: str, text: str, **extra) -> dict:
    entry = {'kind': kind, 'text': text, 'at': datetime.now(timezone.utc).isoformat(), **extra}
    THREAD.append(entry)
    return entry


def _extract_minutes(text: str) -> int | None:
    m = _MINUTES_RE.search(text or '')
    return int(m.group(1)) if m else None


def _process_turn(text: str) -> None:
    """A real message from User 1 — the only caller of this now; the idle

    watchdog uses `_process_auto_nudge` instead, which never fabricates user
    input. Logs ground truth if a number was actually stated, runs the real
    support/propose pipeline, and always ends with exactly one new pending
    Brain 2 draft for the user to react to.
    """
    global CURRENT, INTENTION, GOAL_ACHIEVED, LAST_ACTIVITY

    # A reply to an already-pending draft reads as feedback; a message with
    # nothing pending reads as a fresh reflection — same distinction the
    # explicit /api/send vs /api/reply endpoints make.
    user_kind = 'user_feedback' if CURRENT is not None else 'user'
    _append(user_kind, text)

    minutes = _extract_minutes(text)
    streak = None
    support_message = ''
    if minutes is not None and INTENTION is not None:
        result = orchestrator.log_checkin(PROFILE_EMAIL, INTENTION['intention_id'], minutes, note=text[:200])
        INTENTION = result['intention']
        streak = result['streak']
        if result['needs_support']:
            support = orchestrator.offer_support(PROFILE_EMAIL, INTENTION, streak, result['checkins'])
            support_message = support['message']
            _append('brain2_support', support_message)
            suggested = support.get('suggested_target_minutes')
            new_target = suggested if isinstance(suggested, int) and suggested > 0 else max(10, round(INTENTION['target_minutes'] * 0.5))
            INTENTION = orchestrator.adjust_intention(PROFILE_EMAIL, INTENTION['intention_id'], new_target)
            _append('system', f"Brain 1: target adjusted to {new_target} min/day for now — a stepping stone back to {ORIGINAL_TARGET_MINUTES}.")

    proposal = orchestrator.propose_refinement(
        profile_email=PROFILE_EMAIL,
        domain=DOMAIN,
        user_reflection=text,
        intention=INTENTION if minutes is not None else None,
        streak=streak,
        support_message=support_message,
    )
    CURRENT = {'proposal_id': proposal['profile_entry_id'], 'version': proposal['version'], 'content': proposal['content']}
    _append('brain2', proposal['content'], proposal_id=proposal['profile_entry_id'], version=proposal['version'])

    if (
        not GOAL_ACHIEVED
        and minutes is not None
        and INTENTION is not None
        and INTENTION['target_minutes'] >= ORIGINAL_TARGET_MINUTES
        and minutes >= INTENTION['target_minutes']
    ):
        GOAL_ACHIEVED = True
        _append('milestone', f'GOAL ACHIEVED — sustaining the original {ORIGINAL_TARGET_MINUTES} min/day gym target.')

    LAST_ACTIVITY = time.monotonic()


def handle_send(message: str) -> dict:
    with LOCK:
        _process_turn(message)
    return {'ok': True}


def handle_accept() -> dict:
    global CURRENT, LAST_ACTIVITY
    with LOCK:
        if CURRENT is None:
            return {'ok': False, 'error': 'Nothing pending to accept.'}
        accepted = orchestrator.accept_proposal(CURRENT['proposal_id'], PROFILE_EMAIL)
        _append('system', f"Accepted — Profile '{DOMAIN}' now at v{accepted['version']}.", version=accepted['version'])
        CURRENT = None
        LAST_ACTIVITY = time.monotonic()
    return {'ok': True}


def handle_reply(feedback: str) -> dict:
    with LOCK:
        if CURRENT is None:
            return {'ok': False, 'error': 'Nothing pending to reply to — send a new message instead.'}
        _process_turn(feedback)
    return {'ok': True}


def _process_auto_nudge() -> None:
    """Brain 1 nudging Brain 2 on its own because User 1 hasn't responded —

    the ONLY thing that happens automatically. Unlike a real turn, this never
    fabricates a user message or a number (no `_extract_minutes`, no invented
    minutes) — there IS no new ground truth while the real person is away, so
    none is invented. It only asks Brain 2 to follow up: redraft without
    repeating its last (still-pending) message if one exists, or send a
    fresh, honest check-in if nothing is pending yet.
    """
    global CURRENT

    previous_current = CURRENT
    note = (
        "Brain 1 → Brain 2: no response from User 1 yet — following up, not repeating the last message."
        if previous_current is not None
        else 'Brain 1 → Brain 2: checking in — no update from User 1 yet.'
    )
    _append('system', note)

    proposal = orchestrator.propose_refinement(
        profile_email=PROFILE_EMAIL,
        domain=DOMAIN,
        user_reflection='(No new input from the user yet. Brain 1 is checking in on their behalf.)',
        intention=INTENTION,
        pending_draft_content=previous_current.get('content') if previous_current is not None else None,
    )
    CURRENT = {'proposal_id': proposal['profile_entry_id'], 'version': proposal['version'], 'content': proposal['content']}
    _append('brain2', proposal['content'], proposal_id=proposal['profile_entry_id'], version=proposal['version'])


def _watchdog_loop(idle_seconds: int) -> None:
    global LAST_ACTIVITY
    while True:
        time.sleep(5)
        with LOCK:
            if not THREAD or GOAL_ACHIEVED:
                continue
            if time.monotonic() - LAST_ACTIVITY < idle_seconds:
                continue
            _process_auto_nudge()
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
  .avatar { width:30px; height:30px; min-width:30px; border-radius:50%; display:flex; align-items:center;
    justify-content:center; font-size:16px; flex-shrink:0; background:var(--panel); border:1px solid #262a33; }
  .avatar.user1 { background:#394150; }
  .avatar.brain1 { background:#5a4a2c; border:1px dashed #8a7a4c; }
  .avatar.brain2 { background:#0f4a30; border-color:#1c7c54; }
  .bubble { max-width:72%; padding:10px 14px; border-radius:14px; font-size:14px; line-height:1.45; white-space:pre-wrap; }
  .you .bubble { background:var(--you); border-bottom-right-radius:4px; }
  .you.auto .bubble { background:var(--auto); border:1px dashed #8a7a4c; }
  .brain2 .bubble { background:var(--b2); border-bottom-left-radius:4px; }
  .brain2.support .bubble { background:var(--support); }
  .who { display:block; font-size:11px; opacity:.8; margin-bottom:3px; font-weight:600; }
  .system { text-align:center; color:var(--accent); font-size:12px; margin:14px 0; font-weight:600; }
  .milestone { text-align:center; margin:16px 0; padding:10px; border-radius:10px; background:#d1a62c; color:#221c07;
    font-weight:700; font-size:13px; }
  .controls { margin:8px 0 18px 38px; display:flex; gap:8px; flex-wrap:wrap; align-items:flex-start; }
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
  <p class="sub">Type a message. If you go quiet, Brain 1 keeps talking to Brain 2 on its own until you're back — it never accepts anything for you.</p>
  <div class="stats">
    <div class="stat">Target <b id="s-target">-</b> min/day</div>
    <div class="stat">Goal <b id="s-goal">in progress</b></div>
    <div class="stat">👤 You (User 1)</div>
    <div class="stat">🧠 Brain 1 (relay / stands in when you're away)</div>
    <div class="stat">🤖 Brain 2 (the LLM)</div>
  </div>
</header>
<main id="feed"><div id="empty">Tell Brain 2 what's going on — e.g. "I'm struggling to do gym for one hour a day."</div></main>
<div id="thinking">Brain 1 &rarr; Brain 2 is thinking&hellip;</div>
<div id="composer">
  <div id="idle-note"></div>
  <div class="inner">
    <textarea id="input" placeholder="Type a message to Brain 2…" rows="1"></textarea>
    <button id="send">Send</button>
  </div>
</div>
<script>
let idleDeadline = null;

async function post(path, body) {
  const res = await fetch(path, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body || {}) });
  return res.json();
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
  const { thread, pending, target_minutes, goal_achieved, idle_seconds_remaining } = data;
  document.getElementById('s-target').textContent = target_minutes ?? '-';
  document.getElementById('s-goal').textContent = goal_achieved ? 'achieved' : 'in progress';
  document.getElementById('achieved').style.display = goal_achieved ? 'block' : 'none';
  if (idle_seconds_remaining != null && pending) {
    document.getElementById('idle-note').textContent =
      `If you don't reply, Brain 1 will continue the conversation with Brain 2 on its own in ~${idle_seconds_remaining}s.`;
  } else {
    document.getElementById('idle-note').textContent = '';
  }

  // The feed is fully rebuilt below, which would wipe out anything being
  // typed into the dynamically-created reply box on every 2s poll. Skip the
  // rebuild entirely while that box has focus — the stats/idle-note above
  // still update live either way.
  const active = document.activeElement;
  if (active && active.classList && active.classList.contains('reply-box')) {
    return;
  }

  const feed = document.getElementById('feed');
  feed.innerHTML = '';
  if (!thread.length) {
    feed.innerHTML = '<div id="empty">Tell Brain 2 what\\'s going on — e.g. "I\\'m struggling to do gym for one hour a day."</div>';
    return;
  }

  thread.forEach((ev, i) => {
    const isLatestPending = pending && ev.kind === 'brain2' && ev.proposal_id === pending.proposal_id && i === thread.length - 1;
    if (ev.kind === 'user' || ev.kind === 'user_feedback' || ev.kind === 'brain1_auto' || ev.kind === 'brain1_auto_feedback') {
      const auto = ev.kind.startsWith('brain1_auto');
      const row = document.createElement('div');
      row.className = 'row you' + (auto ? ' auto' : '');
      const who = auto ? 'Brain 1 (auto — standing in while you\\'re away)' : (ev.kind === 'user_feedback' ? 'You · feedback' : 'You');
      const avatar = auto ? '<div class="avatar brain1">🧠</div>' : '<div class="avatar user1">👤</div>';
      row.innerHTML = `<div class="bubble"><span class="who">${who}</span>${esc(ev.text)}</div>${avatar}`;
      feed.appendChild(row);
    } else if (ev.kind === 'brain2_support') {
      const row = document.createElement('div');
      row.className = 'row brain2 support';
      row.innerHTML = `<div class="avatar brain2">🤖</div><div class="bubble"><span class="who">Brain 2 · Amygdala (notices &amp; offers support)</span>${esc(ev.text)}</div>`;
      feed.appendChild(row);
    } else if (ev.kind === 'brain2') {
      const row = document.createElement('div');
      row.className = 'row brain2';
      row.innerHTML = `<div class="avatar brain2">🤖</div><div class="bubble"><span class="who">Brain 2 · Profile '${esc('fitness')}' draft v${ev.version}</span>${esc(ev.text)}</div>`;
      feed.appendChild(row);
      if (isLatestPending) {
        const ctrl = document.createElement('div');
        ctrl.className = 'controls';
        ctrl.innerHTML = `
          <button class="accept-btn">Accept</button>
          <textarea class="reply-box" placeholder="Not quite — reply with feedback (mention actual minutes, e.g. '20 min') and Brain 2 will re-analyse…" rows="1"></textarea>
          <button class="secondary reply-btn">Reply</button>`;
        feed.appendChild(ctrl);
        ctrl.querySelector('.accept-btn').onclick = async () => { setBusy(true); await post('/api/accept', {}); setBusy(false); refresh(); };
        ctrl.querySelector('.reply-btn').onclick = async () => {
          const box = ctrl.querySelector('.reply-box');
          if (!box.value.trim()) return;
          setBusy(true);
          await post('/api/reply', { feedback: box.value.trim() });
          box.value = '';
          setBusy(false);
          refresh();
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
            with LOCK:
                remaining = max(0, round(IDLE_SECONDS - (time.monotonic() - LAST_ACTIVITY))) if (THREAD and not GOAL_ACHIEVED) else None
                self._send_json(
                    {
                        'thread': THREAD,
                        'pending': CURRENT,
                        'target_minutes': INTENTION['target_minutes'] if INTENTION else None,
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
                result = handle_accept()
            elif self.path.startswith('/api/reply'):
                result = handle_reply((payload.get('feedback') or '').strip())
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
