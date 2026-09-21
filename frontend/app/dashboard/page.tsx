'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState } from 'react';

type EntryItem = {
  id: string;
  mood_emoji: string;
  mood_label: string;
  content: string;
  created_at: string;
  reflection?: string | null;
};

type BeliefItem = {
  topic: string;
  status: string;
  confidence: number;
  summary: string;
};

type Tab = 'today' | 'evolution';

const MOOD_OPTIONS = [
  { emoji: '\u{1F60A}', label: 'Good' },
  { emoji: '\u{1F60C}', label: 'Calm' },
  { emoji: '\u{1F624}', label: 'Frustrated' },
  { emoji: '\u{1F614}', label: 'Low' },
  { emoji: '\u{1F914}', label: 'Reflective' },
];

function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const diffMs = Date.now() - then;
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

function formatHeaderDate(): string {
  return new Date()
    .toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
    .toUpperCase();
}

function CalendarIcon({ active }: { active: boolean }) {
  const color = active ? 'var(--today-accent)' : 'var(--today-muted)';
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8">
      <rect x="3" y="5" width="18" height="16" rx="3" />
      <path d="M8 3v4M16 3v4M3 10h18" strokeLinecap="round" />
    </svg>
  );
}

function TrendingIcon({ active }: { active: boolean }) {
  const color = active ? 'var(--today-accent)' : 'var(--today-muted)';
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8">
      <path d="M3 17l6-6 4 4 8-8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M15 7h6v6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function TodayScreen() {
  const [entries, setEntries] = useState<EntryItem[]>([]);
  const [beliefs, setBeliefs] = useState<BeliefItem[]>([]);
  const [tab, setTab] = useState<Tab>('today');
  const [composerOpen, setComposerOpen] = useState(false);
  const [composerMood, setComposerMood] = useState(MOOD_OPTIONS[0]);
  const [composerText, setComposerText] = useState('');
  const [saving, setSaving] = useState(false);

  const headerDate = useMemo(() => formatHeaderDate(), []);

  const fetchAll = async () => {
    const [entriesResponse, beliefsResponse] = await Promise.all([
      fetch('http://localhost:8000/api/v1/entries'),
      fetch('http://localhost:8000/api/v1/beliefs'),
    ]);
    setEntries(await entriesResponse.json());
    setBeliefs(await beliefsResponse.json());
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const handleSaveEntry = async (event: FormEvent) => {
    event.preventDefault();
    if (!composerText.trim()) return;

    setSaving(true);
    try {
      await fetch('http://localhost:8000/api/v1/captures', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: 'journal',
          content: composerText,
          tags: [],
          mood_emoji: composerMood.emoji,
          mood_label: composerMood.label,
        }),
      });
      setComposerText('');
      setComposerMood(MOOD_OPTIONS[0]);
      setComposerOpen(false);
      await fetchAll();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="today-shell">
      <div className="today-frame">
        <header className="today-header">
          <Link href="/" className="today-logo">
            me
          </Link>
          <span className="today-date">{headerDate}</span>
        </header>

        <main className="today-body">
          {tab === 'today' ? (
            <div className="entry-stack">
              {entries.length === 0 && (
                <p className="today-empty">No entries yet. Tap + to add your first check-in.</p>
              )}
              {entries.map((entry) => (
                <article key={entry.id} className="entry-card">
                  <div className="entry-meta">
                    <span className="entry-mood">
                      <span className="entry-mood-emoji">{entry.mood_emoji}</span>
                      {entry.mood_label}
                    </span>
                    <span className="entry-time">{formatRelativeTime(entry.created_at)}</span>
                  </div>
                  <p className="entry-content">{entry.content}</p>

                  {entry.reflection && (
                    <div className="reflection-card">
                      <span className="reflection-label">Reflection</span>
                      <p className="reflection-text">{entry.reflection}</p>
                    </div>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <div className="entry-stack">
              {beliefs.map((belief) => (
                <article key={belief.topic} className="entry-card">
                  <div className="entry-meta">
                    <span className="entry-mood">{belief.topic}</span>
                    <span className="entry-time">{belief.status}</span>
                  </div>
                  <p className="entry-content">{belief.summary}</p>
                  <div className="belief-confidence">
                    Confidence: {(belief.confidence * 100).toFixed(0)}%
                  </div>
                </article>
              ))}
            </div>
          )}
        </main>

        <button
          type="button"
          className="today-fab"
          onClick={() => setComposerOpen(true)}
          aria-label="Add a new entry"
        >
          +
        </button>

        <nav className="today-nav">
          <button
            type="button"
            className={`today-nav-item ${tab === 'today' ? 'active' : ''}`}
            onClick={() => setTab('today')}
          >
            <CalendarIcon active={tab === 'today'} />
            <span>Today</span>
          </button>
          <button
            type="button"
            className={`today-nav-item ${tab === 'evolution' ? 'active' : ''}`}
            onClick={() => setTab('evolution')}
          >
            <TrendingIcon active={tab === 'evolution'} />
            <span>Evolution</span>
          </button>
        </nav>

        {composerOpen && (
          <div className="composer-backdrop" onClick={() => setComposerOpen(false)}>
            <form
              className="composer-sheet"
              onClick={(event) => event.stopPropagation()}
              onSubmit={handleSaveEntry}
            >
              <h2>New check-in</h2>

              <div className="mood-picker">
                {MOOD_OPTIONS.map((option) => (
                  <button
                    type="button"
                    key={option.label}
                    className={`mood-chip ${composerMood.label === option.label ? 'active' : ''}`}
                    onClick={() => setComposerMood(option)}
                  >
                    <span>{option.emoji}</span>
                    {option.label}
                  </button>
                ))}
              </div>

              <textarea
                className="composer-input"
                rows={5}
                value={composerText}
                onChange={(event) => setComposerText(event.target.value)}
                placeholder="What's going on?"
                autoFocus
              />

              <div className="composer-actions">
                <button type="submit" disabled={saving || !composerText.trim()}>
                  {saving ? 'Saving...' : 'Save entry'}
                </button>
                <button type="button" className="secondary" onClick={() => setComposerOpen(false)}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
