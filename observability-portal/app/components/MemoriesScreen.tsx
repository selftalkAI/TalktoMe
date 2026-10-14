'use client';

import { useEffect, useMemo, useState } from 'react';
import { api, Moment, Profile } from '../lib/api';
import { moodColor, shortDate } from '../lib/brain';
import Icon from './Icon';

export default function MemoriesScreen({ profile, onStory }: { profile: Profile; onStory: () => void }) {
  const [moments, setMoments] = useState<Moment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');

  useEffect(() => {
    api.listMoments(profile.email).then(setMoments).catch((e) => setError(e instanceof Error ? e.message : 'Could not load your memories.'));
  }, [profile.email]);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q ? moments.filter((m) => m.content.toLowerCase().includes(q) || (m.reflection ?? '').toLowerCase().includes(q)) : moments;
    const out: Array<{ day: string; items: Moment[] }> = [];
    for (const m of list) {
      const day = shortDate(m.created_at);
      const g = out[out.length - 1];
      if (g && g.day === day) g.items.push(m);
      else out.push({ day, items: [m] });
    }
    return out;
  }, [moments, query]);

  return (
    <div className="screen">
      <p className="kicker">Memories</p>
      <h1 className="display">Everything<br />you’ve <em>said</em></h1>

      <button type="button" className="card" onClick={onStory} style={{ marginTop: 20, width: '100%', textAlign: 'left', display: 'flex', alignItems: 'center', gap: 16, background: '#3b1f2b', borderColor: '#4e2a39', color: '#fbe8da' }}>
        <span style={{ width: 52, height: 52, borderRadius: 26, background: '#f0b394', color: '#3b1f2b', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
          <Icon name="story" />
        </span>
        <span style={{ flex: 1 }}>
          <span style={{ display: 'block', fontWeight: 700, fontSize: 17 }}>Your week, inside your head</span>
          <span style={{ display: 'block', fontSize: 13, color: '#e7c2b0', marginTop: 2 }}>A 3-part story from what you said</span>
        </span>
        <Icon name="chevron" />
      </button>

      <label className="field" style={{ marginTop: 20 }}>
        <span className="sr-only">Search your memories</span>
        <input className="pill-input" style={{ width: '100%', flex: 'none' }} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search what you’ve said…" />
      </label>
      {error && <p className="error">{error}</p>}

      {groups.length === 0 && !error && <p className="empty" style={{ marginTop: 18 }}>{query ? 'Nothing matches that yet.' : 'Your memories start the first time you talk to yourself.'}</p>}

      {groups.map((g) => (
        <section key={g.day} style={{ marginTop: 22 }}>
          <p className="kicker">{g.day}</p>
          <ol style={{ listStyle: 'none', padding: 0, margin: '10px 0 0', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {g.items.map((m) => (
              <li key={m.id} className="card" style={{ padding: 16, borderRadius: 22 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="dot" style={{ background: moodColor(m.mood), width: 10, height: 10 }} />
                  <span className="small muted">
                    {new Date(m.created_at).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}
                    {m.mood ? ` · ${m.mood}` : ''}
                    {m.source === 'voice' ? ' · spoken' : ''}
                  </span>
                </div>
                <p style={{ margin: '8px 0 0', fontSize: 15, lineHeight: 1.5 }}>{m.content}</p>
                {m.reflection && (
                  <p className="say" style={{ fontSize: 17, marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--line)', color: 'var(--muted)' }}>
                    {m.reflection}
                  </p>
                )}
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}
