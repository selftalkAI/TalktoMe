# selfie.Me — UI Design Document

## Welcome / Daily Check-in Screen

Status: Implemented (`frontend/app/page.tsx`)

### Purpose

This is the first screen a user sees when opening the app. Before landing
in the main dashboard, it asks a single, low-friction question — "what's
on your mind right now?" — so the app captures a moment of reflection
before anything else competes for attention.

### Origin

Based on an initial wireframe: a centered card with a greeting heading
("Hi You") above a labeled input area ("What's your Thoughts"). The
implementation keeps that structure but restyles it to match the app's
existing dark theme rather than the flat mockup colors.

### Layout

```
┌─────────────────────────────────────┐
│                                       │
│               Hi You                 │
│   Take a moment to check in with     │
│         yourself before you dive in. │
│                                       │
│  ┌─────────────────────────────────┐ │
│  │ What's your Thoughts             │ │
│  │                                   │ │
│  │                                   │ │
│  └─────────────────────────────────┘ │
│                                       │
│      [ Continue ]  [ Skip for now ]  │
│                                       │
└─────────────────────────────────────┘
```

- Full-viewport, centered card (`.welcome-shell` / `.welcome-card`),
  max-width 560px, so it reads as a single focused moment rather than a
  dashboard.
- Heading ("Hi You") is the largest element on the page — greeting comes
  first, task second.
- One free-text textarea, placeholder "What's your Thoughts", 6 rows,
  autofocused so typing can start immediately.
- Two actions: a primary "Continue" button (submits and advances) and a
  secondary, low-emphasis "Skip for now" link-style button for users who
  don't want to write anything right now.

### Visual style

Reuses the existing design tokens from `frontend/app/globals.css`:

| Token | Value | Use |
| --- | --- | --- |
| `--bg` | `#07141d` | page background |
| `--panel` | `rgba(9, 21, 31, 0.88)` | card background |
| `--panel-border` | `rgba(151, 214, 255, 0.18)` | card + input borders |
| `--text` | `#ebf8ff` | primary text |
| `--muted` | `#b5d6eb` | subtitle / placeholder text |
| `--primary` | `#5cc8ff` | primary button, focus ring |

Card: 24px border radius, soft drop shadow, 1px border in
`--panel-border`. Textarea matches the same border/radius language as
the rest of the app's inputs, with a `--primary`-colored focus outline.

### Behavior

1. User types a thought into the textarea (optional).
2. **Continue**: if there's text, it's POSTed to `/api/v1/captures` as
   `{ source: "text", content: <thought>, tags: ["daily-check-in"] }`,
   then the user is routed to `/dashboard`. If the request fails, an
   inline error message appears ("Could not save that right now. You can
   still continue.") but the user is not blocked from moving on.
   If the field is empty, Continue just routes to `/dashboard`.
3. **Skip for now**: routes straight to `/dashboard` without saving
   anything.

### Relationship to the rest of the app

The previous home page (capture form, memory overview, belief evolution,
reflection panel) moved from `/` to `/dashboard` unchanged, and now has a
"← New check-in" link back to this welcome screen. This screen is
additive — it doesn't replace any existing functionality, it just gives
the app a calmer entry point before the dashboard.

### Open questions / future iterations

- Personalize "Hi You" with the actual user's name once auth/profile
  data exists.
- Decide whether every app open should show this screen, or only once
  per day ("daily check-in" framing implies the latter).
- Consider surfacing the saved thought back to the user on the dashboard
  immediately after Continue, so the capture feels acknowledged.
