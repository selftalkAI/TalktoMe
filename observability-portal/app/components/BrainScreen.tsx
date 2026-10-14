'use client';

import { AnimatePresence } from 'framer-motion';
import { useCallback, useEffect, useState } from 'react';
import { api, KeyArea, Profile } from '../lib/api';
import { regionColor, regionLabel } from '../lib/brain';
import { useThoughts } from '../lib/useThoughts';
import Icon from './Icon';
import RegionMap from './RegionMap';
import RegionScreen from './RegionScreen';
import ThoughtCard from './ThoughtCard';

export default function BrainScreen({ profile, onAreas }: { profile: Profile; onAreas?: (areas: KeyArea[]) => void }) {
  const email = profile.email;
  const [areas, setAreas] = useState<KeyArea[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [thinkingNow, setThinkingNow] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const { thoughts, busyId, yes, no, refine, refresh } = useThoughts(email);

  const load = useCallback(async () => {
    try {
      const a = await api.keyAreas(email);
      setAreas(a);
      onAreas?.(a);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load your brain.');
    } finally {
      setLoading(false);
    }
  }, [email, onAreas]);

  useEffect(() => {
    load();
  }, [load]);

  const thinkNow = async () => {
    setThinkingNow(true);
    setNote(null);
    try {
      const r = await api.thinkNow();
      await Promise.all([load(), refresh()]);
      setNote(r.drafted_count ? `Your brain drafted ${r.drafted_count} new thought${r.drafted_count > 1 ? 's' : ''}.` : 'Nothing new to think about yet. Keep talking.');
    } catch (e) {
      setNote(e instanceof Error ? e.message : 'Your brain couldn’t think right now.');
    } finally {
      setThinkingNow(false);
    }
  };

  if (open) {
    return (
      <RegionScreen
        profile={profile}
        domain={open}
        onBack={() => {
          setOpen(null);
          load();
          refresh();
        }}
      />
    );
  }

  const neurons = areas.reduce((n, a) => n + a.active_memory_count, 0);

  return (
    <div className="screen">
      <p className="kicker">Your brain</p>
      <h1 className="display">
        The map
        <br />
        of <em>you</em>
      </h1>
      <p className="muted small" style={{ marginTop: 8 }}>
        {neurons} neuron{neurons === 1 ? '' : 's'} · {areas.length} region{areas.length === 1 ? '' : 's'}
        {thoughts.length ? ` · ${thoughts.length} new thought${thoughts.length > 1 ? 's' : ''}` : ''}
      </p>

      <div className="card" style={{ marginTop: 18, padding: 10 }}>
        {loading ? <p className="muted center" style={{ padding: 40 }}>Waking up…</p> : <RegionMap areas={areas} onOpen={setOpen} />}
      </div>
      {error && <p className="error">{error}</p>}

      {thoughts.length > 0 && (
        <section style={{ marginTop: 26 }}>
          <h2 className="title" style={{ fontSize: 24 }}>New thoughts</h2>
          <p className="muted small" style={{ marginTop: 4 }}>Nothing joins your brain until you say so.</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}>
            <AnimatePresence>
              {thoughts.map((t) => (
                <ThoughtCard
                  key={t.id}
                  kind={t.kind}
                  domain={t.domain}
                  text={t.text}
                  busy={busyId === t.id}
                  onYes={async () => {
                    await yes(t);
                    load();
                  }}
                  onNo={() => no(t)}
                  onRefine={t.kind === 'thought' ? (w) => refine(t, w) : undefined}
                />
              ))}
            </AnimatePresence>
          </div>
        </section>
      )}

      <section style={{ marginTop: 26 }}>
        <h2 className="title" style={{ fontSize: 24 }}>Regions</h2>
        <div style={{ marginTop: 6 }}>
          {areas.map((a) => (
            <button key={a.domain} type="button" className="row" onClick={() => setOpen(a.domain)}>
              <span className="dot" style={{ background: regionColor(a.domain) }} />
              <span style={{ flex: 1, fontSize: 16, fontWeight: 500 }}>{regionLabel(a.domain)}</span>
              <span className="small muted">
                {a.active_memory_count ? `${a.active_memory_count} neuron${a.active_memory_count > 1 ? 's' : ''}` : 'quiet'}
              </span>
              {a.has_pending_proposal && <span className="small" style={{ color: 'var(--thought)', fontWeight: 600 }}>new</span>}
              <span className="muted"><Icon name="chevron" size={18} /></span>
            </button>
          ))}
        </div>
      </section>

      <button type="button" className="btn btn-ghost btn-block" style={{ marginTop: 22 }} onClick={thinkNow} disabled={thinkingNow}>
        <Icon name="spark" size={18} />
        {thinkingNow ? 'Thinking…' : 'Let my brain think now'}
      </button>
      {note && <p className="small muted center" style={{ marginTop: 10 }}>{note}</p>}
    </div>
  );
}
