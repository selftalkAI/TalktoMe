// Small presentation helpers shared across screens — how regions are named,
// colored and placed. No data fetching here.

const KNOWN: Record<string, { label: string; color: string }> = {
  reading: { label: 'Reading', color: '#E8B86B' },
  learning: { label: 'Learning', color: '#9FD8B5' },
  emotion: { label: 'Feelings', color: '#7FC4D8' },
  skill: { label: 'Skills', color: '#B9A6F2' },
};

const EXTRA = ['#F0997B', '#E59BC0', '#C7D67A', '#8FB8F2', '#F2C46B'];

export function regionLabel(domain: string): string {
  return KNOWN[domain]?.label ?? domain.charAt(0).toUpperCase() + domain.slice(1).replace(/[_-]/g, ' ');
}

export function regionColor(domain: string): string {
  if (KNOWN[domain]) return KNOWN[domain].color;
  let h = 0;
  for (const ch of domain) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return EXTRA[h % EXTRA.length];
}

// Fixed anchor points inside the brain outline (viewBox 360×300), filled in
// order. The first four are the four lobes; extras sit between them.
export const REGION_SLOTS: Array<{ x: number; y: number }> = [
  { x: 120, y: 112 }, // front
  { x: 196, y: 76 }, // top
  { x: 268, y: 128 }, // back
  { x: 186, y: 182 }, // lower
  { x: 236, y: 196 },
  { x: 96, y: 168 },
  { x: 156, y: 132 },
  { x: 226, y: 132 },
];

export function firstName(fullName: string | undefined | null): string {
  return (fullName ?? '').trim().split(/\s+/)[0] || 'there';
}

export function greeting(now = new Date()): string {
  const h = now.getHours();
  if (h < 5) return 'Still up';
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
}

export function shortDate(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const diffDays = Math.round((startOfDay(today) - startOfDay(d)) / 86_400_000);
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

export const MOODS: Array<{ key: string; label: string; color: string }> = [
  { key: 'good', label: 'Good', color: '#9FD8B5' },
  { key: 'calm', label: 'Calm', color: '#7FC4D8' },
  { key: 'okay', label: 'Okay', color: '#C9C2B2' },
  { key: 'low', label: 'Low', color: '#8E8AB8' },
  { key: 'frustrated', label: 'Frustrated', color: '#F0997B' },
  { key: 'excited', label: 'Excited', color: '#E8B86B' },
];

export function moodColor(mood: string | null | undefined): string {
  return MOODS.find((m) => m.key === mood)?.color ?? '#6E8579';
}
