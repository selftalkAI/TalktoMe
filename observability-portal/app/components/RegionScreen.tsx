'use client';

import { useCallback, useEffect, useState } from 'react';
import { api, Memory, Profile, ProfileEntry } from '../lib/api';
import { regionColor, regionLabel, shortDate } from '../lib/brain';
import Icon from './Icon';
import Sheet from './Sheet';
import ThoughtCard from './ThoughtCard';

export default function RegionScreen({ profile, domain, onBack }: { profile: Profile; domain: string; onBack: () => void }) {
  const email = profile.email;
  const color = regionColor(domain);
  const [accepted, setAccepted] = useState<ProfileEntry | null>(null);
  const [pending, setPending] = useState<ProfileEntry | null>(null);
  const [versions, setVersions] = useState(0);
  const [neurons, setNeurons] = useState<Memory[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [words, setWords] = useState('');
  const [wordsError, setWordsError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [region, mems] = await Promise.all([api.region(email, domain), api.memories(email, { domain })]);
      setAccepted(region.accepted);
      const latest = region.history[region.history.length - 1];
      setPending(latest && latest.status === 'proposed' ? latest : null);
      setVersions(region.history.filter((h) => h.status === 'accepted' || h.status === 'superseded').length);
      setNeurons(mems);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not open this region.');
    }
  }, [email, domain]);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That didn’t go through.');
    } finally {
      setBusy(false);
    }
  };

  const ask = async () => {
    if (!words.trim()) {
      setWordsError('Tell your brain something about this first.');
      return;
    }
    await run(() => api.askRegion(email, domain, words.trim()));
    setAsking(false);
    setWords('');
  };

  return (
    <div className="screen" style={{ paddingTop: 0 }}>
      <div style={{ margin: '0 -20px', padding: 'calc(env(safe-area-inset-top) + 24px) 20px 40px', background: 'var(--surface-2)', position: 'relative', overflow: 'hidden' }}>
        <svg aria-hidden="true" width="190" height="150" viewBox="0 0 200 160" style={{ position: 'absolute', right: -16, top: 34 }}>
          <g stroke={color} strokeWidth="1" opacity="0.45">
            <path d="M40 80 L100 40 L160 70 L120 130 L60 120 Z M100 40 L120 130 M40 80 L160 70" fill="none" />
          </g>
          {[[100, 40, 12], [160, 70, 8], [40, 80, 7], [120, 130, 10], [60, 120, 5]].map(([x, y, r], i) => (
            <circle key={i} cx={x} cy={y} r={r} fill={color} opacity={i < Math.max(1, Math.min(5, neurons.length)) ? 1 : 0.25} />
          ))}
        </svg>
        <button type="button" className="icon-btn" aria-label="Back to your brain" onClick={onBack}>
          <Icon name="back" />
        </button>
        <p className="kicker" style={{ marginTop: 18, color }}>
          Region · {neurons.length} neuron{neurons.length === 1 ? '' : 's'}
        </p>
        <h1 className="display" style={{ fontSize: 40 }}>{regionLabel(domain)}</h1>
      </div>

      <div className="card" style={{ marginTop: -22, position: 'relative' }}>
        <p className="kicker">What your brain knows{versions > 1 ? ` · version ${versions}` : ''}</p>
        {accepted ? (
          <p className="say" style={{ fontSize: 20, marginTop: 10, lineHeight: 1.45 }}>{accepted.content}</p>
        ) : (
          <p className="muted" style={{ marginTop: 10 }}>Nothing yet. When you agree with a thought about {regionLabel(domain).toLowerCase()}, it lives here.</p>
        )}
        {accepted?.accepted_at && <p className="small muted" style={{ marginTop: 10 }}>You agreed {shortDate(accepted.accepted_at).toLowerCase()}.</p>}
      </div>

      {pending && (
        <div style={{ marginTop: 14 }}>
          <ThoughtCard
            kind="thought"
            domain={null}
            text={pending.content}
            busy={busy}
            onYes={() => run(() => api.accept(email, pending.profile_entry_id))}
            onNo={() => run(() => api.reject(email, pending.profile_entry_id))}
            onRefine={(w) => run(() => api.refine(email, pending.profile_entry_id, w))}
          />
          <p className="small muted center" style={{ marginTop: 8 }}>Nothing joins your brain until you say so.</p>
        </div>
      )}
      {error && <p className="error">{error}</p>}

      <h2 className="title" style={{ fontSize: 24, marginTop: 26 }}>Neurons in this region</h2>
      {neurons.length === 0 ? (
        <p className="empty" style={{ marginTop: 12 }}>No neurons here yet. Talk about {regionLabel(domain).toLowerCase()} and they’ll appear.</p>
      ) : (
        <ol style={{ listStyle: 'none', padding: 0, margin: '12px 0 0' }}>
          {neurons.map((m, i) => (
            <li key={m.memory_id} style={{ display: 'flex', gap: 14 }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 14 }}>
                <span className="dot" style={{ background: color, marginTop: 5 }} />
                {i < neurons.length - 1 && <span style={{ flex: 1, width: 1, background: 'var(--line-strong)' }} />}
              </div>
              <div style={{ paddingBottom: 16, flex: 1 }}>
                <p className="small muted" style={{ margin: 0 }}>{shortDate(m.created_at)}</p>
                <p style={{ margin: '2px 0 0', fontSize: 15 }}>{m.content}</p>
              </div>
              <button
                type="button"
                className="btn btn-quiet btn-sm"
                style={{ padding: '0 8px', height: 36 }}
                aria-label={`Forget: ${m.content}`}
                onClick={() => run(() => api.forgetMemory(email, m.memory_id))}
              >
                Forget
              </button>
            </li>
          ))}
        </ol>
      )}

      {!pending && (
        <button type="button" className="btn btn-primary btn-block" style={{ marginTop: 18 }} onClick={() => setAsking(true)}>
          Tell your brain about {regionLabel(domain).toLowerCase()}
        </button>
      )}

      <Sheet open={asking} onClose={() => setAsking(false)} label={`Tell your brain about ${regionLabel(domain)}`}>
        <p className="kicker" style={{ color }}>{regionLabel(domain)}</p>
        <h2 className="title" style={{ fontSize: 28 }}>What’s true about you here, right now?</h2>
        <label className="field">
          <span className="sr-only">Your words</span>
          <textarea
            className="textarea"
            value={words}
            autoFocus
            onChange={(e) => {
              setWords(e.target.value);
              setWordsError(null);
            }}
            placeholder="I read when the house finally goes quiet. It's the only time that's mine."
          />
        </label>
        {wordsError && <p className="error">{wordsError}</p>}
        <button type="button" className="btn btn-primary btn-block" style={{ marginTop: 16 }} onClick={ask} disabled={busy}>
          {busy ? 'Thinking…' : 'Let my brain think about it'}
        </button>
        <p className="small muted center" style={{ marginTop: 10 }}>You’ll see the new thought here before it joins your brain.</p>
      </Sheet>
    </div>
  );
}
