import { create } from 'zustand';

function savedCapsule(): string {
  try {
    const value = window.localStorage.getItem('ai4r.conversation-capsule') || '';
    return ['document-analyst', 'research-brief'].includes(value) ? value : '';
  } catch { return ''; }
}

export const useCodexSubscription = create<{
  enabled: boolean;
  state: string;
  model: string;
  capsule: string;
  set: (value: Partial<{ enabled: boolean; state: string; model: string; capsule: string }>) => void;
}>((set) => ({ enabled: false, state: 'checking', model: '', capsule: savedCapsule(), set: (value) => {
  if (value.capsule !== undefined) {
    try { window.localStorage.setItem('ai4r.conversation-capsule', value.capsule); } catch { /* Browser storage may be unavailable. */ }
  }
  set(value);
} }));
