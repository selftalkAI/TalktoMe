'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { useCallback, useEffect, useMemo, useState } from 'react';
import AuthScreen from './components/AuthScreen';
import BrainScreen from './components/BrainScreen';
import MemoriesScreen from './components/MemoriesScreen';
import NeuralOrb from './components/NeuralOrb';
import Onboarding from './components/Onboarding';
import TabBar, { Tab } from './components/TabBar';
import TalkScreen from './components/TalkScreen';
import WeekStory from './components/WeekStory';
import YouScreen from './components/YouScreen';
import { api, KeyArea, Profile } from './lib/api';
import { regionColor } from './lib/brain';

// Only the email is kept between visits — a pointer to re-fetch the
// profile, never a password or a cached copy of anything personal.
const SESSION_KEY = 'selfieme_session_email';

type Stage = 'loading' | 'auth' | 'onboarding' | 'app';

export default function Home() {
  const [stage, setStage] = useState<Stage>('loading');
  const [profile, setProfile] = useState<Profile | null>(null);
  const [pending, setPending] = useState<{ email: string; password: string } | null>(null);
  const [tab, setTab] = useState<Tab>('talk');
  const [areas, setAreas] = useState<KeyArea[]>([]);
  const [hasThoughts, setHasThoughts] = useState(false);
  const [story, setStory] = useState(false);

  useEffect(() => {
    let saved: string | null = null;
    try {
      saved = localStorage.getItem(SESSION_KEY);
    } catch {
      /* storage off */
    }
    if (!saved) return setStage('auth');
    api
      .getProfile(saved)
      .then((p) => {
        setProfile(p);
        setStage('app');
      })
      .catch(() => setStage('auth'));
  }, []);

  const refreshBrain = useCallback(async (email: string) => {
    try {
      const [a, p] = await Promise.all([api.keyAreas(email), api.pending(email)]);
      setAreas(a);
      setHasThoughts(p.length > 0 || a.some((x) => x.has_pending_proposal));
    } catch {
      /* the screens show their own errors */
    }
  }, []);

  useEffect(() => {
    if (profile) refreshBrain(profile.email);
  }, [profile, tab, refreshBrain]);

  const enter = (p: Profile) => {
    try {
      localStorage.setItem(SESSION_KEY, p.email);
    } catch {
      /* session just won't survive a reload */
    }
    setProfile(p);
    setTab('talk');
    setStage('app');
  };

  const logout = () => {
    try {
      localStorage.removeItem(SESSION_KEY);
      sessionStorage.clear();
    } catch {
      /* ignore */
    }
    setProfile(null);
    setStage('auth');
  };

  const regionColors = useMemo(() => areas.filter((a) => a.active_memory_count > 0).map((a) => regionColor(a.domain)), [areas]);

  return (
    <div className="app">
      <AnimatePresence mode="wait">
        {stage === 'loading' && (
          <motion.div key="loading" className="screen-flat" style={{ alignItems: 'center', justifyContent: 'center' }} exit={{ opacity: 0 }}>
            <NeuralOrb colors={[]} thinking size={200} label="Opening your brain" />
          </motion.div>
        )}

        {stage === 'auth' && (
          <motion.div key="auth" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <AuthScreen
              onLoggedIn={enter}
              onNewProfile={(email, password) => {
                setPending({ email, password });
                setStage('onboarding');
              }}
            />
          </motion.div>
        )}

        {stage === 'onboarding' && pending && (
          <motion.div key="onboarding" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <Onboarding email={pending.email} password={pending.password} onDone={enter} onBack={() => setStage('auth')} />
          </motion.div>
        )}

        {stage === 'app' && profile && (
          <motion.div key={`app-${tab}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
            {tab === 'talk' && <TalkScreen profile={profile} regionColors={regionColors} />}
            {tab === 'brain' && <BrainScreen profile={profile} onAreas={setAreas} />}
            {tab === 'memories' && <MemoriesScreen profile={profile} onStory={() => setStory(true)} />}
            {tab === 'you' && <YouScreen profile={profile} areas={areas} onStory={() => setStory(true)} onLogout={logout} />}
          </motion.div>
        )}
      </AnimatePresence>

      {stage === 'app' && profile && <TabBar active={tab} onChange={setTab} badges={{ brain: hasThoughts }} />}

      <AnimatePresence>{story && profile && <WeekStory email={profile.email} onClose={() => setStory(false)} />}</AnimatePresence>
    </div>
  );
}
