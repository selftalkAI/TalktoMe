'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import type { Profile } from './onboarding';

const API_BASE = 'http://localhost:8000';

type ProfileSummary = Pick<Profile, 'fullName' | 'email' | 'photoDataUrl'>;

function rowToProfile(row: any): Profile {
  return {
    fullName: row.full_name,
    email: row.email,
    dob: row.dob ?? '',
    location: row.location ?? '',
    interests: row.interests ?? [],
    otherInterests: row.other_interests ?? '',
    photoDataUrl: row.photo_data_url ?? null,
    quote: row.quote ?? '',
  };
}

export default function Login({
  onLoggedIn,
  onNewProfile,
}: {
  onLoggedIn: (profile: Profile) => void;
  onNewProfile: (email: string, password: string) => void;
}) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
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

  // One screen, one submit: check whether this email has an account, then
  // either verify the password already sitting in the form (log in) or hand
  // both email and whatever password was typed off to onboarding (so a new
  // person doesn't have to retype it there).
  const submit = async () => {
    const trimmedEmail = email.trim();
    if (!trimmedEmail || !password) return;
    setChecking(true);
    setError(null);
    try {
      const checkRes = await fetch(`${API_BASE}/api/v1/profiles/${encodeURIComponent(trimmedEmail)}`);

      if (checkRes.status === 404) {
        onNewProfile(trimmedEmail, password);
        return;
      }
      if (!checkRes.ok) {
        setError('Something went wrong checking that email.');
        return;
      }

      const loginRes = await fetch(`${API_BASE}/api/v1/profiles/${encodeURIComponent(trimmedEmail)}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });
      if (loginRes.ok) {
        onLoggedIn(rowToProfile(await loginRes.json()));
        return;
      }
      if (loginRes.status === 401) {
        setError('Incorrect password.');
        return;
      }
      setError('Something went wrong logging in.');
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
        <h1>Log in or create a profile</h1>
        <p className="onboarding-sub">Enter your email and a password &mdash; we&apos;ll find your profile, or start a new one.</p>

        <label className="form-field">
          <span>Email</span>
          <div className="form-field-input">
            <input
              type="email"
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submit()}
              placeholder="you@example.com"
            />
            {email && (
              <button type="button" className="field-clear" aria-label="Clear email" onClick={() => setEmail('')}>
                ×
              </button>
            )}
          </div>
        </label>

        <label className="form-field">
          <span>Password</span>
          <div className="form-field-input">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submit()}
              placeholder="Your password"
              autoComplete="current-password"
            />
          </div>
        </label>

        {error && <p className="error-text">{error}</p>}

        <motion.button
          type="button"
          className="onboarding-continue"
          whileTap={{ scale: 0.97 }}
          disabled={!email.trim() || !password || checking}
          onClick={submit}
        >
          {checking ? 'Checking…' : 'Continue'} <span aria-hidden>→</span>
        </motion.button>

        {known.length > 0 && (
          <div className="known-profiles">
            <p className="known-profiles-label">Saved profiles (for testing)</p>
            {known.map((p) => (
              <button key={p.email} type="button" className="known-profile-row" onClick={() => setEmail(p.email)}>
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
