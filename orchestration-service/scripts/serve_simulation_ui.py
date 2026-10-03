"""Serves a tiny local UI that watches a `simulate_brain1_brain2_hour.py` run

live — a chat-style view of Brain 1 and Brain 2 talking, plus a stats strip
(day, target, phase, streak, proposals accepted, goal-achieved banner).

Deliberately its own standalone process, not a new endpoint on
orchestration-service or agentic-service: this is a dev/demo viewer only, and
adding it there would mean restarting a service real traffic might be
hitting. It only ever reads the simulation's plain-text log file — it never
touches the SQL database or the running simulation process.

Usage (from orchestration-service/, with its venv active — stdlib only, no
extra dependencies):

    python3 scripts/serve_simulation_ui.py [--port 8765] [--log-file PATH]

With no --log-file, it auto-picks the most recently modified
Docs/DEMO/brain1_brain2_hour_*.log file and keeps re-reading it on every
poll, so it automatically follows whichever simulation ran most recently.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.paths import REPO_ROOT  # noqa: E402

DEMO_DIR = REPO_ROOT / 'Docs' / 'DEMO'

_HEARTBEAT_RE = re.compile(
    r'\[t=\s*([\d.]+)s\] heartbeat — day (\d+)/(\d+), target=(\d+)min, '
    r'phase=(\w+), consecutive_meets=(\d+), proposals_accepted=(\d+)'
)
_BRAIN1_RE = re.compile(r'^BRAIN 1 \(User 1\): (.*)$')
_BRAIN2_RE = re.compile(r"^BRAIN 2 \((.*?)\): (.*)$")
_MILESTONE_RE = re.compile(r'^\*\*\* (.*) \*\*\*$')
_BANNER_RE = re.compile(r'^=== (.*) ===$')
_INTENTION_RE = re.compile(r"intention '(.*)', target (\d+) min/day")


def _latest_log_file() -> Path | None:
    candidates = sorted(DEMO_DIR.glob('brain1_brain2_hour_*.log'), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _parse_log(path: Path) -> dict:
    events: list[dict] = []
    summary = {
        'day': 0,
        'total_days': 0,
        'target_minutes': None,
        'phase': 'starting',
        'consecutive_meets': 0,
        'proposals_accepted': 0,
        'goal_achieved': False,
        'finished': False,
        'title': None,
    }

    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return {'events': [], 'summary': summary, 'log_file': str(path)}

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        m = _BANNER_RE.match(stripped)
        if m:
            events.append({'type': 'banner', 'text': m.group(1)})
            im = _INTENTION_RE.search(stripped)
            if im:
                summary['title'] = im.group(1)
                summary['target_minutes'] = int(im.group(2))
            if 'simulation starting' in stripped:
                tm = re.search(r'starting — (\d+) simulated', stripped)
                if tm:
                    summary['total_days'] = int(tm.group(1))
            if 'Simulation complete' in stripped:
                summary['finished'] = True
            continue

        m = _HEARTBEAT_RE.search(stripped)
        if m:
            _, day, total_days, target, phase, meets, proposals = m.groups()
            events.append({'type': 'heartbeat', 'day': int(day), 'phase': phase})
            summary.update(
                day=int(day),
                total_days=int(total_days),
                target_minutes=int(target),
                phase=phase,
                consecutive_meets=int(meets),
                proposals_accepted=int(proposals),
            )
            continue

        m = _MILESTONE_RE.match(stripped)
        if m:
            events.append({'type': 'milestone', 'text': m.group(1)})
            if 'GOAL ACHIEVED' in stripped:
                summary['goal_achieved'] = True
            continue

        m = _BRAIN1_RE.match(stripped)
        if m:
            events.append({'type': 'brain1', 'text': m.group(1)})
            continue

        m = _BRAIN2_RE.match(stripped)
        if m:
            label, text = m.groups()
            events.append({'type': 'brain2', 'label': label, 'text': text})
            tgt = re.search(r'target (\d+) min/day', stripped) or re.search(r'to (\d+) min/day', stripped)
            if tgt:
                summary['target_minutes'] = int(tgt.group(1))
            continue

        events.append({'type': 'other', 'text': stripped})

    return {'events': events, 'summary': summary, 'log_file': str(path)}


_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Brain 1 &lt;-&gt; Brain 2</title>
<style>
  :root {
    --bg: #0f1115; --panel: #171a21; --b1: #2c5fd1; --b2: #1c7c54;
    --text: #e8eaed; --muted: #8b92a1; --ok: #2fbf71; --warn: #d1a62c; --banner: #2a2e38;
  }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, Segoe UI, Roboto, sans-serif; background: var(--bg); color: var(--text); }
  header { position: sticky; top: 0; background: var(--panel); border-bottom: 1px solid #262a33; padding: 12px 20px; z-index: 5; }
  h1 { margin: 0 0 8px; font-size: 16px; font-weight: 600; }
  .stats { display: flex; flex-wrap: wrap; gap: 10px; }
  .stat { background: var(--bg); border: 1px solid #262a33; border-radius: 10px; padding: 6px 12px; font-size: 13px; }
  .stat b { color: var(--text); } .stat span.label { color: var(--muted); margin-right: 6px; }
  .progress { height: 6px; background: #262a33; border-radius: 4px; margin-top: 10px; overflow: hidden; }
  .progress-fill { height: 100%; background: var(--ok); width: 0%; transition: width .4s; }
  #achieved { display: none; background: linear-gradient(90deg, #1c7c54, #2fbf71); color: #0b1a12; font-weight: 700;
    padding: 10px 20px; text-align: center; }
  main { max-width: 760px; margin: 0 auto; padding: 20px; padding-bottom: 60px; }
  .bubble-row { display: flex; align-items: flex-end; gap: 8px; margin: 10px 0; }
  .bubble-row.b1 { justify-content: flex-start; }
  .bubble-row.b2 { justify-content: flex-end; }
  .avatar { width: 52px; height: 52px; min-width: 52px; border-radius: 50%; display: flex; align-items: center;
    justify-content: center; font-size: 30px; flex-shrink: 0; background: var(--panel); border: 2px solid #262a33; }
  .avatar.brain1 { background: #2a3a5a; border-color: var(--b1); }
  .avatar.brain2 { background: #0f4a30; border-color: var(--b2); }
  .bubble { max-width: 72%; padding: 10px 14px; border-radius: 14px; font-size: 14px; line-height: 1.4; }
  .bubble .who { display: block; font-size: 11px; opacity: .75; margin-bottom: 3px; font-weight: 600; letter-spacing: .02em; }
  .b1 .bubble { background: var(--b1); border-bottom-left-radius: 4px; }
  .b2 .bubble { background: var(--b2); border-bottom-right-radius: 4px; }
  .system { text-align: center; color: var(--muted); font-size: 12px; margin: 14px 0; }
  .banner { text-align: center; color: var(--muted); font-size: 12px; margin: 18px 0; padding: 6px; background: var(--banner); border-radius: 8px; }
  .milestone { text-align: center; margin: 16px 0; padding: 10px; border-radius: 10px; background: var(--warn); color: #221c07; font-weight: 700; font-size: 13px; }
  #empty { color: var(--muted); text-align: center; margin-top: 60px; font-size: 14px; }
  #live-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--ok); margin-right: 6px;
    animation: pulse 1.4s infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .3; } }
</style>
</head>
<body>
<div id="achieved">GOAL ACHIEVED</div>
<header>
  <h1><span id="live-dot"></span><span id="title">Brain 1 &lt;-&gt; Brain 2</span></h1>
  <div class="stats" style="margin-bottom:8px;">
    <div class="stat">🧠 Brain 1 (standing in for User 1)</div>
    <div class="stat">🤖 Brain 2 (the LLM)</div>
  </div>
  <div class="stats">
    <div class="stat"><span class="label">Day</span><b id="s-day">-</b></div>
    <div class="stat"><span class="label">Target</span><b id="s-target">-</b> min/day</div>
    <div class="stat"><span class="label">Phase</span><b id="s-phase">-</b></div>
    <div class="stat"><span class="label">Meets streak</span><b id="s-meets">-</b></div>
    <div class="stat"><span class="label">Profile updates</span><b id="s-proposals">-</b></div>
  </div>
  <div class="progress"><div class="progress-fill" id="progress-fill"></div></div>
</header>
<main id="feed"><div id="empty">Waiting for the simulation to start…</div></main>
<script>
let lastLen = 0;
async function poll() {
  try {
    const res = await fetch('/api/state');
    const data = await res.json();
    render(data);
  } catch (e) { /* server not ready yet */ }
  setTimeout(poll, 2000);
}

function render(data) {
  const feed = document.getElementById('feed');
  const s = data.summary;
  if (s.title) document.getElementById('title').textContent = s.title + ' — Fitness Journey';
  document.getElementById('s-day').textContent = s.total_days ? `${s.day}/${s.total_days}` : s.day;
  document.getElementById('s-target').textContent = s.target_minutes ?? '-';
  document.getElementById('s-phase').textContent = s.phase;
  document.getElementById('s-meets').textContent = s.consecutive_meets;
  document.getElementById('s-proposals').textContent = s.proposals_accepted;
  document.getElementById('progress-fill').style.width = s.total_days ? `${Math.min(100, 100 * s.day / s.total_days)}%` : '0%';
  document.getElementById('live-dot').style.display = s.finished ? 'none' : 'inline-block';
  document.getElementById('achieved').style.display = s.goal_achieved ? 'block' : 'none';

  if (data.events.length === lastLen) return;
  lastLen = data.events.length;
  document.getElementById('empty').style.display = 'none';
  feed.innerHTML = '';

  for (const ev of data.events) {
    const row = document.createElement('div');
    if (ev.type === 'brain1' || ev.type === 'brain2') {
      row.className = 'bubble-row ' + (ev.type === 'brain1' ? 'b1' : 'b2');
      const who = ev.type === 'brain1' ? 'Brain 1 · User 1' : ('Brain 2' + (ev.label ? ' · ' + ev.label : ''));
      const avatar = ev.type === 'brain1' ? '<div class="avatar brain1">🧠</div>' : '<div class="avatar brain2">🤖</div>';
      const bubble = `<div class="bubble"><span class="who">${esc(who)}</span>${esc(ev.text)}</div>`;
      row.innerHTML = ev.type === 'brain1' ? (avatar + bubble) : (bubble + avatar);
    } else if (ev.type === 'milestone') {
      row.className = 'milestone'; row.textContent = ev.text;
    } else if (ev.type === 'banner') {
      row.className = 'banner'; row.textContent = ev.text;
    } else if (ev.type === 'heartbeat') {
      continue; // reflected in the stats strip, not the feed, to keep the chat readable
    } else {
      row.className = 'system'; row.textContent = ev.text;
    }
    feed.appendChild(row);
  }
  window.scrollTo(0, document.body.scrollHeight);
}

function esc(s) {
  const d = document.createElement('div'); d.textContent = s; return d.innerHTML;
}

poll();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    log_file: Path | None = None

    def log_message(self, fmt, *args):  # quiet — don't spam the terminal per poll
        pass

    def do_GET(self) -> None:
        if self.path.startswith('/api/state'):
            log_path = Handler.log_file or _latest_log_file()
            data = _parse_log(log_path) if log_path else {'events': [], 'summary': {}, 'log_file': None}
            body = json.dumps(data).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        body = _INDEX_HTML.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--log-file', type=str, default=None, help='Pin to one log file instead of auto-following the newest.')
    args = parser.parse_args()

    Handler.log_file = Path(args.log_file).resolve() if args.log_file else None

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    chosen = Handler.log_file or _latest_log_file()
    print(f'Serving simulation UI at http://127.0.0.1:{args.port}  (watching: {chosen})')
    server.serve_forever()


if __name__ == '__main__':
    main()
