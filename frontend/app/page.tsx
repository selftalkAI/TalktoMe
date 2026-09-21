'use client';

import { useRouter } from 'next/navigation';
import { FormEvent, useState } from 'react';

export default function WelcomePage() {
  const router = useRouter();
  const [thought, setThought] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    if (!thought.trim()) {
      router.push('/dashboard');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await fetch('http://localhost:8000/api/v1/captures', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: 'text',
          content: thought,
          tags: ['daily-check-in'],
        }),
      });
      router.push('/dashboard');
    } catch (err) {
      setError('Could not save that right now. You can still continue.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="welcome-shell">
      <form className="welcome-card" onSubmit={handleSubmit}>
        <h1>Hi You</h1>
        <p className="welcome-subtitle">
          Take a moment to check in with yourself before you dive in.
        </p>

        <textarea
          className="thought-input"
          value={thought}
          onChange={(event) => setThought(event.target.value)}
          placeholder="What's your Thoughts"
          rows={6}
          autoFocus
        />

        {error && <p className="welcome-error">{error}</p>}

        <div className="welcome-actions">
          <button type="submit" disabled={submitting}>
            {submitting ? 'Saving...' : 'Continue'}
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => router.push('/dashboard')}
          >
            Skip for now
          </button>
        </div>
      </form>
    </main>
  );
}
