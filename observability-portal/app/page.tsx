'use client';

import { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion, useDragControls } from 'framer-motion';

const API_BASE = 'http://localhost:8000';

const MOODS = [
  { key: 'good', label: '😊 Good' },
  { key: 'calm', label: '😌 Calm' },
  { key: 'okay', label: '😐 Okay' },
  { key: 'low', label: '😔 Low' },
  { key: 'frustrated', label: '😤 Frustrated' },
  { key: 'excited', label: '🤩 Excited' },
];

type Source = 'text' | 'voice' | 'photo';
type Tab = 'today' | 'evolution';

type Moment = {
  id: string;
  created_at: string;
  source: string;
  content: string;
  mood: string | null;
  photo_data_url: string | null;
  reflection: string | null;
};

type EvolutionStats = {
  range_days: number;
  total_moments_all_time: number;
  moments_in_range: number;
  moments_today: number;
  mood_counts_in_range: Record<string, number>;
  has_history_before_range: boolean;
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

function moodLabel(mood: string | null): string {
  const found = MOODS.find((m) => m.key === mood);
  return found ? found.label : mood ? mood : '';
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

function HomeIcon({ active }: { active: boolean }) {
  return active ? (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
      <path d="M3.5 11.5 12 4l8.5 7.5" stroke="#1d8cf0" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <path d="M5.5 10.5V20h13v-9.5" fill="#1d8cf0" stroke="#1d8cf0" strokeWidth="2" strokeLinejoin="round" />
      <rect x="10" y="14" width="4" height="6" fill="#ffffff" />
    </svg>
  ) : (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
      <path
        d="M3.5 11.5 12 4l8.5 7.5M5.5 10.5V20h13v-9.5"
        stroke="#8a8d91"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect x="10" y="14" width="4" height="6" stroke="#8a8d91" strokeWidth="1.8" />
    </svg>
  );
}

function ChartIcon({ active }: { active: boolean }) {
  const color = active ? '#1d8cf0' : '#8a8d91';
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
      {active ? (
        <>
          <rect x="4" y="12" width="4" height="8" rx="1" fill={color} />
          <rect x="10" y="8" width="4" height="12" rx="1" fill={color} />
          <rect x="16" y="4" width="4" height="16" rx="1" fill={color} />
        </>
      ) : (
        <>
          <rect x="4" y="12" width="4" height="8" rx="1" stroke={color} strokeWidth="1.8" />
          <rect x="10" y="8" width="4" height="12" rx="1" stroke={color} strokeWidth="1.8" />
          <rect x="16" y="4" width="4" height="16" rx="1" stroke={color} strokeWidth="1.8" />
        </>
      )}
    </svg>
  );
}

export default function HomePage() {
  const [tab, setTab] = useState<Tab>('today');
  const [composerOpen, setComposerOpen] = useState(false);
  const dragControls = useDragControls();

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

  const [evolutionDays, setEvolutionDays] = useState(30);
  const [stats, setStats] = useState<EvolutionStats | null>(null);
  const [narrative, setNarrative] = useState<string | null>(null);
  const [narrativeLoading, setNarrativeLoading] = useState(false);

  const loadMoments = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/moments`);
      if (res.ok) setMoments(await res.json());
    } catch {
      // Quiet fail here — errors surface when the person tries to save/reflect instead.
    }
  }, []);

  useEffect(() => {
    loadMoments();
  }, [loadMoments]);

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

  const loadEvolution = useCallback(async (days: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/evolution?days=${days}`);
      if (res.ok) setStats(await res.json());
    } catch {
      setStats(null);
    }
  }, []);

  useEffect(() => {
    if (tab === 'evolution') {
      setNarrative(null);
      loadEvolution(evolutionDays);
    }
  }, [tab, evolutionDays, loadEvolution]);

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
    if (!content.trim() && !photoDataUrl) return;
    setSaving(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/moments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
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

      setReflectingId(saved.id);
      try {
        const reflectRes = await fetch(`${API_BASE}/api/v1/moments/${saved.id}/reflect`, { method: 'POST' });
        const reflectData = await reflectRes.json();
        if (reflectRes.ok) {
          setMoments((prev) => prev.map((m) => (m.id === saved.id ? { ...m, reflection: reflectData.reflection } : m)));
        }
      } finally {
        setReflectingId(null);
      }
    } catch {
      setError('Could not reach the service. Is it running?');
    } finally {
      setSaving(false);
    }
  };

  const handleReflect = async (momentId: string) => {
    setReflectingId(momentId);
    try {
      const res = await fetch(`${API_BASE}/api/v1/moments/${momentId}/reflect`, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        setMoments((prev) => prev.map((m) => (m.id === momentId ? { ...m, reflection: data.reflection } : m)));
      }
    } finally {
      setReflectingId(null);
    }
  };

  const handleNarrative = async () => {
    setNarrativeLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/evolution/narrative?days=${evolutionDays}`);
      const data = await res.json();
      if (res.ok) setNarrative(data.narrative);
    } finally {
      setNarrativeLoading(false);
    }
  };

  const streak = useMemo(() => computeStreak(moments), [moments]);
  const hasToday = useMemo(
    () => moments.some((m) => new Date(m.created_at).toDateString() === new Date().toDateString()),
    [moments],
  );

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="brand">me</span>
        <AnimatePresence>
          {streak > 0 && (
            <motion.div
              className="streak-badge"
              title={`${streak}-day streak`}
              initial={{ scale: 0, rotate: -20 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ type: 'spring', stiffness: 400, damping: 14 }}
            >
              <span className="streak-flame">🔥</span>
              <span>{streak}</span>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      <main className="app-content">
        <AnimatePresence mode="wait">
          {tab === 'today' ? (
            <motion.section
              key="today"
              className="today"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
            >
              <motion.div className="prompt-bar" onClick={openComposer} whileTap={{ scale: 0.98 }}>
                <p className="prompt-greeting">Hi you</p>
                <div className="prompt-pill">
                  <span>What&apos;s your thoughts</span>
                </div>
              </motion.div>

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
                        {moment.mood && <span className="mood-pill">{moodLabel(moment.mood)}</span>}
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
          ) : (
            <motion.section
              key="evolution"
              className="evolution"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
            >
              <h1>How you&apos;ve changed</h1>

              <div className="range-row">
                {[7, 30, 90, 365].map((d) => (
                  <motion.button
                    key={d}
                    type="button"
                    whileTap={{ scale: 0.94 }}
                    className={evolutionDays === d ? 'range-chip selected' : 'range-chip'}
                    onClick={() => setEvolutionDays(d)}
                  >
                    {d === 7 ? 'Week' : d === 30 ? 'Month' : d === 90 ? '3 months' : 'Year'}
                  </motion.button>
                ))}
              </div>

              {stats ? (
                <>
                  <div className="stat-row">
                    <div className="stat">
                      <strong>{stats.moments_in_range}</strong>
                      <span>captured</span>
                    </div>
                    <div className="stat-divider" />
                    <div className="stat">
                      <strong>{stats.moments_today}</strong>
                      <span>today</span>
                    </div>
                    <div className="stat-divider" />
                    <div className="stat">
                      <strong>{stats.total_moments_all_time}</strong>
                      <span>all time</span>
                    </div>
                  </div>

                  <div className="mood-breakdown">
                    {Object.entries(stats.mood_counts_in_range).length === 0 && (
                      <p className="empty-body center">No moods logged in this range yet.</p>
                    )}
                    {Object.entries(stats.mood_counts_in_range).map(([mood, count]) => (
                      <div key={mood} className="mood-bar-row">
                        <span className="mood-bar-label">{moodLabel(mood) || mood}</span>
                        <div className="mood-bar-track">
                          <motion.div
                            className="mood-bar-fill"
                            initial={{ width: 0 }}
                            animate={{ width: `${Math.min(100, (count / stats.moments_in_range) * 100)}%` }}
                            transition={{ duration: 0.4, ease: 'easeOut' }}
                          />
                        </div>
                        <span className="mood-bar-count">{count}</span>
                      </div>
                    ))}
                  </div>

                  <motion.button
                    type="button"
                    className="narrative-btn"
                    whileTap={{ scale: 0.97 }}
                    onClick={handleNarrative}
                    disabled={narrativeLoading}
                  >
                    {narrativeLoading ? 'Thinking about it…' : "Show me how I've changed"}
                  </motion.button>

                  <AnimatePresence>
                    {narrative && (
                      <motion.div
                        className="narrative-card"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3 }}
                      >
                        <p>{narrative}</p>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {!stats.has_history_before_range && (
                    <p className="hint center">This is as far back as your history goes — keep capturing moments and this view will get richer.</p>
                  )}
                </>
              ) : (
                <p className="empty-body center">Not enough here yet — save a few moments first.</p>
              )}
            </motion.section>
          )}
        </AnimatePresence>
      </main>

      <AnimatePresence>
        {tab === 'today' && !composerOpen && (
          <motion.button
            type="button"
            className="fab"
            aria-label="Capture a moment"
            onClick={openComposer}
            initial={{ scale: 0, rotate: -45 }}
            animate={{ scale: 1, rotate: 0 }}
            exit={{ scale: 0, rotate: 45 }}
            whileTap={{ scale: 0.88 }}
            transition={{ type: 'spring', stiffness: 400, damping: 20 }}
          >
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
              <path d="M12 5v14M5 12h14" stroke="#ffffff" strokeWidth="2.4" strokeLinecap="round" />
            </svg>
          </motion.button>
        )}
      </AnimatePresence>

      <nav className="tab-bar">
        <button type="button" aria-label="Today" className={tab === 'today' ? 'tab-bar-item active' : 'tab-bar-item'} onClick={() => setTab('today')}>
          <HomeIcon active={tab === 'today'} />
        </button>
        <button type="button" aria-label="Evolution" className={tab === 'evolution' ? 'tab-bar-item active' : 'tab-bar-item'} onClick={() => setTab('evolution')}>
          <ChartIcon active={tab === 'evolution'} />
        </button>
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
              <button type="button" className="composer-cancel" onClick={closeComposer} disabled={saving}>
                Cancel
              </button>
              <span className="composer-title">New moment</span>
              <button
                type="button"
                className="composer-save"
                disabled={saving || (!content.trim() && !photoDataUrl)}
                onClick={handleSave}
              >
                {saving ? 'Saving…' : 'Save'}
              </button>
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
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
