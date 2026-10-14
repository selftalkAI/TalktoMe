# selfie.Me design system — "Inner Voice"

The app is a self-talk app that slowly builds a model of the user's own mind.
It should feel like a quiet, luminous room at night where your thoughts
become visible — never like a productivity tool or a chatbot.

## Language (never show internal names)

| Internal | What the user sees |
|---|---|
| Brain 1 | **you** |
| Brain 2 | **your brain** / "your second brain" |
| moment | something you said / a thought |
| profile entry (accepted) | what your brain knows |
| proposal (pending) | **a new thought** |
| memory (active) | a neuron |
| domain / key area | a **region** (Reading, Learning, Feelings, Skills, …) |
| accept / refine / reject | **That's me** / **Not quite** / **That's not me** |

The one promise, repeated wherever a proposal appears:
*Nothing joins your brain until you say so.*

## Tokens (`app/globals.css`)

Two themes on the same tokens: `dusk` (default, dark) and `day` (light),
set by `data-theme` on `<html>`.

| Token | Dusk | Day | Use |
|---|---|---|---|
| `--bg` | #0E1915 | #F5F2EA | page |
| `--surface` | #15241F | #FFFFFF | cards, composer |
| `--surface-2` | #1B2C25 | #EEF2EC | your bubbles, rows |
| `--line` | #23392F | #E3DDCF | hairlines |
| `--text` | #EDE8DD | #1C2B24 | body |
| `--muted` | #8FA89C | #5E7368 | labels, meta |
| `--accent` | #9FD8B5 | #1F6B4C | primary action, "you are here" |
| `--thought` | #E8B86B | #A8641F | new thoughts, insights |
| `--on-accent` / `--on-thought` | dark ink | white | text on those fills |

Region colors (`regionColor()` in `app/lib/brain.ts`): Reading amber,
Learning mint, Feelings sky, Skills violet; any custom region gets a stable
color from its name.

## Type

- **Instrument Serif** — your brain's voice: greetings, brain replies,
  "what your brain knows", thought statements. Sizes 22–44px, weight 400,
  italic for one emphasised word at most.
- **DM Sans** — everything the user types and all UI. 13–16px; labels are
  12px uppercase with 0.1em tracking.

Rule of thumb: **serif = the brain speaking, sans = you and the interface.**

## Shape and motion

- Radius: 28px cards, 22–26px pill buttons and inputs, 999px chips.
- Touch targets ≥ 44px. Bottom tab bar floats 16px from the edges.
- No drop shadows or gradient washes. Depth comes from surface steps and the
  neural orb.
- Motion (framer-motion): bubbles rise 8px and fade in (220ms); the orb
  "breathes" while your brain is thinking; respect `prefers-reduced-motion`.

## Components (`app/components/`)

`NeuralOrb` · `TabBar` · `Bubble` · `ThoughtCard` · `RegionMap` ·
`Sheet` (bottom sheet) · `WeekStory` (full-screen story).
Compose new screens from these before inventing new pieces.

## Accessibility

Real `<button>`/`<input>`/`<label>`, `aria-label` on icon-only buttons,
text contrast ≥ 4.5:1 in both themes, emoji never carry meaning.
