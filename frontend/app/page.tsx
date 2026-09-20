'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';

type MemoryItem = {
  id: string;
  title: string;
  type: string;
  summary: string;
  created_at: string;
  tags?: string[];
};

type BeliefItem = {
  topic: string;
  status: string;
  confidence: number;
  summary: string;
};

const initialForm = {
  source: 'text',
  content: '',
  tags: 'personal, reflection',
};

export default function HomePage() {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [beliefs, setBeliefs] = useState<BeliefItem[]>([]);
  const [summary, setSummary] = useState({ memory_count: 0, belief_count: 0, phase: 'founder pilot' });
  const [form, setForm] = useState(initialForm);
  const [query, setQuery] = useState('');
  const [reflection, setReflection] = useState<{ topic: string; insight: string; evidence: string[]; confidence: number } | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchAll = async () => {
    const [memoryResponse, beliefResponse, summaryResponse] = await Promise.all([
      fetch('http://localhost:8000/api/v1/memories'),
      fetch('http://localhost:8000/api/v1/beliefs'),
      fetch('http://localhost:8000/api/v1/summary'),
    ]);

    setMemories(await memoryResponse.json());
    setBeliefs(await beliefResponse.json());
    setSummary(await summaryResponse.json());
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const visibleMemories = useMemo(() => {
    if (!query.trim()) return memories;
    return memories.filter((memory) => {
      const text = `${memory.title} ${memory.summary}`.toLowerCase();
      return text.includes(query.toLowerCase());
    });
  }, [memories, query]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);

    const payload = {
      source: form.source,
      content: form.content,
      tags: form.tags.split(',').map((tag) => tag.trim()).filter(Boolean),
    };

    await fetch('http://localhost:8000/api/v1/captures', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    setForm(initialForm);
    await fetchAll();
    setLoading(false);
  };

  const handleReflection = async () => {
    const response = await fetch('http://localhost:8000/api/v1/reflections?topic=privacy+and+identity');
    setReflection(await response.json());
  };

  return (
    <main className="page-shell">
      <section className="hero">
        <span className="eyebrow">Founder pilot</span>
        <h1>selfie.Me</h1>
        <p className="subtitle">
          A privacy-first personal memory AI designed to preserve a person&apos;s memories,
          beliefs, decisions, and evolving self over time.
        </p>
      </section>

      <section className="dashboard-grid">
        <div className="panel">
          <div className="panel-header">
            <h2>Capture</h2>
            <span>{summary.phase}</span>
          </div>

          <form onSubmit={handleSubmit} className="capture-form">
            <label>
              Source
              <select value={form.source} onChange={(event) => setForm({ ...form, source: event.target.value })}>
                <option value="text">Text</option>
                <option value="voice">Voice</option>
                <option value="journal">Journal</option>
                <option value="photo">Photo</option>
              </select>
            </label>

            <label>
              Memory content
              <textarea
                rows={6}
                value={form.content}
                onChange={(event) => setForm({ ...form, content: event.target.value })}
                placeholder="What is happening, what are you thinking, and why does it matter?"
                required
              />
            </label>

            <label>
              Tags
              <input value={form.tags} onChange={(event) => setForm({ ...form, tags: event.target.value })} />
            </label>

            <button type="submit" disabled={loading}>
              {loading ? 'Saving...' : 'Save capture'}
            </button>
          </form>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Memory overview</h2>
            <span>{summary.memory_count} items</span>
          </div>

          <div className="metric-row">
            <div className="metric">
              <strong>{summary.memory_count}</strong>
              <span>memories</span>
            </div>
            <div className="metric">
              <strong>{summary.belief_count}</strong>
              <span>beliefs</span>
            </div>
          </div>

          <div className="search-wrap">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search memories and reflections"
            />
          </div>

          <div className="list-stack">
            {visibleMemories.map((memory) => (
              <article key={memory.id} className="memory-item">
                <div className="memory-meta">
                  <span className="pill">{memory.type}</span>
                  <span>{new Date(memory.created_at).toLocaleDateString()}</span>
                </div>
                <h3>{memory.title}</h3>
                <p>{memory.summary}</p>
                {memory.tags && memory.tags.length > 0 && (
                  <div className="tag-row">
                    {memory.tags.map((tag) => (
                      <span key={`${memory.id}-${tag}`} className="tag">#{tag}</span>
                    ))}
                  </div>
                )}
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="bottom-grid">
        <div className="panel">
          <div className="panel-header">
            <h2>Belief evolution</h2>
          </div>
          <div className="belief-list">
            {beliefs.map((belief) => (
              <div key={belief.topic} className="belief-item">
                <div className="belief-topline">
                  <strong>{belief.topic}</strong>
                  <span>{belief.status}</span>
                </div>
                <div className="confidence">Confidence: {(belief.confidence * 100).toFixed(0)}%</div>
                <p>{belief.summary}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Reflection</h2>
            <button type="button" className="secondary" onClick={handleReflection}>Generate</button>
          </div>

          {reflection ? (
            <div className="reflection-box">
              <p className="reflection-insight">{reflection.insight}</p>
              <div className="confidence">Confidence: {(reflection.confidence * 100).toFixed(0)}%</div>
              <ul>
                {reflection.evidence.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="empty-state">No reflection generated yet.</p>
          )}
        </div>
      </section>
    </main>
  );
}
