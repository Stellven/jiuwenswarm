import type { SessionSnapshot } from './api';

export function sessionStatus(session: SessionSnapshot | null | undefined, stale = false) {
  if (stale) return 'unavailable';
  return session?.status ?? 'loading';
}

export function sessionElapsed(seconds: number | null | undefined) {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return null;
  const minutes = Math.floor(seconds / 60);
  return [Math.floor(minutes / 60), minutes % 60, Math.floor(seconds % 60)]
    .map((part) => String(part).padStart(2, '0'))
    .join(':');
}
