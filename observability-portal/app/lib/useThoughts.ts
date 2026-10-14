'use client';

import { useCallback, useEffect, useState } from 'react';
import { api, Memory, ProfileEntry } from './api';

// Everything waiting for the user's yes/no: drafts your brain wrote for a
// region (pending profile proposals) and small things it heard you say that
// need your confirmation (candidate / requires_confirmation memories).

export type Thought =
  | { kind: 'thought'; id: string; domain: string; text: string; entry: ProfileEntry }
  | { kind: 'memory'; id: string; domain: string | null; text: string; memory: Memory };

export function useThoughts(email: string) {
  const [thoughts, setThoughts] = useState<Thought[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [pending, needsConfirm, candidates] = await Promise.all([
        api.pending(email),
        api.memories(email, { status: 'requires_confirmation' }).catch(() => [] as Memory[]),
        api.memories(email, { status: 'candidate' }).catch(() => [] as Memory[]),
      ]);
      setThoughts([
        ...pending.map((e): Thought => ({ kind: 'thought', id: e.profile_entry_id, domain: e.domain, text: e.content, entry: e })),
        ...[...needsConfirm, ...candidates].map(
          (m): Thought => ({ kind: 'memory', id: m.memory_id, domain: m.domain, text: m.content, memory: m }),
        ),
      ]);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load new thoughts.');
    }
  }, [email]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const act = useCallback(
    async (t: Thought, fn: () => Promise<unknown>) => {
      setBusyId(t.id);
      try {
        await fn();
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : 'That didn’t go through. Try again.');
      } finally {
        setBusyId(null);
      }
    },
    [refresh],
  );

  const yes = (t: Thought) => act(t, () => (t.kind === 'thought' ? api.accept(email, t.id) : api.confirmMemory(email, t.id)));
  const no = (t: Thought) => act(t, () => (t.kind === 'thought' ? api.reject(email, t.id) : api.suppressMemory(email, t.id)));
  const refine = (t: Thought, words: string) => act(t, () => api.refine(email, t.id, words));

  return { thoughts, busyId, error, refresh, yes, no, refine };
}
