'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, Moment, Profile } from '../lib/api';
import { firstName, greeting, MOODS, shortDate } from '../lib/brain';
import { useThoughts } from '../lib/useThoughts';
import Icon from './Icon';
import NeuralOrb from './NeuralOrb';
import ThoughtCard from './ThoughtCard';

type SpeechRec = {
  start: () => void;
  stop: () => void;
  onresult: ((e: any) => void) | null;
  onend: (() => void) | null;
  interimResults: boolean;
  continuous: boolean;
  lang: string;
};

const OPENER_KEY = 'selfieme_opener';

export default function TalkScreen({ profile, regionColors }: { profile: Profile; regionColors: string[] }) {
  const email = profile.email;
  const [moments, setMoments] = useState<Moment[]>([]);
  const [opener, setOpener] = useState<string | null>(null);
  const [text, setText] = useState('');
  const [mood, setMood] = useState<string | null>(null);
  const [showMoods, setShowMoods] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [usedVoice, setUsedVoice] = useState(false);
  const recRef = useRef<SpeechRec | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const { thoughts, busyId, yes, no, refine, refresh: refreshThoughts } = useThoughts(email);

  const load = useCallback(async () => {
    try {
      setMoments(await api.listMoments(email));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load your thoughts.');
    }
  }, [email]);

  useEffect(() => {
    load();
    // Your brain says hello once per visit (Thalamus), not on every tab switch.
    const cached = sessionStorage.getItem(OPENER_KEY);
    if (cached) {
      setOpener(cached);
      return;
    }
    api
      .openConversation(email)
      .then((r) => {
        if (r.opening_message) {
          setOpener(r.opening_message);
          sessionStorage.setItem(OPENER_KEY, r.opening_message);
        }
      })
      .catch(() => setOpener(null));
  }, [email, load]);

  const thread = useMemo(() => [...moments].reverse().slice(-40), [moments]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [thread.length, thinking]);

  const send = async () => {
    const content = text.trim();
    if (!content || thinking) return;
    setError(null);
    setText('');
    setThinking(true);
    try {
      const moment = await api.addMoment(email, content, usedVoice ? 'voice' : 'text', mood);
      setMoments((m) => [moment, ...m]);
      setMood(null);
      setShowMoods(false);
      setUsedVoice(false);
      try {
        const r = await api.reflect(email, moment.id);
        setMoments((m) => m.map((x) => (x.id === moment.id ? { ...x, reflection: r.reflection } : x)));
      } catch {
        // The thought is saved even if your brain couldn't answer right now.
      }
      refreshThoughts();
    } catch (e) {
      setText(content);
      setError(e instanceof Error ? e.message : 'That didn’t save. Try again.');
    } finally {
      setThinking(false);
    }
  };

  const toggleMic = () => {
    const W = window as any;
    const Ctor = W.SpeechRecognition || W.webkitSpeechRecognition;
    if (!Ctor) {
      setError('Voice isn’t supported in this browser — try Safari or Chrome.');
      return;
    }
    if (recording) {
      recRef.current?.stop();
      return;
    }
    const rec: SpeechRec = new Ctor();
    rec.lang = navigator.language || 'en-US';
    rec.interimResults = true;
    rec.continuous = false;
    const base = text ? text + ' ' : '';
    rec.onresult = (e: any) => {
      const said = Array.from(e.results)
        .map((r: any) => r[0].transcript)
        .join('');
      setText(base + said);
      setUsedVoice(true);
    };
    rec.onend = () => setRecording(false);
    recRef.current = rec;
    setRecording(true);
    rec.start();
  };

  let lastDay = '';

  return (
    <div className="screen" style={{ paddingBottom: 240 }}>
      <header className="talk-head">
        <NeuralOrb colors={regionColors} thinking={thinking} size={170} />
        <p className="kicker">{thinking ? 'Your brain is thinking' : 'Your second brain is listening'}</p>
      </header>

      {thread.length === 0 && (
        <div style={{ marginTop: 18 }}>
          <h1 className="display" style={{ fontSize: 40 }}>
            {greeting()},<br />
            <em>{firstName(profile.full_name)}</em>
          </h1>
        </div>
      )}

      <section className="thread" aria-live="polite">
        {opener && (
          <div className="brain-say">
            <p className="kicker">Your brain</p>
            <p className="say">{opener}</p>
          </div>
        )}

        {thread.map((m) => {
          const day = shortDate(m.created_at);
          const sep = day !== lastDay ? day : null;
          lastDay = day;
          return (
            <motion.div key={m.id} style={{ display: 'contents' }} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              {sep && <div className="day-sep">{sep}</div>}
              <div className="bubble-me">
                {m.content}
                {m.mood && (
                  <span className="small muted" style={{ display: 'block', marginTop: 6 }}>
                    feeling {m.mood}
                  </span>
                )}
              </div>
              {m.reflection && (
                <div className="brain-say">
                  <p className="kicker">You, remembered</p>
                  <p className="say">{m.reflection}</p>
                </div>
              )}
            </motion.div>
          );
        })}

        {thinking && (
          <div className="brain-say" aria-label="Your brain is thinking">
            <div className="thinking">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}

        <AnimatePresence>
          {thoughts.slice(0, 2).map((t) => (
            <ThoughtCard
              key={t.id}
              kind={t.kind}
              domain={t.domain}
              text={t.text}
              busy={busyId === t.id}
              onYes={() => yes(t)}
              onNo={() => no(t)}
              onRefine={t.kind === 'thought' ? (w) => refine(t, w) : undefined}
            />
          ))}
        </AnimatePresence>
        {thoughts.length > 0 && (
          <p className="small muted center" style={{ margin: 0 }}>
            Nothing joins your brain until you say so.
            {thoughts.length > 2 ? ` ${thoughts.length - 2} more in Brain.` : ''}
          </p>
        )}
        <div ref={endRef} />
      </section>

      <div className="composer">
        {showMoods && (
          <div className="mood-strip" role="group" aria-label="How do you feel?">
            {MOODS.map((m) => (
              <button
                key={m.key}
                type="button"
                className="chip"
                aria-pressed={mood === m.key}
                onClick={() => setMood(mood === m.key ? null : m.key)}
              >
                <span className="dot" style={{ background: m.color, width: 8, height: 8 }} />
                {m.label}
              </button>
            ))}
          </div>
        )}
        {error && (
          <p className="error" role="alert" style={{ margin: '0 0 8px', background: 'var(--surface)', padding: '8px 14px', borderRadius: 14 }}>
            {error}
          </p>
        )}
        <div className="composer-inner">
          <button
            type="button"
            className="icon-btn"
            aria-label="How do you feel?"
            aria-expanded={showMoods}
            onClick={() => setShowMoods((s) => !s)}
            style={mood ? { borderColor: 'var(--accent)' } : undefined}
          >
            <span className="dot" style={{ background: mood ? MOODS.find((m) => m.key === mood)?.color : 'var(--faint)' }} />
          </button>
          <label htmlFor="talk-input" className="sr-only">
            Talk to yourself
          </label>
          <input
            id="talk-input"
            className="pill-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()}
            placeholder={recording ? 'Listening…' : 'Talk to yourself…'}
            autoComplete="off"
          />
          {text.trim() ? (
            <button type="button" className="icon-btn solid" aria-label="Send" onClick={send} disabled={thinking}>
              <Icon name="send" size={22} />
            </button>
          ) : (
            <button
              type="button"
              className={`icon-btn solid${recording ? ' recording' : ''}`}
              aria-label={recording ? 'Stop listening' : 'Speak'}
              aria-pressed={recording}
              onClick={toggleMic}
            >
              <Icon name="mic" size={22} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
