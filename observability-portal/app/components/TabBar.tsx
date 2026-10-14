'use client';

import Icon from './Icon';

export type Tab = 'talk' | 'brain' | 'memories' | 'you';

const TABS: Array<{ key: Tab; label: string; icon: string }> = [
  { key: 'talk', label: 'Talk', icon: 'talk' },
  { key: 'brain', label: 'Brain', icon: 'brain' },
  { key: 'memories', label: 'Memories', icon: 'clock' },
  { key: 'you', label: 'You', icon: 'user' },
];

export default function TabBar({ active, onChange, badges = {} }: { active: Tab; onChange: (t: Tab) => void; badges?: Partial<Record<Tab, boolean>> }) {
  return (
    <nav className="tabbar" aria-label="Main">
      {TABS.map((t) => (
        <button
          key={t.key}
          type="button"
          className="tab"
          aria-current={active === t.key ? 'page' : undefined}
          onClick={() => onChange(t.key)}
        >
          <Icon name={t.icon} />
          {t.label}
          {badges[t.key] && <span className="badge" aria-label="new" />}
        </button>
      ))}
    </nav>
  );
}
