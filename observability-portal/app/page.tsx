'use client';

import { useCallback, useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import Login from './login';
import Onboarding, { Profile } from './onboarding';
import Welcome from './welcome';
import { BrainChat, MirrorView } from './brain';

const API_BASE = 'http://localhost:8000';
// Only the email is persisted — never a password. On reload, it's used to
// re-fetch the profile fresh from the server (GET /api/v1/profiles/{email}),
// so what's in localStorage is a pointer, not a cached credential.
const SESSION_EMAIL_KEY = 'selfieme_session_email';

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

function greeting(): string {
  const h = new Date().getHours();
  if (h < 5) return 'Still up';
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
}

export default function HomePage() {
  // Today = what Brain 2 is waiting on you for; Talk = the conversation; Me = Brain 1's mirror view.
  const [view, setView] = useState<'today' | 'talk' | 'me'>('today');
  const [talkDraft, setTalkDraft] = useState('');

  // The app always STARTS on login, but a reload shouldn't act like a fresh
  // login — 'checking-session' covers the moment between mount and knowing
  // whether a persisted session (SESSION_EMAIL_KEY) still resolves to a real
  // profile, so a refresh doesn't flash the login screen before jumping
  // straight back into the app.
  const [screen, setScreen] = useState<'checking-session' | 'login' | 'onboarding' | 'welcome' | 'app'>(
    'checking-session',
  );
  const [pendingEmail, setPendingEmail] = useState('');
  const [pendingPassword, setPendingPassword] = useState('');
  const [profile, setProfile] = useState<Profile | null>(null);

  useEffect(() => {
    const savedEmail = typeof window !== 'undefined' ? window.localStorage.getItem(SESSION_EMAIL_KEY) : null;
    if (!savedEmail) {
      setScreen('login');
      return;
    }
    fetch(`${API_BASE}/api/v1/profiles/${encodeURIComponent(savedEmail)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((row) => {
        if (row) {
          setProfile(rowToProfile(row));
          setScreen('app');
        } else {
          window.localStorage.removeItem(SESSION_EMAIL_KEY);
          setScreen('login');
        }
      })
      .catch(() => setScreen('login'));
  }, []);

  const persistSession = (email: string) => {
    try {
      window.localStorage.setItem(SESSION_EMAIL_KEY, email);
    } catch {
      // Private browsing / storage disabled — session just won't survive a reload.
    }
  };

  const handleLoggedIn = (existingProfile: Profile) => {
    setProfile(existingProfile);
    persistSession(existingProfile.email);
    setScreen('welcome');
  };

  const handleNewProfile = (email: string, password: string) => {
    setPendingEmail(email);
    setPendingPassword(password);
    setScreen('onboarding');
  };

  const handleOnboardingComplete = async (newProfile: Profile) => {
    const res = await fetch(`${API_BASE}/api/v1/profiles`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: newProfile.email,
        full_name: newProfile.fullName,
        password: newProfile.password,
        dob: newProfile.dob || null,
        location: newProfile.location || null,
        interests: newProfile.interests,
        other_interests: newProfile.otherInterests || null,
        photo_data_url: newProfile.photoDataUrl,
        quote: newProfile.quote || null,
      }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail ?? 'Could not save this profile.');
    }
    // Never keep the plaintext password in app state past this call — it
    // only ever existed to make this one request.
    const { password: _password, ...profileWithoutPassword } = newProfile;
    setProfile(profileWithoutPassword);
    persistSession(profileWithoutPassword.email);
    setScreen('welcome');
  };

  const handleWelcomeContinue = () => setScreen('app');

  const handleStartWithSuggestion = (suggestion: string) => {
    setTalkDraft(suggestion);
    setView('talk');
    setScreen('app');
  };

  const handleSkip = () => {
    setProfile({
      fullName: '',
      email: '',
      dob: '',
      location: '',
      interests: [],
      otherInterests: '',
      photoDataUrl: null,
      quote: '',
    });
    setScreen('app');
  };

  // Brain 2's profile proposals — drafted in conversation or by the nightly
  // reflection — waiting on her to accept or not.
  const [pendingProposals, setPendingProposals] = useState<any[]>([]);
  const [proposalBusyId, setProposalBusyId] = useState<string | null>(null);

  const loadPendingProposals = useCallback(async () => {
    if (!profile?.email) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/brain2/pending?profile_email=${encodeURIComponent(profile.email)}`);
      if (res.ok) setPendingProposals(await res.json());
    } catch {
      // Quiet fail — the cards reload next time Today is opened.
    }
  }, [profile?.email]);

  const decideProposal = async (proposalId: string, accept: boolean) => {
    if (!profile?.email) return;
    setProposalBusyId(proposalId);
    try {
      const res = await fetch(`${API_BASE}/api/v1/brain2/profile/proposals/${proposalId}/${accept ? 'accept' : 'reject'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_email: profile.email }),
      });
      if (res.ok) setPendingProposals((prev) => prev.filter((p) => p.profile_entry_id !== proposalId));
    } finally {
      setProposalBusyId(null);
    }
  };

  // Facts and patterns Brain 1 noticed but she hasn't confirmed — never used
  // as true until she says so. Private (T3) ones are handled by consent in Me.
  const [pendingMemories, setPendingMemories] = useState<any[]>([]);
  const [memoryBusyId, setMemoryBusyId] = useState<string | null>(null);

  const loadPendingMemories = useCallback(async () => {
    if (!profile?.email) return;
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/memories?profile_email=${encodeURIComponent(profile.email)}&status=requires_confirmation`,
      );
      if (res.ok) setPendingMemories((await res.json()).filter((m: any) => m.sensitivity_tier !== 'T3'));
    } catch {
      // Quiet fail — same as proposals.
    }
  }, [profile?.email]);

  useEffect(() => {
    if (view !== 'today') return;
    loadPendingProposals();
    loadPendingMemories();
  }, [view, loadPendingProposals, loadPendingMemories]);

  const decideMemory = async (memoryId: string, confirm: boolean) => {
    if (!profile?.email) return;
    setMemoryBusyId(memoryId);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/memories/${memoryId}/${confirm ? 'confirm' : 'suppress'}?profile_email=${encodeURIComponent(profile.email)}`,
        { method: 'PATCH' },
      );
      if (res.ok) setPendingMemories((prev) => prev.filter((m) => m.memory_id !== memoryId));
    } finally {
      setMemoryBusyId(null);
    }
  };

  if (screen === 'checking-session') {
    return <div className="app-shell" />;
  }

  if (screen === 'login') {
    return (
      <div className="app-shell">
        <Login onLoggedIn={handleLoggedIn} onNewProfile={handleNewProfile} />
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="app-shell">
        <Onboarding
          initialEmail={pendingEmail}
          initialPassword={pendingPassword}
          onComplete={handleOnboardingComplete}
          onSkip={handleSkip}
        />
      </div>
    );
  }

  if (screen === 'welcome') {
    return (
      <div className="app-shell">
        <Welcome profile={profile} onContinue={handleWelcomeContinue} onStartWithSuggestion={handleStartWithSuggestion} />
      </div>
    );
  }

  const nothingWaiting = pendingProposals.length === 0 && pendingMemories.length === 0;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="greeting">
            {greeting()}
            {profile.fullName ? `, ${profile.fullName.split(' ')[0]}` : ''} 👋
          </p>
          <p className="greeting-sub">Your second brain is listening</p>
        </div>
        <div className="avatar">
          {profile.photoDataUrl ? (
            <img src={profile.photoDataUrl} alt="" className="avatar-photo" />
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="8" r="3.6" fill="#1b4b3a" />
              <path d="M4.5 20c1.2-4 4-6 7.5-6s6.3 2 7.5 6" stroke="#1b4b3a" strokeWidth="1.8" strokeLinecap="round" fill="none" />
            </svg>
          )}
        </div>
      </header>

      <div className="segmented view-switch" role="tablist" aria-label="View">
        {(['today', 'talk', 'me'] as const).map((v) => (
          <button key={v} type="button" role="tab" aria-selected={view === v} className={view === v ? 'segment selected' : 'segment'} onClick={() => setView(v)}>
            {v === 'today' ? 'Today' : v === 'talk' ? 'Talk' : 'Me'}
          </button>
        ))}
      </div>

      <main className="app-content">
        {view === 'talk' && <BrainChat apiBase={API_BASE} email={profile.email} initialDraft={talkDraft} />}
        {view === 'me' && <MirrorView apiBase={API_BASE} email={profile.email} />}
        {view === 'today' && (
          <motion.section className="today" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }}>
            <motion.div className="prompt-bar" onClick={() => setView('talk')} whileTap={{ scale: 0.98 }}>
              <span className="prompt-pill">What&apos;s on your mind? Talk to Brain 2</span>
            </motion.div>

            <AnimatePresence>
              {pendingProposals.map((proposal) => (
                <motion.div
                  key={proposal.profile_entry_id}
                  className="proposal-card"
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, height: 0, marginBottom: 0, paddingTop: 0, paddingBottom: 0 }}
                  transition={{ duration: 0.25 }}
                >
                  <span className="proposal-label">I&apos;ve learned something &middot; {proposal.domain}</span>
                  <p className="proposal-content">{proposal.content}</p>
                  <div className="proposal-actions">
                    <button type="button" className="proposal-accept" disabled={proposalBusyId === proposal.profile_entry_id}
                      onClick={() => decideProposal(proposal.profile_entry_id, true)}>
                      Yes, save it
                    </button>
                    <button type="button" className="proposal-reject" disabled={proposalBusyId === proposal.profile_entry_id}
                      onClick={() => decideProposal(proposal.profile_entry_id, false)}>
                      Not quite
                    </button>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            <AnimatePresence>
              {pendingMemories.map((memory) => (
                <motion.div
                  key={memory.memory_id}
                  className="proposal-card"
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, height: 0, marginBottom: 0, paddingTop: 0, paddingBottom: 0 }}
                  transition={{ duration: 0.25 }}
                >
                  <span className="proposal-label">
                    {memory.source_type === 'pattern' ? 'A pattern Brain 1 noticed' : 'Brain 1 noticed'}
                    {memory.domain ? ` · ${memory.domain}` : ''}
                  </span>
                  <p className="proposal-content">{memory.content}</p>
                  <div className="proposal-actions">
                    <button type="button" className="proposal-accept" disabled={memoryBusyId === memory.memory_id}
                      onClick={() => decideMemory(memory.memory_id, true)}>
                      That&apos;s right
                    </button>
                    <button type="button" className="proposal-reject" disabled={memoryBusyId === memory.memory_id}
                      onClick={() => decideMemory(memory.memory_id, false)}>
                      Not this
                    </button>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            {nothingWaiting && (
              <div className="empty-state">
                <p className="empty-title">Nothing waiting for you</p>
                <p className="hint">Things Brain 2 learns or notices about you will show up here for your yes or no.</p>
              </div>
            )}
          </motion.section>
        )}
      </main>
    </div>
  );
}
