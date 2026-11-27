import type { RunList } from './api';

declare const __MUSE_STATIC_BUILD__: boolean;

type StaticRecord = { status: number; contentType: string; body: unknown };

declare global {
  interface Window {
    __MUSE_STATIC__?: Record<string, StaticRecord>;
  }
}

export const staticBuild = typeof __MUSE_STATIC_BUILD__ !== 'undefined' && __MUSE_STATIC_BUILD__;

function staticRecord(path: string) {
  const [pathname, search] = path.split('?', 2);
  const query = new URLSearchParams(search);
  query.sort();
  const canonical = query.toString();
  const key = canonical ? `${pathname}?${canonical}` : pathname;
  const records = window.__MUSE_STATIC__;
  return records && Object.prototype.hasOwnProperty.call(records, key) ? records[key] : undefined;
}

export function hasStaticRun(id: string) {
  const list = staticRecord('/api/factory/runs')?.body as RunList | undefined;
  const entry = staticRecord(`/api/factory/runs/${encodeURIComponent(id)}`);
  return entry?.status === 200 && Boolean(list?.runs.some((run) => run.id === id));
}

export async function staticJson<T>(path: string, init?: RequestInit): Promise<T> {
  if (init?.signal?.aborted) throw new DOMException('The request was aborted.', 'AbortError');
  if (init?.method && init.method !== 'GET') throw new Error('This static copy is read-only.');
  const entry = staticRecord(path);
  if (!entry) throw new Error('This record is unavailable in the static copy.');
  if (entry.status < 200 || entry.status >= 300) {
    const body = entry.body as { detail?: string; error?: string } | undefined;
    throw new Error(body?.detail || body?.error || `Record unavailable (${entry.status}).`);
  }
  return entry.body as T;
}
