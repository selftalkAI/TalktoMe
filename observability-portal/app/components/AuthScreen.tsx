'use client';

import { motion } from 'framer-motion';
import { useState } from 'react';
import { api, ApiError, Profile } from '../lib/api';
import NeuralOrb from './NeuralOrb';

export default function AuthScreen({
  onLoggedIn,
  onNewProfile,
}: {
  onLoggedIn: (p: Profile) => void;
  onNewProfile: (email: string, password: string) => void;
}) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    const e = email.trim();
    if (!e || !e.includes('@')) return setError('Enter your email.');
    if (!password) return setError('Enter a password.');
    setBusy(true);
    setError(null);
    try {
      try {
        await api.getProfile(e);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          if (password.length < 6) {
            setError('New here? Pick a password of at least 6 characters.');
            return;
          }
          onNewProfile(e, password);
          return;
        }
        throw err;
      }
      onLoggedIn(await api.login(e, password));
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? 'That password doesn’t match.' : err instanceof Error ? err.message : 'Something went wrong.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="screen-flat">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginTop: 24 }}
      >
        <NeuralOrb colors={[]} thinking size={220} label="selfie.Me" />
        <p className="kicker" style={{ marginTop: 10 }}>selfie.Me</p>
      </motion.div>

      <motion.h1
        className="display"
        style={{ fontSize: 48, marginTop: 22 }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2, duration: 0.6 }}
      >
        Talk to yourself.
        <br />
        <em>Your brain is listening.</em>
      </motion.h1>
      <p className="muted" style={{ marginTop: 12 }}>It remembers what you say, notices patterns, and only keeps what you agree is you.</p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        style={{ marginTop: 'auto', paddingTop: 28 }}
      >
        <label className="field">
          <span>Email</span>
          <input className="input" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
        </label>
        <label className="field">
          <span>Password</span>
          <input className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 6 characters" />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" className="btn btn-primary btn-block" style={{ marginTop: 20 }} disabled={busy}>
          {busy ? 'Opening…' : 'Open my brain'}
        </button>
        <p className="small muted center" style={{ marginTop: 12 }}>New here? The same button creates your brain.</p>
      </form>
    </main>
  );
}
