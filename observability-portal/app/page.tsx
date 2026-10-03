'use client';

import { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion, useDragControls } from 'framer-motion';
import Login from './login';
import Onboarding, { Profile } from './onboarding';
import Welcome from './welcome';

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

const MOODS = [
  { key: 'good', label: '😊 Good' },
  { key: 'calm', label: '😌 Calm' },
  { key: 'okay', label: '😐 Okay' },
  { key: 'low', label: '😔 Low' },
  { key: 'frustrated', label: '😤 Frustrated' },
  { key: 'excited', label: '🤩 Excited' },
];

type Source = 'text' | 'voice' | 'photo';

type Moment = {
  id: string;
  created_at: string;
  source: string;
  content: string;
  mood: string | null;
  photo_data_url: string | null;
  reflection: string | null;
};

function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  const diffMs = Date.now() - then;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

function greeting(): string {
  const h = new Date().getHours();
  if (h < 5) return 'Still up';
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
}

// Consecutive calendar days (ending at the most recent entry) with at least
// one moment — the same "don't break the chain" mechanic Duolingo/Snapchat
// use, because a streak makes skipping a day feel like a loss, not just a
// missed gain.
function computeStreak(moments: Moment[]): number {
  if (moments.length === 0) return 0;
  const dayKeys = Array.from(new Set(moments.map((m) => new Date(m.created_at).toDateString())));
  const days = dayKeys.map((d) => new Date(d).getTime()).sort((a, b) => b - a);
  let streak = 1;
  for (let i = 1; i < days.length; i += 1) {
    const diffDays = Math.round((days[i - 1] - days[i]) / 86_400_000);
    if (diffDays === 1) streak += 1;
    else break;
  }
  return streak;
}

const SOURCE_META: Record<Source, { icon: string; label: string }> = {
  text: { icon: '✍️', label: 'text' },
  voice: { icon: '🎙️', label: 'voice' },
  photo: { icon: '📷', label: 'photo' },
};

export default function HomePage() {
  const [composerOpen, setComposerOpen] = useState(false);
  const dragControls = useDragControls();

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
    setContent(suggestion);
    setComposerOpen(true);
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

  const [moments, setMoments] = useState<Moment[]>([]);
  const [source, setSource] = useState<Source>('text');
  const [content, setContent] = useState('');
  const [photoDataUrl, setPhotoDataUrl] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [reflectingId, setReflectingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [isRecording, setIsRecording] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  const recognitionRef = useRef<any>(null);

  const loadMoments = useCallback(async () => {
    if (!profile?.email) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/moments?profile_email=${encodeURIComponent(profile.email)}`);
      if (res.ok) setMoments(await res.json());
    } catch {
      // Quiet fail here — errors surface when the person tries to save/reflect instead.
    }
  }, [profile?.email]);

  useEffect(() => {
    loadMoments();
  }, [loadMoments]);

  // Brain 2's Profile proposals (drafted by Broca, sometimes by the
  // Scheduler with no input from you at all) — everything it's drafted and
  // is waiting on you to accept, refine, or reject. Previously invisible:
  // real work Brain 2 was doing into a void.
  const [pendingProposals, setPendingProposals] = useState<any[]>([]);
  const [proposalBusyId, setProposalBusyId] = useState<string | null>(null);

  const loadPendingProposals = useCallback(async () => {
    if (!profile?.email) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/brain2/pending?profile_email=${encodeURIComponent(profile.email)}`);
      if (res.ok) setPendingProposals(await res.json());
    } catch {
      // Quiet fail — Brain 2's proposals are a bonus surface, never block the journal.
    }
  }, [profile?.email]);

  useEffect(() => {
    loadPendingProposals();
  }, [loadPendingProposals]);

  const acceptProposal = async (proposalId: string) => {
    if (!profile?.email) return;
    setProposalBusyId(proposalId);
    try {
      const res = await fetch(`${API_BASE}/api/v1/brain2/profile/proposals/${proposalId}/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_email: profile.email }),
      });
      if (res.ok) setPendingProposals((prev) => prev.filter((p) => p.profile_entry_id !== proposalId));
    } finally {
      setProposalBusyId(null);
    }
  };

  const rejectProposal = async (proposalId: string) => {
    if (!profile?.email) return;
    setProposalBusyId(proposalId);
    try {
      const res = await fetch(`${API_BASE}/api/v1/brain2/profile/proposals/${proposalId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_email: profile.email }),
      });
      if (res.ok) setPendingProposals((prev) => prev.filter((p) => p.profile_entry_id !== proposalId));
    } finally {
      setProposalBusyId(null);
    }
  };

  // Hippocampus's candidate memories sitting at requires_confirmation —
  // proposed, not yet durable, until you say which ones are actually true.
  const [pendingMemories, setPendingMemories] = useState<any[]>([]);
  const [memoryBusyId, setMemoryBusyId] = useState<string | null>(null);

  const loadPendingMemories = useCallback(async () => {
    if (!profile?.email) return;
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/memories?profile_email=${encodeURIComponent(profile.email)}&status=requires_confirmation`,
      );
      if (res.ok) setPendingMemories(await res.json());
    } catch {
      // Quiet fail — same bonus-surface contract as proposals.
    }
  }, [profile?.email]);

  useEffect(() => {
    loadPendingMemories();
  }, [loadPendingMemories]);

  const confirmMemory = async (memoryId: string) => {
    if (!profile?.email) return;
    setMemoryBusyId(memoryId);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/memories/${memoryId}/confirm?profile_email=${encodeURIComponent(profile.email)}`,
        { method: 'PATCH' },
      );
      if (res.ok) setPendingMemories((prev) => prev.filter((m) => m.memory_id !== memoryId));
    } finally {
      setMemoryBusyId(null);
    }
  };

  const suppressMemory = async (memoryId: string) => {
    if (!profile?.email) return;
    setMemoryBusyId(memoryId);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/memories/${memoryId}/suppress?profile_email=${encodeURIComponent(profile.email)}`,
        { method: 'PATCH' },
      );
      if (res.ok) setPendingMemories((prev) => prev.filter((m) => m.memory_id !== memoryId));
    } finally {
      setMemoryBusyId(null);
    }
  };

  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSpeechSupported(false);
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = 'en-US';
    recognition.onresult = (event: any) => {
      let transcript = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        transcript += event.results[i][0].transcript;
      }
      setContent((prev) => (prev ? `${prev} ${transcript}` : transcript));
    };
    recognition.onend = () => setIsRecording(false);
    recognitionRef.current = recognition;
  }, []);

  const toggleRecording = () => {
    if (!recognitionRef.current) return;
    if (isRecording) {
      recognitionRef.current.stop();
      setIsRecording(false);
    } else {
      recognitionRef.current.start();
      setIsRecording(true);
    }
  };

  const handlePhotoChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setPhotoDataUrl(reader.result as string);
    reader.readAsDataURL(file);
  };

  const resetForm = () => {
    setContent('');
    setPhotoDataUrl(null);
    setSource('text');
  };

  const openComposer = () => {
    setError(null);
    setComposerOpen(true);
  };

  const closeComposer = () => {
    if (isRecording) toggleRecording();
    setComposerOpen(false);
    resetForm();
    setError(null);
  };

  const handleSave = async () => {
    if (!profile?.email) return;
    if (!content.trim() && !photoDataUrl) return;
    setSaving(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/moments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile_email: profile.email,
          source,
          content: content.trim() || '(photo only)',
          mood: null,
          photo_data_url: photoDataUrl,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail ?? 'Could not save this moment.');
        return;
      }

      const saved: Moment = data;
      setMoments((prev) => [saved, ...prev]);
      if (isRecording) toggleRecording();
      resetForm();
      setComposerOpen(false);

      // A moment that already came back with a reflection keeps it as-is;
      // only the ordinary case (no reflection yet) reflects here.
      if (!saved.reflection) {
        setReflectingId(saved.id);
        try {
          const reflectRes = await fetch(
            `${API_BASE}/api/v1/moments/${saved.id}/reflect?profile_email=${encodeURIComponent(profile.email)}`,
            { method: 'POST' },
          );
          const reflectData = await reflectRes.json();
          if (reflectRes.ok) {
            setMoments((prev) => prev.map((m) => (m.id === saved.id ? { ...m, reflection: reflectData.reflection } : m)));
          }
        } finally {
          setReflectingId(null);
        }
      }
    } catch {
      setError('Could not reach the service. Is it running?');
    } finally {
      setSaving(false);
    }
  };

  const handleReflect = async (momentId: string) => {
    if (!profile?.email) return;
    setReflectingId(momentId);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/moments/${momentId}/reflect?profile_email=${encodeURIComponent(profile.email)}`,
        { method: 'POST' },
      );
      const data = await res.json();
      if (res.ok) {
        setMoments((prev) => prev.map((m) => (m.id === momentId ? { ...m, reflection: data.reflection } : m)));
      }
    } finally {
      setReflectingId(null);
    }
  };

  const streak = useMemo(() => computeStreak(moments), [moments]);
  const hasToday = useMemo(
    () => moments.some((m) => new Date(m.created_at).toDateString() === new Date().toDateString()),
    [moments],
  );

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

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="greeting">
            {greeting()}
            {profile.fullName ? `, ${profile.fullName.split(' ')[0]}` : ''} 👋
          </p>
          <p className="greeting-sub">{hasToday ? 'Logged today' : 'Nothing logged yet today'}</p>
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
          <AnimatePresence>
            {streak > 0 && (
              <motion.div
                className="streak-badge"
                title={`${streak}-day streak`}
                initial={{ scale: 0, rotate: -20 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ type: 'spring', stiffness: 400, damping: 14 }}
              >
                <span>🔥{streak}</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </header>

      <main className="app-content">
        <motion.section
          className="today"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18 }}
        >
          <motion.div className="prompt-bar" onClick={openComposer} whileTap={{ scale: 0.98 }}>
            <span className="prompt-pill">What&apos;s your thoughts?</span>
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
                <span className="proposal-label">Brain 2 &middot; {proposal.domain}</span>
                <p className="proposal-content">{proposal.content}</p>
                <div className="proposal-actions">
                  <button
                    type="button"
                    className="proposal-accept"
                    disabled={proposalBusyId === proposal.profile_entry_id}
                    onClick={() => acceptProposal(proposal.profile_entry_id)}
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    className="proposal-reject"
                    disabled={proposalBusyId === proposal.profile_entry_id}
                    onClick={() => rejectProposal(proposal.profile_entry_id)}
                  >
                    Not now
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
                  Brain 2 noticed &middot; {memory.domain || memory.type}
                </span>
                <p className="proposal-content">{memory.content}</p>
                <div className="proposal-actions">
                  <button
                    type="button"
                    className="proposal-accept"
                    disabled={memoryBusyId === memory.memory_id}
                    onClick={() => confirmMemory(memory.memory_id)}
                  >
                    That&apos;s right
                  </button>
                  <button
                    type="button"
                    className="proposal-reject"
                    disabled={memoryBusyId === memory.memory_id}
                    onClick={() => suppressMemory(memory.memory_id)}
                  >
                    Not this
                  </button>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {moments.length === 0 ? (
            <div className="empty-state">
              <p className="empty-title">Nothing here yet</p>
            </div>
          ) : (
            <div className="feed">
              {moments.map((moment, index) => (
                <motion.article
                  key={moment.id}
                  className="moment-card"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, delay: Math.min(index, 6) * 0.04 }}
                >
                  <div className="moment-top">
                    <span className={`source-badge ${moment.source}`}>
                      {SOURCE_META[moment.source as Source]?.icon ?? '✍️'}
                    </span>
                    <span className="entry-label entry-label-brain1">Brain 1</span>
                    <span className="moment-time">{timeAgo(moment.created_at)}</span>
                  </div>
                  {moment.photo_data_url && <img src={moment.photo_data_url} alt="" className="moment-photo" />}
                  <p className="moment-content">{moment.content}</p>

                  {moment.reflection ? (
                    <motion.div
                      className="reflection-bubble"
                      initial={{ opacity: 0, scale: 0.96 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ type: 'spring', stiffness: 300, damping: 24 }}
                    >
                      <span className="proposal-label">Brain 2</span>
                      <p>{moment.reflection}</p>
                    </motion.div>
                  ) : reflectingId === moment.id ? (
                    <p className="reflecting">
                      <span className="dot-pulse" />
                      reflecting…
                    </p>
                  ) : (
                    <motion.button
                      type="button"
                      className="reflect-btn"
                      whileTap={{ scale: 0.94 }}
                      onClick={() => handleReflect(moment.id)}
                    >
                      Reflect on this
                    </motion.button>
                  )}
                </motion.article>
              ))}
            </div>
          )}
        </motion.section>
      </main>

      <nav className="tab-bar">
        <motion.button
          type="button"
          className="fab"
          aria-label="Capture a moment"
          onClick={openComposer}
          whileTap={{ scale: 0.88 }}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M12 5v14M5 12h14" stroke="#ffffff" strokeWidth="2.4" strokeLinecap="round" />
          </svg>
        </motion.button>
      </nav>

      <AnimatePresence>
        {composerOpen && (
          <motion.div
            className="composer-sheet"
            role="dialog"
            aria-modal="true"
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 32, stiffness: 320 }}
            drag="y"
            dragControls={dragControls}
            dragListener={false}
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.5 }}
            onDragEnd={(_, info) => {
              if (info.offset.y > 120 || info.velocity.y > 500) closeComposer();
            }}
          >
            <div className="sheet-grabber-row" onPointerDown={(event) => dragControls.start(event)}>
              <div className="sheet-grabber" />
            </div>

            <header className="composer-header">
              <button type="button" className="composer-back" aria-label="Close" onClick={closeComposer} disabled={saving}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path d="M15 5 8 12l7 7" stroke="#23271f" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              <span className="composer-title">New moment</span>
            </header>

            <div className="composer-body">
              <div className="segmented">
                <button type="button" className={source === 'text' ? 'segment selected' : 'segment'} onClick={() => setSource('text')}>Text</button>
                <button type="button" className={source === 'voice' ? 'segment selected' : 'segment'} onClick={() => setSource('voice')}>Voice</button>
                <button type="button" className={source === 'photo' ? 'segment selected' : 'segment'} onClick={() => setSource('photo')}>Photo</button>
              </div>

              <textarea
                autoFocus
                rows={5}
                value={content}
                onChange={(event) => setContent(event.target.value)}
                placeholder="What's your thoughts"
              />

              {source === 'voice' && (
                <div className="voice-row">
                  {speechSupported ? (
                    <button type="button" className={isRecording ? 'record-btn recording' : 'record-btn'} onClick={toggleRecording}>
                      {isRecording ? '● Stop recording' : '🎙️ Start speaking'}
                    </button>
                  ) : (
                    <p className="hint">Voice capture needs a browser with speech recognition (Chrome works). Type instead for now.</p>
                  )}
                </div>
              )}

              {source === 'photo' && (
                <div className="photo-row">
                  <input type="file" accept="image/*" capture="environment" onChange={handlePhotoChange} />
                  {photoDataUrl && <img src={photoDataUrl} alt="attached" className="photo-preview" />}
                </div>
              )}

              {error && <p className="error-text">{error}</p>}
            </div>

            <div className="composer-footer">
              <motion.button
                type="button"
                className="composer-save"
                whileTap={{ scale: 0.97 }}
                disabled={saving || (!content.trim() && !photoDataUrl)}
                onClick={handleSave}
              >
                {saving ? 'Saving…' : 'Save'}
              </motion.button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
