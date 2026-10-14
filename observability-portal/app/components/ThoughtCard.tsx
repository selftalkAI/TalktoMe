'use client';

import { motion } from 'framer-motion';
import { useState } from 'react';
import Icon from './Icon';
import Sheet from './Sheet';
import { regionColor, regionLabel } from '../lib/brain';

// "A new thought" — something your brain drafted (a Profile proposal) or a
// small thing it heard you say (a candidate memory). Only the user's tap
// decides what joins their brain.

type Props = {
  kind: 'thought' | 'memory';
  domain: string | null;
  text: string;
  busy?: boolean;
  onYes: () => void;
  onNo: () => void;
  onRefine?: (words: string) => Promise<void> | void;
};

export default function ThoughtCard({ kind, domain, text, busy, onYes, onNo, onRefine }: Props) {
  const [refining, setRefining] = useState(false);
  const [words, setWords] = useState('');
  const [wordsError, setWordsError] = useState<string | null>(null);

  const submitRefine = async () => {
    if (!words.trim()) {
      setWordsError('Say it in your own words first.');
      return;
    }
    await onRefine?.(words.trim());
    setRefining(false);
    setWords('');
  };

  return (
    <motion.article
      className="thought-card"
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.97 }}
      transition={{ duration: 0.22 }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: 'var(--thought)' }}>
          <Icon name={kind === 'thought' ? 'bulb' : 'spark'} size={16} />
        </span>
        <p className="kicker thought">{kind === 'thought' ? 'A new thought' : 'Is this you?'}</p>
        {domain && (
          <span className="small muted" style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span className="dot" style={{ background: regionColor(domain), width: 8, height: 8 }} />
            {regionLabel(domain)}
          </span>
        )}
      </div>
      <p className="say" style={{ fontSize: kind === 'thought' ? 20 : 19 }}>{text}</p>
      <div className="btn-row">
        <button type="button" className="btn btn-thought btn-sm" disabled={busy} onClick={onYes}>
          That&rsquo;s me
        </button>
        {kind === 'thought' && onRefine ? (
          <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => setRefining(true)}>
            Not quite
          </button>
        ) : null}
        <button type="button" className="btn btn-quiet btn-sm" disabled={busy} onClick={onNo}>
          Not me
        </button>
      </div>

      <Sheet open={refining} onClose={() => setRefining(false)} label="Say it your way">
        <p className="kicker thought">Not quite</p>
        <h2 className="title" style={{ fontSize: 28 }}>Say it your way</h2>
        <p className="muted small" style={{ marginTop: 6 }}>Your brain will redraw this thought with your words. The old version stays in history.</p>
        <label className="field">
          <span className="sr-only">What&rsquo;s closer to the truth?</span>
          <textarea
            className="textarea"
            value={words}
            onChange={(e) => {
              setWords(e.target.value);
              setWordsError(null);
            }}
            placeholder="It's less about time, more that I read when I can't sleep."
            autoFocus
          />
        </label>
        {wordsError && <p className="error">{wordsError}</p>}
        <button type="button" className="btn btn-primary btn-block" style={{ marginTop: 16 }} disabled={busy} onClick={submitRefine}>
          {busy ? 'Redrawing…' : 'Redraw this thought'}
        </button>
      </Sheet>
    </motion.article>
  );
}
