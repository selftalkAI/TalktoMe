'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';

// Brain 1 + Brain 2 in the portal (Building_Brain2.md §12, Building_Brain1.md §8):
//   BrainChat — talk with Brain 2 in any area of life; replies show the persona it
//               spoke as; a profile proposal appears as its own card, never inside chat;
//               Brain 2's proactive check-ins arrive in the same thread.
//   MirrorView — everything Brain 1 believes about you, section by section, with how
//               it knows (said / inferred, confirmed / a guess), plus how well it knows you.

type Turn = { turn_id?: string; role: 'user' | 'assistant'; content: string; proactive?: number; created_at?: string };
type Persona = { voice: string; expertise: string; source: string };
type Proposal = { profile_entry_id: string; domain: string; content: string; version: number };

const AREAS = ['general', 'fitness', 'cooking', 'work', 'money', 'family', 'learning', 'feelings'];
const VOICES: { key: string | null; label: string }[] = [
  { key: null, label: 'Let Brain 1 choose' },
  { key: 'friend', label: 'Friend' },
  { key: 'coach', label: 'Coach' },
  { key: 'big_sister', label: 'Big sister' },
  { key: 'big_brother', label: 'Big brother' },
  { key: 'mother_like', label: 'Mother-like' },
  { key: 'father_like', label: 'Father-like' },
  { key: 'grandparent_like', label: 'Grandparent-like' },
  { key: 'mentor', label: 'Mentor' },
  { key: 'buddy', label: 'Buddy' },
];

const label = (key: string) => key.replace(/_/g, ' ');

export function BrainChat({ apiBase, email }: { apiBase: string; email: string }) {
  const [area, setArea] = useState('general');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [personas, setPersonas] = useState<Record<number, Persona>>({});
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [voice, setVoice] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const enc = encodeURIComponent(email);

  const loadThread = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/api/v1/brain/${enc}/conversation?domain=${encodeURIComponent(area)}&limit=60`);
      if (res.ok) setTurns(await res.json());
    } catch {
      // Quiet: the thread reloads on the next poll.
    }
  }, [apiBase, enc, area]);

  useEffect(() => {
    setPersonas({});
    setProposal(null);
    loadThread();
    // Brain 2's proactive check-ins land in the stored conversation; poll for them.
    const timer = setInterval(loadThread, 30000);
    return () => clearInterval(timer);
  }, [loadThread]);

  useEffect(() => {
    fetch(`${apiBase}/api/v1/brain1/${enc}/voice`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => data && setVoice(data.voice))
      .catch(() => undefined);
  }, [apiBase, enc]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns, thinking]);

  const send = async () => {
    const message = draft.trim();
    if (!message || thinking) return;
    setDraft('');
    setError(null);
    setTurns((prev) => [...prev, { role: 'user', content: message }]);
    setThinking(true);
    try {
      const res = await fetch(`${apiBase}/api/v1/brain/${enc}/turn`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, domain: area }),
      });
      if (!res.ok) throw new Error(await res.text());
      const turn = await res.json();
      setTurns((prev) => {
        setPersonas((p) => ({ ...p, [prev.length]: turn.persona }));
        return [...prev, { role: 'assistant', content: turn.reply }];
      });
      if (turn.proposal) setProposal(turn.proposal);
      fetch(`${apiBase}/api/v1/brain1/${enc}/voice`).then((r) => r.json()).then((d) => setVoice(d.voice)).catch(() => undefined);
    } catch {
      setError("Brain 2 couldn't reply just now — is the Orchestration Service running?");
    } finally {
      setThinking(false);
    }
  };

  const chooseVoice = async (key: string | null) => {
    setVoice(key);
    await fetch(`${apiBase}/api/v1/brain1/${enc}/voice`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ voice: key }),
    }).catch(() => undefined);
  };

  const decide = async (accept: boolean) => {
    if (!proposal) return;
    await fetch(`${apiBase}/api/v1/brain2/profile/proposals/${proposal.profile_entry_id}/${accept ? 'accept' : 'reject'}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile_email: email }),
    }).catch(() => undefined);
    setProposal(null);
  };

  return (
    <section className="brain-chat">
      <div className="chip-row" role="tablist" aria-label="Area of life">
        {AREAS.map((a) => (
          <button key={a} type="button" className={a === area ? 'chip selected' : 'chip'} onClick={() => setArea(a)}>
            {label(a)}
          </button>
        ))}
      </div>

      <label className="voice-picker">
        <span>Brain 2 talks to you like</span>
        <select value={voice ?? ''} onChange={(e) => chooseVoice(e.target.value || null)}>
          {VOICES.map((v) => (
            <option key={v.label} value={v.key ?? ''}>
              {v.label}
            </option>
          ))}
        </select>
      </label>

      <div className="chat-thread">
        {turns.length === 0 && !thinking && (
          <p className="empty-title chat-empty">Tell Brain 2 what&apos;s going on in your {label(area)} life.</p>
        )}
        {turns.map((t, i) => (
          <motion.div
            key={t.turn_id ?? `${i}-${t.content.slice(0, 12)}`}
            className={t.role === 'user' ? 'bubble-row you' : 'bubble-row brain2'}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="chat-bubble">
              {t.role === 'assistant' && (
                <span className="proposal-label">
                  Brain 2
                  {personas[i] ? ` · ${label(personas[i].voice)}${personas[i].source === 'her_choice' ? ' (your choice)' : ''}` : ''}
                  {t.proactive ? ' · checking in' : ''}
                </span>
              )}
              <p>{t.content}</p>
            </div>
          </motion.div>
        ))}
        {thinking && (
          <p className="reflecting">
            <span className="dot-pulse" />
            Brain 1 is thinking it through with Brain 2…
          </p>
        )}
        <AnimatePresence>
          {proposal && (
            <motion.div className="proposal-card" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <span className="proposal-label">I&apos;ve learned something · {label(proposal.domain)} — does this sound right?</span>
              <p className="proposal-content">{proposal.content}</p>
              <div className="proposal-actions">
                <button type="button" className="proposal-accept" onClick={() => decide(true)}>
                  Yes, save it
                </button>
                <button type="button" className="proposal-reject" onClick={() => decide(false)}>
                  Not quite
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={endRef} />
      </div>

      {error && <p className="error-text">{error}</p>}

      <div className="chat-composer">
        <textarea
          rows={1}
          value={draft}
          placeholder="Talk to Brain 2…"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button type="button" className="composer-save" disabled={thinking || !draft.trim()} onClick={send}>
          Send
        </button>
      </div>
    </section>
  );
}

type Field = { value: string; source: string; status: string; confidence: number; tier: string };
type Mirror = {
  sections: Record<string, Field[]>;
  strength: { sections_known: number; sections_total: number; average_confidence: number };
  here_now: { weekday: string; local_time: string; part_of_day: string; season: string; city: string | null; weather: { words: string; temperature_c: number } | null };
  version: number | null;
};

const SECTION_TITLES: [string, string][] = [
  ['identity', 'Who you are'],
  ['people', 'Your people'],
  ['inner_world', 'Inner world'],
  ['body', 'Body & health'],
  ['life_map', 'Your days & places'],
  ['tastes', 'Things you love'],
  ['goals', 'Goals'],
  ['story', 'Your story'],
  ['what_works', 'What works for you'],
  ['communication', 'How you like to be spoken to'],
  ['boundaries', 'Boundaries'],
  ['open_questions', 'Still getting to know'],
];

export function MirrorView({ apiBase, email }: { apiBase: string; email: string }) {
  const [mirror, setMirror] = useState<Mirror | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetch(`${apiBase}/api/v1/brain1/${encodeURIComponent(email)}/profile`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setMirror)
      .catch(() => setFailed(true));
  }, [apiBase, email]);

  if (failed) return <p className="error-text">Couldn&apos;t load what Brain 1 knows — is the Orchestration Service running?</p>;
  if (!mirror) return <p className="reflecting"><span className="dot-pulse" />Loading…</p>;

  const { strength, here_now: now } = mirror;
  return (
    <section className="mirror">
      <div className="mirror-summary">
        <p className="mirror-strength">
          Brain 1 knows {strength.sections_known} of {strength.sections_total} parts of your life
        </p>
        <div className="mirror-bar">
          <div style={{ width: `${Math.round((strength.sections_known / strength.sections_total) * 100)}%` }} />
        </div>
        <p className="hint">
          {now.weekday} {now.part_of_day}, {now.season}
          {now.city ? ` in ${now.city}` : ''}
          {now.weather ? ` · ${now.weather.words}, ${now.weather.temperature_c}°C` : ''}
          {mirror.version ? ` · version ${mirror.version}` : ''}
        </p>
      </div>
      {SECTION_TITLES.map(([key, title]) => {
        const fields = mirror.sections[key] ?? [];
        return (
          <div key={key} className="mirror-section">
            <h3>{title}</h3>
            {fields.length === 0 ? (
              <p className="hint">Nothing yet.</p>
            ) : (
              <ul>
                {fields.map((f, i) => (
                  <li key={`${key}-${i}`}>
                    <span>{f.value}</span>
                    <span className={f.status === 'confirmed' ? 'mirror-tag sure' : 'mirror-tag guess'}>
                      {key === 'open_questions' ? 'to ask' : f.status === 'confirmed' ? `you ${f.source === 'onboarding' ? 'told us at sign-up' : 'said'}` : 'a guess'}
                      {f.tier === 'T3' ? ' · private' : ''}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </section>
  );
}
