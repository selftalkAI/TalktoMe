'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, useState } from 'react';
import { api, Evolution } from '../lib/api';
import { MOODS, moodColor } from '../lib/brain';
import Icon from './Icon';

// "Your week, inside your head" — a short story built only from what you
// actually said this week. Tap the right side to advance, left to go back.

export default function WeekStory({ email, onClose }: { email: string; onClose: () => void }) {
  const [evo, setEvo] = useState<Evolution | null>(null);
  const [narrative, setNarrative] = useState<string | null>(null);
  const [i, setI] = useState(0);

  useEffect(() => {
    api.evolution(email, 7).then(setEvo).catch(() => setEvo(null));
    api
      .evolutionNarrative(email, 7)
      .then((r) => setNarrative(r.narrative))
      .catch(() => setNarrative('Your brain couldn’t write this part right now. Your words are all still here.'));
  }, [email]);

  const moods = evo
    ? Object.entries(evo.mood_counts_in_range)
        .filter(([k]) => k !== 'unspecified')
        .sort((a, b) => b[1] - a[1])
    : [];
  const maxMood = Math.max(1, ...moods.map(([, n]) => n));
  const top = moods[0]?.[0];
  const slides = 3;

  const go = (d: number) => {
    const n = i + d;
    if (n >= slides) onClose();
    else setI(Math.max(0, n));
  };

  return (
    <motion.div className="story" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} role="dialog" aria-modal="true" aria-label="Your week">
      <div className="story-inner">
        <div className="story-bars" aria-hidden="true">
          {Array.from({ length: slides }).map((_, k) => (
            <span key={k} className={k <= i ? 'on' : ''} />
          ))}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 14 }}>
          <p style={{ margin: 0, fontSize: 13, fontWeight: 600, letterSpacing: '0.08em', color: '#f0b394' }}>YOUR WEEK, INSIDE YOUR HEAD</p>
          <button type="button" aria-label="Close" onClick={onClose} style={{ width: 44, height: 44, borderRadius: 22, border: 0, background: '#4e2a39', color: '#fbe8da', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="close" size={18} />
          </button>
        </div>

        <AnimatePresence mode="wait">
          <motion.div key={i} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.3 }} style={{ flex: 1 }}>
            {i === 0 && (
              <>
                <h2>
                  This week you talked to yourself <em>{evo ? evo.moments_in_range : '…'}</em> time{evo?.moments_in_range === 1 ? '' : 's'}.
                </h2>
                <p className="lead">
                  {evo && evo.moments_in_range === 0
                    ? 'A quiet week. Your brain is still here whenever you want to talk.'
                    : `That’s ${evo?.total_moments_all_time ?? '…'} thoughts your brain has heard from you so far.`}
                </p>
              </>
            )}
            {i === 1 && (
              <>
                <h2>{top ? <>Mostly, you felt <em>{MOODS.find((m) => m.key === top)?.label.toLowerCase() ?? top}</em>.</> : <>You didn’t name many feelings this week.</>}</h2>
                <div style={{ marginTop: 30, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {moods.length === 0 && <p className="lead">Next time, tap the dot beside the text box to tell your brain how you feel.</p>}
                  {moods.map(([k, n]) => (
                    <div key={k}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 15 }}>
                        <span style={{ fontWeight: 600 }}>{MOODS.find((m) => m.key === k)?.label ?? k}</span>
                        <span style={{ color: '#e7c2b0' }}>{n}</span>
                      </div>
                      <div style={{ height: 12, borderRadius: 6, background: '#4e2a39', marginTop: 6 }}>
                        <motion.div initial={{ width: 0 }} animate={{ width: `${(n / maxMood) * 100}%` }} transition={{ duration: 0.6 }} style={{ height: 12, borderRadius: 6, background: moodColor(k) }} />
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
            {i === 2 && (
              <>
                <h2>How you’re <em>changing</em></h2>
                <p className="lead">{narrative ?? 'Your brain is reading your week…'}</p>
              </>
            )}
          </motion.div>
        </AnimatePresence>

        <div style={{ display: 'flex', gap: 10 }}>
          <button type="button" onClick={() => go(-1)} disabled={i === 0} style={{ flex: 1, height: 54, borderRadius: 27, border: '1px solid #8a5a6c', background: 'transparent', color: '#fbe8da', fontSize: 16, opacity: i === 0 ? 0.4 : 1 }}>
            Back
          </button>
          <button type="button" onClick={() => go(1)} style={{ flex: 1, height: 54, borderRadius: 27, border: 0, background: '#f0b394', color: '#3b1f2b', fontSize: 16, fontWeight: 700 }}>
            {i === slides - 1 ? 'Done' : 'Next'}
          </button>
        </div>
      </div>
    </motion.div>
  );
}
