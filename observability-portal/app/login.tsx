'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import type { Profile } from './onboarding';

const API_BASE = 'http://localhost:8000';

type ProfileSummary = Pick<Profile, 'fullName' | 'email' | 'photoDataUrl'>;

export default function Login({
  onLoggedIn,
  onNewProfile,
}: {
  onLoggedIn: (profile: Profile) => void;
  onNewProfile: (email: string) => void;
}) {
  const [email, setEmail] = useState('');
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [known, setKnown] = useState<ProfileSummary[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/profiles`)
      .then((res) => (res.ok ? res.json() : []))
      .then((rows: any[]) =>
        setKnown(rows.map((r) => ({ fullName: r.full_name, email: r.email, photoDataUrl: r.photo_data_url }))),
      )
      .catch(() => setKnown([]));
  }, []);

  const attemptLogin = async (candidateEmail: string) => {
    const trimmed = candidateEmail.trim();
    if (!trimmed) return;
    setChecking(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/profiles/${encodeURIComponent(trimmed)}`);
      if (res.ok) {
        const row = await res.json();
        onLoggedIn({
          fullName: row.full_name,
          email: row.email,
          dob: row.dob ?? '',
          location: row.location ?? '',
          interests: row.interests ?? [],
          otherInterests: row.other_interests ?? '',
          photoDataUrl: row.photo_data_url ?? null,
          quote: row.quote ?? '',
        });
        return;
      }
      if (res.status === 404) {
        onNewProfile(trimmed);
        return;
      }
      setError('Something went wrong checking that email.');
    } catch {
      setError('Could not reach the service. Is orchestration-service running?');
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="onboarding-shell">
      <div className="onboarding-body login-body">
        <p className="onboarding-step">Welcome</p>
        <h1>What&apos;s your email?</h1>
        <p className="onboarding-sub">We&apos;ll find your profile, or help you create a new one.</p>

        <div className="form-field-input">
          <input
            type="email"
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && attemptLogin(email)}
            placeholder="you@example.com"
          />
          {email && (
            <button type="button" className="field-clear" aria-label="Clear email" onClick={() => setEmail('')}>
              ×
            </button>
          )}
        </div>

        {error && <p className="error-text">{error}</p>}

        <motion.button
          type="button"
          className="onboarding-continue"
          whileTap={{ scale: 0.97 }}
          disabled={!email.trim() || checking}
          onClick={() => attemptLogin(email)}
        >
          {checking ? 'Checking…' : 'Continue'} <span aria-hidden>→</span>
        </motion.button>

        {known.length > 0 && (
          <div className="known-profiles">
            <p className="known-profiles-label">Saved profiles (for testing)</p>
            {known.map((p) => (
              <button key={p.email} type="button" className="known-profile-row" onClick={() => attemptLogin(p.email)}>
                <span className="known-profile-avatar">
                  {p.photoDataUrl ? (
                    <img src={p.photoDataUrl} alt="" />
                  ) : (
                    p.fullName.trim().charAt(0).toUpperCase() || '?'
                  )}
                </span>
                <span>
                  <span className="known-profile-name">{p.fullName}</span>
                  <span className="known-profile-email">{p.email}</span>
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
