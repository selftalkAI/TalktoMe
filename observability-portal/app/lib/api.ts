// Typed client for the Orchestration Service. Every screen talks to the
// backend only through these functions, so the UI never guesses a route.

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000';

export type Profile = {
  email: string;
  full_name: string;
  dob: string | null;
  location: string | null;
  interests: string[];
  other_interests: string | null;
  photo_data_url: string | null;
  quote: string | null;
  mood_summary?: string | null;
  created_at?: string;
};

export type NewProfile = {
  email: string;
  full_name: string;
  password: string;
  dob: string | null;
  location: string | null;
  interests: string[];
  other_interests: string | null;
  photo_data_url: string | null;
  quote: string | null;
};

export type Moment = {
  id: string;
  created_at: string;
  source: string;
  content: string;
  mood: string | null;
  photo_data_url: string | null;
  reflection: string | null;
};

export type Memory = {
  memory_id: string;
  type: string;
  domain: string | null;
  content: string;
  status: string;
  sensitivity_tier: string;
  created_at: string;
};

export type ProfileEntry = {
  profile_entry_id: string;
  domain: string;
  version: number;
  content: string;
  status: 'proposed' | 'accepted' | 'superseded' | 'rejected';
  proposed_at: string;
  accepted_at: string | null;
};

export type KeyArea = {
  domain: string;
  is_key_area: boolean;
  accepted_entry: ProfileEntry | null;
  version: number;
  active_memory_count: number;
  has_pending_proposal: boolean;
};

export type Evolution = {
  range_days: number;
  total_moments_all_time: number;
  moments_in_range: number;
  moments_today: number;
  mood_counts_in_range: Record<string, number>;
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "Can't reach selfie.Me. Is the orchestration service running?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === 'string' ? body.detail : detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

const q = (email: string) => `profile_email=${encodeURIComponent(email)}`;
const post = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) });

export const api = {
  // Who you are
  getProfile: (email: string) => call<Profile>(`/api/v1/profiles/${encodeURIComponent(email)}`),
  login: (email: string, password: string) =>
    call<Profile>(`/api/v1/profiles/${encodeURIComponent(email)}/login`, post({ password })),
  createProfile: (p: NewProfile) => call<Profile>('/api/v1/profiles', post(p)),

  // Talking to yourself
  openConversation: (email: string) =>
    call<{ opening_message: string }>(`/api/v1/profiles/${encodeURIComponent(email)}/conversation/open`, post({})),
  listMoments: (email: string) => call<Moment[]>(`/api/v1/moments?${q(email)}`),
  addMoment: (email: string, content: string, source: 'text' | 'voice', mood: string | null) =>
    call<Moment>('/api/v1/moments', post({ profile_email: email, source, content, mood })),
  reflect: (email: string, momentId: string) =>
    call<{ reflection: string; referenced_past_count: number }>(
      `/api/v1/moments/${momentId}/reflect?${q(email)}`,
      { method: 'POST' },
    ),

  // What your brain knows
  keyAreas: (email: string) => call<KeyArea[]>(`/api/v1/brain1/${encodeURIComponent(email)}/key-areas`),
  region: (email: string, domain: string) =>
    call<{ domain: string; accepted: ProfileEntry | null; history: ProfileEntry[] }>(
      `/api/v1/brain2/profile/${encodeURIComponent(domain)}?${q(email)}`,
    ),
  memories: (email: string, opts: { status?: string; domain?: string } = {}) => {
    const params = [q(email), `status=${encodeURIComponent(opts.status ?? 'active')}`];
    if (opts.domain) params.push(`domain=${encodeURIComponent(opts.domain)}`);
    return call<Memory[]>(`/api/v1/memories?${params.join('&')}`);
  },
  confirmMemory: (email: string, id: string) =>
    call<Memory>(`/api/v1/memories/${id}/confirm?${q(email)}`, { method: 'PATCH' }),
  suppressMemory: (email: string, id: string) =>
    call<Memory>(`/api/v1/memories/${id}/suppress?${q(email)}`, { method: 'PATCH' }),
  forgetMemory: (email: string, id: string) =>
    call<Memory>(`/api/v1/memories/${id}?${q(email)}`, { method: 'DELETE' }),

  // New thoughts (proposals) — only your tap makes them stick
  pending: (email: string) => call<ProfileEntry[]>(`/api/v1/brain2/pending?${q(email)}`),
  accept: (email: string, id: string) =>
    call<ProfileEntry>(`/api/v1/brain2/profile/proposals/${id}/accept`, post({ profile_email: email })),
  reject: (email: string, id: string) =>
    call<ProfileEntry>(`/api/v1/brain2/profile/proposals/${id}/reject`, post({ profile_email: email })),
  refine: (email: string, id: string, words: string) =>
    call<ProfileEntry>(
      `/api/v1/brain2/profile/proposals/${id}/refine`,
      post({ profile_email: email, additional_reflection: words }),
    ),
  askRegion: (email: string, domain: string, words: string) =>
    call<ProfileEntry>(
      `/api/v1/brain2/profile/${encodeURIComponent(domain)}/proposal`,
      post({ profile_email: email, user_reflection: words }),
    ),
  thinkNow: () => call<{ drafted_count: number }>('/api/v1/brain2/scheduler/run-now', { method: 'POST' }),

  // How your mind changed
  evolution: (email: string, days = 7) => call<Evolution>(`/api/v1/evolution?${q(email)}&days=${days}`),
  evolutionNarrative: (email: string, days = 7) =>
    call<{ narrative: string }>(`/api/v1/evolution/narrative?${q(email)}&days=${days}`),
};
