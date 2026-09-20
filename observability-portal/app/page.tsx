'use client';

import { ChangeEvent, useCallback, useEffect, useRef, useState } from 'react';

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
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function moodLabel(mood: string | null): string {
  const found = MOODS.find((m) => m.key === mood);
  return found ? found.label : mood ? mood : '';
}

export default function HomePage() {
  const [tab, setTab] = useState<'today' | 'evolution'>('today');

  const [moments, setMoments] = useState<Moment[]>([]);
  const [selectedMood, setSelectedMood] = useState<string | null>(null);
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
    setSelectedMood(null);
    setPhotoDataUrl(null);
    setSource('text');
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
          mood: selectedMood,
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
      resetForm();

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

  const today = new Date();
  const dateLabel = today.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });

  return (
    <main className="shell">
      <header className="top">
        <span className="brand">me</span>
        <nav className="tabs">
          <button className={tab === 'today' ? 'tab active' : 'tab'} onClick={() => setTab('today')}>Today</button>
          <button className={tab === 'evolution' ? 'tab active' : 'tab'} onClick={() => setTab('evolution')}>My Evolution</button>
        </nav>
      </header>

      {tab === 'today' && (
        <section className="today">
          <div className="composer">
            <p className="date-label">{dateLabel}</p>
            <h1>How are you, right now?</h1>

            <div className="mood-row">
              {MOODS.map((mood) => (
                <button
                  key={mood.key}
                  type="button"
                  className={selectedMood === mood.key ? 'mood-chip selected' : 'mood-chip'}
                  onClick={() => setSelectedMood(mood.key === selectedMood ? null : mood.key)}
                >
                  {mood.label}
                </button>
              ))}
            </div>

            <div className="source-row">
              <button type="button" className={source === 'text' ? 'source-chip selected' : 'source-chip'} onClick={() => setSource('text')}>✍️ Text</button>
              <button type="button" className={source === 'voice' ? 'source-chip selected' : 'source-chip'} onClick={() => setSource('voice')}>🎙️ Voice</button>
              <button type="button" className={source === 'photo' ? 'source-chip selected' : 'source-chip'} onClick={() => setSource('photo')}>📷 Photo</button>
            </div>

            <textarea
              rows={5}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="What happened, what did you think, how did you react..."
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
                <input type="file" accept="image/*" onChange={handlePhotoChange} />
                {photoDataUrl && <img src={photoDataUrl} alt="attached" className="photo-preview" />}
              </div>
            )}

            {error && <p className="error-text">{error}</p>}

            <button type="button" className="save-btn" disabled={saving} onClick={handleSave}>
              {saving ? 'Saving...' : 'Save this moment'}
            </button>
          </div>

          <div className="feed">
            {moments.length === 0 && (
              <p className="empty">Nothing here yet. The first moment you save starts your story.</p>
            )}
            {moments.map((moment) => (
              <article key={moment.id} className="moment-card">
                <div className="moment-top">
                  <span className="moment-mood">{moodLabel(moment.mood)}</span>
                  <span className="moment-time">{timeAgo(moment.created_at)}</span>
                </div>
                {moment.photo_data_url && <img src={moment.photo_data_url} alt="" className="moment-photo" />}
                <p className="moment-content">{moment.content}</p>

                {moment.reflection ? (
                  <div className="reflection">
                    <span className="reflection-label">reflection</span>
                    <p>{moment.reflection}</p>
                  </div>
                ) : reflectingId === moment.id ? (
                  <p className="reflecting">reflecting…</p>
                ) : (
                  <button type="button" className="reflect-btn" onClick={() => handleReflect(moment.id)}>
                    Reflect on this
                  </button>
                )}
              </article>
            ))}
          </div>
        </section>
      )}

      {tab === 'evolution' && (
        <section className="evolution">
          <h1>How you&apos;ve changed</h1>
          <div className="range-row">
            {[7, 30, 90, 365].map((d) => (
              <button key={d} type="button" className={evolutionDays === d ? 'range-chip selected' : 'range-chip'} onClick={() => setEvolutionDays(d)}>
                {d === 7 ? 'Past week' : d === 30 ? 'Past month' : d === 90 ? 'Past 3 months' : 'Past year'}
              </button>
            ))}
          </div>

          {stats ? (
            <>
              <div className="stat-row">
                <div className="stat">
                  <strong>{stats.moments_in_range}</strong>
                  <span>moments captured</span>
                </div>
                <div className="stat">
                  <strong>{stats.moments_today}</strong>
                  <span>today</span>
                </div>
                <div className="stat">
                  <strong>{stats.total_moments_all_time}</strong>
                  <span>all time</span>
                </div>
              </div>

              <div className="mood-breakdown">
                {Object.entries(stats.mood_counts_in_range).length === 0 && (
                  <p className="empty">No moods logged in this range yet.</p>
                )}
                {Object.entries(stats.mood_counts_in_range).map(([mood, count]) => (
                  <div key={mood} className="mood-bar-row">
                    <span className="mood-bar-label">{moodLabel(mood) || mood}</span>
                    <div className="mood-bar-track">
                      <div className="mood-bar-fill" style={{ width: `${Math.min(100, (count / stats.moments_in_range) * 100)}%` }} />
                    </div>
                    <span className="mood-bar-count">{count}</span>
                  </div>
                ))}
              </div>

              <button type="button" className="narrative-btn" onClick={handleNarrative} disabled={narrativeLoading}>
                {narrativeLoading ? 'Thinking about it...' : 'Show me how I\'ve changed'}
              </button>

              {narrative && <p className="narrative-text">{narrative}</p>}

              {!stats.has_history_before_range && (
                <p className="hint">This is as far back as your history goes — keep capturing moments and this view will get richer.</p>
              )}
            </>
          ) : (
            <p className="empty">Not enough here yet — save a few moments first.</p>
          )}
        </section>
      )}
    </main>
  );
}
