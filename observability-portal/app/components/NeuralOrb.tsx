'use client';

// The visible "second brain": a small constellation around a glowing core.
// Each satellite neuron is one of the user's regions (by color); the core
// breathes while the brain is thinking.

export default function NeuralOrb({
  colors,
  thinking = false,
  size = 180,
  label = 'Your brain',
}: {
  colors: string[];
  thinking?: boolean;
  size?: number;
  label?: string;
}) {
  const sats = (colors.length ? colors : ['#9FD8B5', '#E8B86B', '#B9A6F2', '#7FC4D8']).slice(0, 6);
  const cx = 95;
  const cy = 75;
  const points = sats.map((_, i) => {
    const a = (i / sats.length) * Math.PI * 2 - Math.PI / 2.4;
    const rx = i % 2 ? 62 : 54;
    const ry = i % 2 ? 50 : 44;
    return { x: cx + Math.cos(a) * rx, y: cy + Math.sin(a) * ry };
  });

  return (
    <svg role="img" aria-label={thinking ? `${label} is thinking` : label} width={size} height={size * 0.8} viewBox="0 0 190 152">
      <g stroke="var(--line-strong)" strokeWidth="1">
        {points.map((p, i) => (
          <line key={`c${i}`} x1={cx} y1={cy} x2={p.x} y2={p.y} />
        ))}
        {points.map((p, i) => {
          const n = points[(i + 1) % points.length];
          return <line key={`r${i}`} x1={p.x} y1={p.y} x2={n.x} y2={n.y} opacity="0.6" />;
        })}
      </g>
      <circle cx={cx} cy={cy} r="34" fill="var(--orb-1)" />
      <circle cx={cx} cy={cy} r="22" fill="var(--orb-2)" className={thinking ? 'orb-breathe' : undefined} />
      <circle cx={cx} cy={cy} r="10" fill="var(--accent)" className={thinking ? 'orb-breathe' : undefined} />
      {points.map((p, i) => (
        <circle key={`n${i}`} cx={p.x} cy={p.y} r={i % 3 === 0 ? 6 : 4.5} fill={sats[i]} />
      ))}
      <circle cx={cx - 2} cy="10" r="2.5" fill="var(--text)" opacity="0.6" />
      <circle cx="30" cy="40" r="2" fill="var(--text)" opacity="0.4" />
      <circle cx="166" cy="128" r="2" fill="var(--text)" opacity="0.4" />
    </svg>
  );
}
