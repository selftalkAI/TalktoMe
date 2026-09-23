'use client';

import { ChangeEvent, useState } from 'react';
import { motion } from 'framer-motion';

export type Profile = {
  fullName: string;
  email: string;
  dob: string;
  location: string;
  interests: string[];
  otherInterests: string;
  photoDataUrl: string | null;
  quote: string;
};

const INTERESTS = [
  { key: 'parenting', icon: '👨‍👩‍👧', label: 'Parenting' },
  { key: 'healthy_living', icon: '❤️', label: 'Healthy Living' },
  { key: 'recipes', icon: '🍽️', label: 'Recipes' },
  { key: 'kids_activities', icon: '🧩', label: 'Kids Activities' },
  { key: 'learning', icon: '📖', label: 'Learning' },
  { key: 'travel', icon: '✈️', label: 'Travel' },
  { key: 'home_lifestyle', icon: '🏡', label: 'Home & Lifestyle' },
  { key: 'mindfulness', icon: '🍃', label: 'Mindfulness' },
  { key: 'community', icon: '👥', label: 'Community' },
  { key: 'photography', icon: '📷', label: 'Photography' },
  { key: 'career', icon: '💼', label: 'Career & Work' },
  { key: 'finance', icon: '📊', label: 'Finance' },
];

function ClearableField({
  label,
  type = 'text',
  value,
  onChange,
  placeholder,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="form-field">
      <span>{label}</span>
      <div className="form-field-input">
        <input type={type} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
        {value && (
          <button type="button" className="field-clear" aria-label={`Clear ${label}`} onClick={() => onChange('')}>
            ×
          </button>
        )}
      </div>
    </label>
  );
}

function emptyProfile(initialEmail: string): Profile {
  return {
    fullName: '',
    email: initialEmail,
    dob: '',
    location: '',
    interests: [],
    otherInterests: '',
    photoDataUrl: null,
    quote: '',
  };
}

export default function Onboarding({
  initialEmail,
  onComplete,
  onSkip,
}: {
  initialEmail: string;
  onComplete: (profile: Profile) => Promise<void>;
  onSkip: () => void;
}) {
  const [step, setStep] = useState(1);
  const [profile, setProfile] = useState<Profile>(() => emptyProfile(initialEmail));
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const handlePhotoChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setProfile((p) => ({ ...p, photoDataUrl: reader.result as string }));
    reader.readAsDataURL(file);
  };

  const toggleInterest = (key: string) => {
    setProfile((p) => ({
      ...p,
      interests: p.interests.includes(key) ? p.interests.filter((k) => k !== key) : [...p.interests, key],
    }));
  };

  const handleCreate = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      await onComplete(profile);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Could not save your profile.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="onboarding-shell">
      <header className="onboarding-header">
        <button
          type="button"
          className="onboarding-back"
          aria-label="Back"
          disabled={step === 1}
          onClick={() => setStep((s) => Math.max(1, s - 1))}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M15 5 8 12l7 7" stroke="#23271f" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <div className="progress-track">
          {[1, 2, 3].map((s) => (
            <span key={s} className={s <= step ? 'progress-seg filled' : 'progress-seg'} />
          ))}
        </div>
        <button type="button" className="onboarding-skip" onClick={onSkip}>
          Skip
        </button>
      </header>

      <div className="onboarding-body">
        <p className="onboarding-step">Step {step} of 3</p>

        {step === 1 && (
          <motion.div key="s1" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.2 }}>
            <h1>Let&apos;s get to know you</h1>
            <p className="onboarding-sub">This helps us personalize your experience.</p>

            <ClearableField
              label="Full name"
              value={profile.fullName}
              onChange={(v) => setProfile((p) => ({ ...p, fullName: v }))}
              placeholder="Your name"
            />

            <ClearableField
              label="Email"
              type="email"
              value={profile.email}
              onChange={(v) => setProfile((p) => ({ ...p, email: v }))}
              placeholder="you@example.com"
            />

            <label className="form-field">
              <span>Date of birth</span>
              <input type="date" value={profile.dob} onChange={(e) => setProfile((p) => ({ ...p, dob: e.target.value }))} />
            </label>

            <ClearableField
              label="Location"
              value={profile.location}
              onChange={(v) => setProfile((p) => ({ ...p, location: v }))}
              placeholder="City, region"
            />

            <motion.button
              type="button"
              className="onboarding-continue"
              whileTap={{ scale: 0.97 }}
              disabled={!profile.fullName.trim() || !profile.email.trim()}
              onClick={() => setStep(2)}
            >
              Continue <span aria-hidden>→</span>
            </motion.button>

            <p className="privacy-note">🔒 Your information is safe with us.</p>
          </motion.div>
        )}

        {step === 2 && (
          <motion.div key="s2" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.2 }}>
            <h1>What are you interested in?</h1>
            <p className="onboarding-sub">Choose a few topics to personalize your feed.</p>

            <div className="interest-grid">
              {INTERESTS.map((interest) => {
                const selected = profile.interests.includes(interest.key);
                return (
                  <motion.button
                    key={interest.key}
                    type="button"
                    whileTap={{ scale: 0.95 }}
                    className={selected ? 'interest-card selected' : 'interest-card'}
                    onClick={() => toggleInterest(interest.key)}
                  >
                    {selected && <span className="interest-check">✓</span>}
                    <span className="interest-icon">{interest.icon}</span>
                    <span className="interest-label">{interest.label}</span>
                  </motion.button>
                );
              })}
            </div>

            <ClearableField
              label="Other interests (optional)"
              value={profile.otherInterests}
              onChange={(v) => setProfile((p) => ({ ...p, otherInterests: v }))}
              placeholder="e.g. gardening, art, pets…"
            />

            <motion.button type="button" className="onboarding-continue" whileTap={{ scale: 0.97 }} onClick={() => setStep(3)}>
              Continue <span aria-hidden>→</span>
            </motion.button>
          </motion.div>
        )}

        {step === 3 && (
          <motion.div key="s3" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.2 }}>
            <h1>Add a profile photo</h1>
            <p className="onboarding-sub">A photo helps you recognize your own space.</p>

            <div className="photo-upload-wrap">
              <div className="photo-upload-circle-wrap">
                <label className="photo-upload-circle">
                  {profile.photoDataUrl ? (
                    <img src={profile.photoDataUrl} alt="" />
                  ) : (
                    <span className="photo-upload-placeholder">{profile.fullName.trim().charAt(0).toUpperCase() || '🙂'}</span>
                  )}
                  <span className="photo-upload-badge">📷</span>
                  <input type="file" accept="image/*" onChange={handlePhotoChange} hidden />
                </label>
                {profile.photoDataUrl && (
                  <button
                    type="button"
                    className="photo-remove"
                    aria-label="Remove photo"
                    onClick={() => setProfile((p) => ({ ...p, photoDataUrl: null }))}
                  >
                    ×
                  </button>
                )}
              </div>
              <p className="profile-name">{profile.fullName || 'You'}</p>
              {profile.location && <p className="profile-location">{profile.location}</p>}
            </div>

            <div className="quote-card">
              <span className="quote-edit">✏️</span>
              <input
                type="text"
                value={profile.quote}
                onChange={(e) => setProfile((p) => ({ ...p, quote: e.target.value }))}
                placeholder="Add a personal quote…"
              />
              {profile.quote && (
                <button
                  type="button"
                  className="field-clear"
                  aria-label="Clear quote"
                  onClick={() => setProfile((p) => ({ ...p, quote: '' }))}
                >
                  ×
                </button>
              )}
            </div>

            {(profile.location || profile.interests.length > 0) && (
              <div className="profile-facts">
                {profile.location && (
                  <div className="profile-fact-row">
                    <span className="fact-icon">📍</span>
                    <span>{profile.location}</span>
                  </div>
                )}
                {profile.interests.length > 0 && (
                  <div className="profile-fact-row">
                    <span className="fact-icon">🍃</span>
                    <span>{profile.interests.map((k) => INTERESTS.find((i) => i.key === k)?.label).join(', ')}</span>
                  </div>
                )}
              </div>
            )}

            {saveError && <p className="error-text">{saveError}</p>}

            <motion.button
              type="button"
              className="onboarding-continue"
              whileTap={{ scale: 0.97 }}
              disabled={saving}
              onClick={handleCreate}
            >
              {saving ? 'Saving…' : 'Create Profile'}
            </motion.button>

            <p className="terms-note">By continuing, you agree to our Terms of Use and Privacy Policy.</p>
          </motion.div>
        )}
      </div>
    </div>
  );
}
