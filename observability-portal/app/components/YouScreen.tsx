'use client';

import { useEffect, useState } from 'react';
import { api, Evolution, KeyArea, Profile } from '../lib/api';
import { firstName, regionColor, regionLabel } from '../lib/brain';
import Icon from './Icon';

type Theme = 'dusk' | 'day';

export default function YouScreen({
  profile,
  areas,
  onStory,
  onLogout,
}: {
  profile: Profile;
  areas: KeyArea[];
  onStory: () => void;
  onLogout: () => void;
}) {
  const [evo, setEvo] = useState<Evolution | null>(null);
  const [theme, setTheme] = useState<Theme>('dusk');

  useEffect(() => {
    api.evolution(profile.email, 7).then(setEvo).catch(() => setEvo(null));
    const t = document.documentElement.dataset.theme;
    setTheme(t === 'day' ? 'day' : 'dusk');
  }, [profile.email]);

  const switchTheme = (t: Theme) => {
    setTheme(t);
    document.documentElement.dataset.theme = t;
    try {
      localStorage.setItem('selfieme_theme', t);
    } catch {
      /* storage off: theme just won't persist */
    }
  };

  const neurons = areas.reduce((n, a) => n + a.active_memory_count, 0);
  const known = areas.filter((a) => a.accepted_entry).length;

  return (
    <div className="screen">
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
        {profile.photo_data_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={profile.photo_data_url} alt="" className="avatar" style={{ width: 112, height: 112, border: '3px solid var(--accent)' }} />
        ) : (
          <span className="avatar" style={{ width: 112, height: 112, fontSize: 44, border: '3px solid var(--accent)' }}>
            {firstName(profile.full_name).charAt(0)}
          </span>
        )}
        <h1 className="title" style={{ fontSize: 34, marginTop: 14 }}>{profile.full_name}</h1>
        {profile.location && <p className="muted small" style={{ margin: '4px 0 0' }}>{profile.location}</p>}
        {profile.quote && (
          <p className="say" style={{ marginTop: 16, fontStyle: 'italic', color: 'var(--thought)' }}>&ldquo;{profile.quote}&rdquo;</p>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0,1fr))', gap: 10, marginTop: 24 }}>
        {[
          { n: evo?.total_moments_all_time ?? '–', l: 'thoughts' },
          { n: neurons, l: 'neurons' },
          { n: known, l: 'regions known' },
        ].map((s) => (
          <div key={s.l} className="card" style={{ padding: '16px 8px', textAlign: 'center', borderRadius: 22 }}>
            <div className="serif" style={{ fontSize: 32, lineHeight: 1 }}>{s.n}</div>
            <div className="small muted" style={{ marginTop: 6 }}>{s.l}</div>
          </div>
        ))}
      </div>

      {areas.length > 0 && (
        <div className="chips" style={{ marginTop: 16, justifyContent: 'center' }}>
          {areas.map((a) => (
            <span key={a.domain} className="chip">
              <span className="dot" style={{ background: regionColor(a.domain), width: 8, height: 8 }} />
              {regionLabel(a.domain)}
            </span>
          ))}
        </div>
      )}

      <button type="button" className="btn btn-thought btn-block" style={{ marginTop: 24 }} onClick={onStory}>
        <Icon name="story" size={18} />
        Your week, inside your head
      </button>

      <section className="card" style={{ marginTop: 18, padding: '6px 18px' }}>
        <div className="row" style={{ cursor: 'default' }}>
          <span className="muted"><Icon name={theme === 'dusk' ? 'moon' : 'sun'} /></span>
          <span style={{ flex: 1 }}>Look</span>
          <div className="chips" role="group" aria-label="Theme">
            <button type="button" className="chip" aria-pressed={theme === 'dusk'} onClick={() => switchTheme('dusk')}>Dusk</button>
            <button type="button" className="chip" aria-pressed={theme === 'day'} onClick={() => switchTheme('day')}>Day</button>
          </div>
        </div>
        <div className="row" style={{ cursor: 'default' }}>
          <span className="muted"><Icon name="user" /></span>
          <span style={{ flex: 1 }}>Signed in as</span>
          <span className="small muted">{profile.email}</span>
        </div>
        <button type="button" className="row" onClick={onLogout} style={{ color: 'var(--danger)' }}>
          <Icon name="logout" />
          <span style={{ flex: 1 }}>Log out</span>
        </button>
      </section>
      <p className="small muted center" style={{ marginTop: 16 }}>Your brain is private to you. Nothing joins it without your yes.</p>
    </div>
  );
}
