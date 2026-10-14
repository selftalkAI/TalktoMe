'use client';

import { motion } from 'framer-motion';
import { KeyArea } from '../lib/api';
import { REGION_SLOTS, regionColor, regionLabel } from '../lib/brain';

// Your mind drawn as a brain: each region is a cluster of neurons. Bigger
// cluster = more you've said about it; a dashed ring = a new thought waiting.

const OUTLINE =
  'M62 150 C 34 98, 76 40, 148 46 C 188 14, 262 24, 288 70 C 334 86, 336 162, 294 178 C 284 210, 232 222, 206 200 C 184 232, 118 226, 108 194 C 72 200, 54 178, 62 150 Z';

export default function RegionMap({ areas, onOpen }: { areas: KeyArea[]; onOpen: (domain: string) => void }) {
  const placed = areas.slice(0, REGION_SLOTS.length).map((a, i) => ({ ...a, ...REGION_SLOTS[i] }));
  const total = areas.reduce((n, a) => n + a.active_memory_count, 0);

  return (
    <svg
      role="img"
      aria-label={`Your brain map: ${placed.map((a) => `${regionLabel(a.domain)} ${a.active_memory_count} neurons`).join(', ')}`}
      viewBox="22 4 330 256"
      width="100%"
      style={{ display: 'block' }}
    >
      <path d={OUTLINE} fill="var(--surface-2)" stroke="var(--line-strong)" strokeWidth="1.5" />
      <g stroke="var(--line-strong)" strokeWidth="1" opacity="0.8">
        {placed.map((a, i) => {
          const n = placed[(i + 1) % placed.length];
          return placed.length > 1 ? <line key={`l${i}`} x1={a.x} y1={a.y} x2={n.x} y2={n.y} /> : null;
        })}
      </g>
      {placed.map((a, i) => {
        const color = regionColor(a.domain);
        const r = 7 + Math.min(a.active_memory_count, 24) * 0.55;
        const sats = Math.min(a.active_memory_count, 7);
        return (
          <motion.g
            key={a.domain}
            initial={{ opacity: 0, scale: 0.6 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.08 * i, duration: 0.35 }}
            style={{ transformOrigin: `${a.x}px ${a.y}px`, cursor: 'pointer' }}
            onClick={() => onOpen(a.domain)}
          >
            {Array.from({ length: sats }).map((_, k) => {
              const ang = (k / Math.max(sats, 1)) * Math.PI * 2;
              const d = r + 10;
              return <circle key={k} cx={a.x + Math.cos(ang) * d} cy={a.y + Math.sin(ang) * d} r="2.6" fill={color} opacity="0.75" />;
            })}
            <circle cx={a.x} cy={a.y} r={r} fill={color} opacity={a.active_memory_count ? 1 : 0.35} />
            {a.has_pending_proposal && (
              <circle cx={a.x} cy={a.y} r={r + 18} fill="none" stroke="var(--thought)" strokeWidth="1.5" strokeDasharray="3 4" />
            )}
            <text
              x={a.x}
              y={a.y + r + 28}
              textAnchor="middle"
              fontFamily="var(--sans)"
              fontSize="12"
              fontWeight="600"
              fill="var(--text)"
            >
              {regionLabel(a.domain)}
            </text>
          </motion.g>
        );
      })}
      {total === 0 && (
        <text x="180" y="138" textAnchor="middle" fontFamily="var(--serif)" fontSize="18" fill="var(--muted)">
          Talk to yourself and this lights up
        </text>
      )}
    </svg>
  );
}
