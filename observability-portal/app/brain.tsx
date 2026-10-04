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

export function BrainChat({ apiBase, email, initialDraft = '' }: { apiBase: string; email: string; initialDraft?: string }) {
  const [area, setArea] = useState('general');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [personas, setPersonas] = useState<Record<number, Persona>>({});
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [consentAsk, setConsentAsk] = useState<{ category: string; question: string } | null>(null);
  const [voice, setVoice] = useState<string | null>(null);
  const [draft, setDraft] = useState(initialDraft);
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
      if (turn.consent_requests?.length) setConsentAsk(turn.consent_requests[0]);
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

  const answerConsent = async (granted: boolean) => {
    if (!consentAsk) return;
    await fetch(`${apiBase}/api/v1/brain1/${enc}/consents/${consentAsk.category}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ granted }),
    }).catch(() => undefined);
    setConsentAsk(null);
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
        <AnimatePresence>
          {consentAsk && (
            <motion.div className="proposal-card consent-card" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <span className="proposal-label">Private · {consentAsk.category}</span>
              <p className="proposal-content">{consentAsk.question}</p>
              <div className="proposal-actions">
                <button type="button" className="proposal-accept" onClick={() => answerConsent(true)}>
                  Yes, remember
                </button>
                <button type="button" className="proposal-reject" onClick={() => answerConsent(false)}>
                  No, keep it out
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

type Field = {
  value: string; source: string; status: string; confidence: number; tier: string;
  memory_id?: string; question_id?: string;
};
type Mirror = {
  sections: Record<string, Field[]>;
  strength: { sections_known: number; sections_total: number; average_confidence: number; prediction_accuracy: number | null; correction_rate: number | null };
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
  const [consents, setConsents] = useState<Record<string, boolean | null>>({});
  const [failed, setFailed] = useState(false);
  const [editing, setEditing] = useState<{ id: string; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const enc = encodeURIComponent(email);

  const load = useCallback(() => {
    fetch(`${apiBase}/api/v1/brain1/${enc}/profile`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setMirror)
      .catch(() => setFailed(true));
    fetch(`${apiBase}/api/v1/brain1/${enc}/consents`)
      .then((r) => (r.ok ? r.json() : {}))
      .then(setConsents)
      .catch(() => undefined);
  }, [apiBase, enc]);

  useEffect(load, [load]);

  // Every change goes through the memory layer: confirm, correct (supersedes, never
  // overwrites), suppress, or delete — then the mirror is rebuilt from scratch.
  const act = async (key: string, request: () => Promise<Response>) => {
    setBusy(key);
    try {
      await request();
    } finally {
      setBusy(null);
      setEditing(null);
      load();
    }
  };
  const memoryUrl = (id: string, action = '') => `${apiBase}/api/v1/memories/${id}${action}?profile_email=${enc}`;
  const confirm = (id: string) => act(id, () => fetch(memoryUrl(id, '/confirm'), { method: 'PATCH' }));
  const dismiss = (id: string) => act(id, () => fetch(memoryUrl(id, '/suppress'), { method: 'PATCH' }));
  const forget = (id: string) => act(id, () => fetch(memoryUrl(id), { method: 'DELETE' }));
  const correct = (id: string, content: string) =>
    act(id, () => fetch(memoryUrl(id, '/correct'), { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content }) }));
  const skip = (qid: string) =>
    act(qid, () => fetch(`${apiBase}/api/v1/brain1/${enc}/questions/${qid}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: 'dropped' }) }));
  const setConsent = (category: string, granted: boolean) =>
    act(category, () => fetch(`${apiBase}/api/v1/brain1/${enc}/consents/${category}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ granted }) }));

  if (failed) return <p className="error-text">Couldn&apos;t load what Brain 1 knows — is the Orchestration Service running?</p>;
  if (!mirror) return <p className="reflecting"><span className="dot-pulse" />Loading…</p>;

  const { strength, here_now: now } = mirror;
  const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`);
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
          Patterns you agreed with: {pct(strength.prediction_accuracy)} · Things you had to correct: {pct(strength.correction_rate)}
        </p>
        <p className="hint">
          {now.weekday} {now.part_of_day}, {now.season}
          {now.city ? ` in ${now.city}` : ''}
          {now.weather ? ` · ${now.weather.words}, ${now.weather.temperature_c}°C` : ''}
          {mirror.version ? ` · version ${mirror.version}` : ''}
        </p>
      </div>

      <div className="mirror-section">
        <h3>Private details</h3>
        <p className="hint">Health and money details are only used when you say so. You can change this any time.</p>
        {(['health', 'finances'] as const).map((category) => (
          <label key={category} className="consent-row">
            <span>Let Brain 2 use my {category} details</span>
            <input type="checkbox" checked={consents[category] === true} disabled={busy === category}
              onChange={(e) => setConsent(category, e.target.checked)} />
          </label>
        ))}
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
                {fields.map((f, i) => {
                  const id = f.memory_id;
                  const isEditing = id && editing?.id === id;
                  return (
                    <li key={`${key}-${i}`}>
                      <div className="mirror-row">
                        {isEditing ? (
                          <input className="mirror-edit" value={editing.text} autoFocus
                            onChange={(e) => setEditing({ id, text: e.target.value })}
                            onKeyDown={(e) => { if (e.key === 'Enter' && editing.text.trim()) correct(id, editing.text.trim()); }} />
                        ) : (
                          <span>{f.value}</span>
                        )}
                        <span className={f.status === 'confirmed' ? 'mirror-tag sure' : 'mirror-tag guess'}>
                          {key === 'open_questions' ? 'to ask' : f.status === 'confirmed' ? `you ${f.source === 'onboarding' ? 'told us at sign-up' : 'said'}` : 'a guess'}
                          {f.tier === 'T3' ? ' · private' : ''}
                        </span>
                      </div>
                      {(id || f.question_id) && (
                        <div className="mirror-actions">
                          {f.question_id && <button type="button" disabled={busy === f.question_id} onClick={() => skip(f.question_id!)}>Don&apos;t ask</button>}
                          {id && f.status !== 'confirmed' && (
                            <>
                              <button type="button" disabled={busy === id} onClick={() => confirm(id)}>That&apos;s right</button>
                              <button type="button" disabled={busy === id} onClick={() => dismiss(id)}>Not true</button>
                            </>
                          )}
                          {id && f.status === 'confirmed' && !isEditing && (
                            <>
                              <button type="button" disabled={busy === id} onClick={() => setEditing({ id, text: f.value })}>Fix</button>
                              <button type="button" disabled={busy === id} onClick={() => forget(id)}>Forget</button>
                            </>
                          )}
                          {isEditing && (
                            <>
                              <button type="button" disabled={!editing.text.trim()} onClick={() => correct(id, editing.text.trim())}>Save</button>
                              <button type="button" onClick={() => setEditing(null)}>Cancel</button>
                            </>
                          )}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        );
      })}
    </section>
  );
}
