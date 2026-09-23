'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Profile } from './onboarding';

const API_BASE = 'http://localhost:8000';

type Stage = 'opening' | 'listening' | 'understanding' | 'ready';

type ConversationResult = {
  welcome_message: string;
  suggested_first_action: string;
};

export default function Welcome({
  profile,
  onContinue,
  onStartWithSuggestion,
}: {
  profile: Profile;
  onContinue: () => void;
  onStartWithSuggestion: (suggestion: string) => void;
}) {
  const [stage, setStage] = useState<Stage>('opening');
  const [openingMessage, setOpeningMessage] = useState('');
  const [responseText, setResponseText] = useState('');
  const [result, setResult] = useState<ConversationResult | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/profiles/${encodeURIComponent(profile.email)}/conversation/open`, { method: 'POST' })
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => {
        if (cancelled) return;
        setOpeningMessage(data.opening_message);
        setStage('listening');
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [profile.email]);

  // Best-effort only — the agent being unreachable must never block someone
  // from reaching their own journal.
  useEffect(() => {
    if (failed) onContinue();
  }, [failed, onContinue]);

  const submitResponse = async () => {
    if (!responseText.trim()) return;
    setStage('understanding');
    try {
      const res = await fetch(`${API_BASE}/api/v1/profiles/${encodeURIComponent(profile.email)}/conversation/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ response_text: responseText.trim() }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setResult(data);
      setStage('ready');
    } catch {
      setFailed(true);
    }
  };

  if (failed) return null;

  return (
    <div className="onboarding-shell">
      <div className="onboarding-body welcome-body">
        {stage === 'opening' && <p className="welcome-loading">Getting to know you…</p>}

        {stage !== 'opening' && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
            <p className="welcome-message">{openingMessage}</p>

            <AnimatePresence mode="wait">
              {stage === 'ready' && result ? (
                <motion.div key="result" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
                  <p className="welcome-message welcome-followup">{result.welcome_message}</p>

                  {result.suggested_first_action && (
                    <div className="suggestion-card">
                      <span className="suggestion-label">Try this first</span>
                      <p>{result.suggested_first_action}</p>
                    </div>
                  )}

                  <motion.button
                    type="button"
                    className="onboarding-continue"
                    whileTap={{ scale: 0.97 }}
                    onClick={() =>
                      result.suggested_first_action ? onStartWithSuggestion(result.suggested_first_action) : onContinue()
                    }
                  >
                    {result.suggested_first_action ? 'Log this moment' : "Let's go"} <span aria-hidden>→</span>
                  </motion.button>

                  {result.suggested_first_action && (
                    <button type="button" className="welcome-skip" onClick={onContinue}>
                      Skip to my journal
                    </button>
                  )}
                </motion.div>
              ) : (
                <motion.div key="input" exit={{ opacity: 0 }}>
                  <textarea
                    autoFocus
                    rows={4}
                    className="welcome-response"
                    value={responseText}
                    onChange={(e) => setResponseText(e.target.value)}
                    placeholder="Tell me however you're doing…"
                    disabled={stage === 'understanding'}
                  />
                  <motion.button
                    type="button"
                    className="onboarding-continue"
                    whileTap={{ scale: 0.97 }}
                    disabled={!responseText.trim() || stage === 'understanding'}
                    onClick={submitResponse}
                  >
                    {stage === 'understanding' ? 'Listening…' : 'Share'} <span aria-hidden>→</span>
                  </motion.button>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </div>
    </div>
  );
}
