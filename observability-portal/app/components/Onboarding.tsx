'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { ChangeEvent, useState } from 'react';
import { api, Profile } from '../lib/api';
import Icon from './Icon';

const INTERESTS: Array<{ key: string; label: string; color: string }> = [
  { key: 'parenting', label: 'Parenting', color: '#E8B86B' },
  { key: 'healthy_living', label: 'Healthy living', color: '#9FD8B5' },
  { key: 'learning', label: 'Learning', color: '#7FC4D8' },
  { key: 'mindfulness', label: 'Mindfulness', color: '#B9A6F2' },
  { key: 'career', label: 'Career & work', color: '#F0997B' },
  { key: 'community', label: 'Community', color: '#E59BC0' },
  { key: 'travel', label: 'Travel', color: '#8FB8F2' },
  { key: 'recipes', label: 'Cooking', color: '#F2C46B' },
  { key: 'home_lifestyle', label: 'Home', color: '#C7D67A' },
  { key: 'photography', label: 'Photography', color: '#9FD8B5' },
  { key: 'finance', label: 'Money', color: '#E8B86B' },
  { key: 'kids_activities', label: 'Kids', color: '#F0997B' },
];

export default function Onboarding({
  email,
  password,
  onDone,
  onBack,
}: {
  email: string;
  password: string;
  onDone: (p: Profile) => void;
  onBack: () => void;
}) {
  const [step, setStep] = useState(1);
  const [name, setName] = useState('');
  const [confirm, setConfirm] = useState('');
  const [dob, setDob] = useState('');
  const [location, setLocation] = useState('');
  const [interests, setInterests] = useState<string[]>([]);
  const [other, setOther] = useState('');
  const [quote, setQuote] = useState('');
  const [photo, setPhoto] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const next = () => {
    setError(null);
    if (step === 1) {
      if (!name.trim()) return setError('What should your brain call you?');
      if (confirm !== password) return setError('Passwords don’t match. Type the same one again.');
    }
    setStep((s) => s + 1);
  };

  const onPhoto = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 1_400_000) return setError('That photo is too big. Pick one under 1.4 MB.');
    const r = new FileReader();
    r.onload = () => setPhoto(r.result as string);
    r.readAsDataURL(f);
  };

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const p = await api.createProfile({
        email,
        password,
        full_name: name.trim(),
        dob: dob || null,
        location: location.trim() || null,
        interests,
        other_interests: other.trim() || null,
        photo_data_url: photo,
        quote: quote.trim() || null,
      });
      onDone(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Couldn’t create your brain. Try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="screen-flat">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button type="button" className="icon-btn" aria-label="Back" onClick={() => (step === 1 ? onBack() : setStep(step - 1))}>
          <Icon name="back" />
        </button>
        <div className="steps" style={{ flex: 1, margin: 0 }} aria-label={`Step ${step} of 3`}>
          {[1, 2, 3].map((n) => (
            <span key={n} className={n <= step ? 'on' : ''} />
          ))}
        </div>
      </div>

      <AnimatePresence mode="wait">
        <motion.section
          key={step}
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -24 }}
          transition={{ duration: 0.25 }}
          style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
        >
          {step === 1 && (
            <>
              <p className="kicker" style={{ marginTop: 26 }}>Step 1 of 3</p>
              <h1 className="title" style={{ fontSize: 36 }}>Who is this brain <em>for?</em></h1>
              <label className="field">
                <span>Your name</span>
                <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Sujitha Salla" autoComplete="name" />
              </label>
              <label className="field">
                <span>Type your password again</span>
                <input className="input" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', gap: 10 }}>
                <label className="field">
                  <span>Birthday</span>
                  <input className="input" type="date" value={dob} onChange={(e) => setDob(e.target.value)} />
                </label>
                <label className="field">
                  <span>Where you live</span>
                  <input className="input" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Langley, BC" />
                </label>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <p className="kicker" style={{ marginTop: 26 }}>Step 2 of 3</p>
              <h1 className="title" style={{ fontSize: 36 }}>What lives in your <em>mind</em> most days?</h1>
              <p className="muted small" style={{ marginTop: 8 }}>These become the first regions of your brain. Pick any.</p>
              <div className="interest-grid">
                {INTERESTS.map((i) => {
                  const on = interests.includes(i.key);
                  return (
                    <button
                      key={i.key}
                      type="button"
                      className="interest"
                      aria-pressed={on}
                      onClick={() => setInterests((xs) => (on ? xs.filter((x) => x !== i.key) : [...xs, i.key]))}
                    >
                      <span className="dot" style={{ background: i.color, width: on ? 16 : 12, height: on ? 16 : 12, transition: 'all 150ms' }} />
                      {i.label}
                    </button>
                  );
                })}
              </div>
              <label className="field">
                <span>Anything else?</span>
                <input className="input" value={other} onChange={(e) => setOther(e.target.value)} placeholder="Gardening, poetry, my garage band" />
              </label>
            </>
          )}

          {step === 3 && (
            <>
              <p className="kicker" style={{ marginTop: 26 }}>Step 3 of 3</p>
              <h1 className="title" style={{ fontSize: 36 }}>A face, and a line <em>you live by</em></h1>
              <label style={{ alignSelf: 'center', marginTop: 24, cursor: 'pointer', position: 'relative' }}>
                <input type="file" accept="image/*" onChange={onPhoto} className="sr-only" />
                {photo ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={photo} alt="Your photo" className="avatar" style={{ width: 128, height: 128 }} />
                ) : (
                  <span className="avatar" style={{ width: 128, height: 128, fontSize: 44, border: '1px dashed var(--line-strong)' }}>
                    {name.trim().charAt(0) || '?'}
                  </span>
                )}
                <span className="icon-btn solid" style={{ position: 'absolute', right: -4, bottom: -4, width: 44, height: 44 }}>
                  <Icon name="camera" />
                </span>
                <span className="sr-only">Add a photo</span>
              </label>
              <label className="field" style={{ marginTop: 24 }}>
                <span>Your line</span>
                <textarea className="textarea" value={quote} onChange={(e) => setQuote(e.target.value)} placeholder="Kind people raise kind humans." style={{ fontFamily: 'var(--serif)', fontSize: 20 }} />
              </label>
              <p className="small muted" style={{ marginTop: 10 }}>Your brain is private to you. Nothing about you joins it without your yes.</p>
            </>
          )}
        </motion.section>
      </AnimatePresence>

      {error && <p className="error" role="alert">{error}</p>}
      <button type="button" className="btn btn-primary btn-block" style={{ marginTop: 20 }} disabled={busy} onClick={step < 3 ? next : create}>
        {step < 3 ? 'Continue' : busy ? 'Creating your brain…' : 'Create my brain'}
      </button>
    </main>
  );
}
