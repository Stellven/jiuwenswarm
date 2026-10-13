import { create } from 'zustand';

export const useCodexSubscription = create<{
  enabled: boolean;
  state: string;
  model: string;
  set: (value: Partial<{ enabled: boolean; state: string; model: string }>) => void;
}>((set) => ({ enabled: false, state: 'checking', model: '', set }));
