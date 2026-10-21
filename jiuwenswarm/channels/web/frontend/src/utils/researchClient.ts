/** Native M1 client. Authentication scopes and acceptance remain server-owned. */
export interface ResearchRef {
  id: string;
  sha256: string;
}
export interface ResearchDefaults {
  account_id: string;
  workspace_id: string | null;
  configuration_ref: ResearchRef | null;
  inputs_ready?: boolean;
  plan_source?: 'static' | 'planned' | null;
  profile_id?: string | null;
}
interface ResearchSession {
  token: string;
  defaults: ResearchDefaults;
  bootstrap?: string;
}

const SESSION_KEY = 'ai4r.native-session';
const BOOTSTRAP_KEY = 'ai4r.local-bootstrap';
let bootstrapPromise: Promise<boolean> | null = null;

function validSession(value: unknown): value is ResearchSession {
  if (!value || typeof value !== 'object') return false;
  const parsed = value as Partial<ResearchSession>;
  const defaults = parsed.defaults;
  if (
    typeof parsed.token !== 'string' ||
    !parsed.token ||
    !defaults ||
    typeof defaults.account_id !== 'string' ||
    !defaults.account_id
  )
    return false;
  if (defaults.workspace_id !== null && (typeof defaults.workspace_id !== 'string' || !defaults.workspace_id))
    return false;
  const ref = defaults.configuration_ref;
  if (defaults.inputs_ready !== undefined && typeof defaults.inputs_ready !== 'boolean') return false;
  return (
    ref === null ||
    (typeof ref === 'object' &&
      ref !== null &&
      typeof ref.id === 'string' &&
      !!ref.id &&
      typeof ref.sha256 === 'string' &&
      /^[a-f0-9]{64}$/.test(ref.sha256))
  );
}

function session(): ResearchSession | null {
  try {
    const value = window.sessionStorage.getItem(SESSION_KEY);
    if (!value) return null;
    const parsed: unknown = JSON.parse(value);
    return validSession(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function hasResearchSession(): boolean {
  return session() !== null;
}

export function hasResearchConfiguration(): boolean {
  return session()?.defaults.configuration_ref != null;
}

export function hasResearchInputs(): boolean {
  const defaults = session()?.defaults;
  return defaults?.inputs_ready ?? defaults?.configuration_ref != null;
}

export function researchWorkspace(): string {
  const workspace = session()?.defaults.workspace_id;
  if (!workspace) throw new Error('Approved native workspace is unavailable');
  return workspace;
}

function runHandleKey(): string {
  const current = session();
  if (!current) throw new Error('Native research authentication required');
  return 'ai4r.run-handles:' + JSON.stringify([current.defaults.account_id, current.defaults.workspace_id]);
}
export function researchRunHandles(sessionId: string): string[] {
  try {
    const rows: unknown = JSON.parse(window.sessionStorage.getItem(runHandleKey()) ?? '[]');
    if (!Array.isArray(rows)) return [];
    return rows
      .filter((row) => row && row.sessionId === sessionId && typeof row.runId === 'string')
      .map((row) => row.runId);
  } catch {
    return [];
  }
}
export function rememberResearchRun(sessionId: string, runId: string): void {
  const key = runHandleKey();
  let rows: { sessionId: string; runId: string }[] = [];
  try {
    const value = JSON.parse(window.sessionStorage.getItem(key) ?? '[]');
    if (Array.isArray(value))
      rows = value.filter((row) => row && typeof row.sessionId === 'string' && typeof row.runId === 'string');
  } catch {
    /* Corrupt local pointers never become research authority. */
  }
  if (!rows.some((row) => row.sessionId === sessionId && row.runId === runId)) rows.push({ sessionId, runId });
  window.sessionStorage.setItem(key, JSON.stringify(rows));
}

const inputSelections = new Map<string, string[]>();
const inputBusy = new Set<string>();
export function selectedResearchInputs(sessionId: string): string[] {
  if (inputBusy.has(sessionId)) throw new Error('Wait for the controlled upload to finish');
  return [...(inputSelections.get(sessionId) ?? [])];
}
export function selectResearchInputs(sessionId: string, ids: string[]): void {
  inputSelections.set(sessionId, [...new Set(ids)]);
  window.dispatchEvent?.(
    new CustomEvent('research.inputs.changed', { detail: { sessionId, ids: inputSelections.get(sessionId) } }),
  );
}
export function markResearchUpload(sessionId: string, busy: boolean): void {
  if (busy) inputBusy.add(sessionId);
  else inputBusy.delete(sessionId);
}

export interface ResearchUpload {
  id: string;
  filename: string;
  kind: 'docs' | 'repo' | 'datasets';
  status: string;
  content_sha256: string;
  text_sha256: string | null;
}
export async function uploadResearchInput(kind: ResearchUpload['kind'], file: File): Promise<ResearchUpload> {
  const body = new FormData();
  body.set('scope_id', researchWorkspace());
  body.set('file', file);
  return await researchRequest<ResearchUpload>(`/api/v1/inputs/${kind}`, { method: 'POST', body });
}

export async function bootstrapResearchSession(): Promise<boolean> {
  if (bootstrapPromise) return bootstrapPromise;
  const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ''));
  const challenge =
    fragment.get('research_bootstrap') || session()?.bootstrap || window.sessionStorage.getItem(BOOTSTRAP_KEY);
  if (!challenge) return session() !== null;
  bootstrapPromise = (async () => {
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
    window.sessionStorage.removeItem(SESSION_KEY);
    const response = await fetch('/auth/research/bootstrap', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ challenge }),
    });
    if (!response.ok) {
      if (response.status === 401 || response.status === 403) window.sessionStorage.removeItem(BOOTSTRAP_KEY);
      throw new Error('Native research authentication failed');
    }
    const value: unknown = await response.json();
    if (!validSession(value)) {
      throw new Error('Native research authentication is invalid');
    }
    const reusable = (value as ResearchSession & { reusable_bootstrap?: boolean }).reusable_bootstrap === true;
    if (reusable) window.sessionStorage.setItem(BOOTSTRAP_KEY, challenge);
    else window.sessionStorage.removeItem(BOOTSTRAP_KEY);
    window.sessionStorage.setItem(
      SESSION_KEY,
      JSON.stringify({ ...value, ...(reusable ? { bootstrap: challenge } : {}) }),
    );
    return true;
  })();
  try {
    return await bootstrapPromise;
  } finally {
    bootstrapPromise = null;
  }
}

export async function researchFetch(path: string, options: RequestInit = {}): Promise<Response> {
  if (!path.startsWith('/api/v1/') && !path.startsWith('/auth/research/'))
    throw new Error('Unsupported research operation');
  const target = new URL(path, window.location.origin);
  if (
    target.origin !== window.location.origin ||
    (!target.pathname.startsWith('/api/v1/') && !target.pathname.startsWith('/auth/research/'))
  )
    throw new Error('Foreign research origin refused');
  const current = session();
  if (!current) throw new Error('Native research authentication required');
  const headers = new Headers(options.headers);
  headers.set('Authorization', `Bearer ${current.token}`);
  if (typeof options.body === 'string') headers.set('Content-Type', 'application/json');
  const response = await fetch(target.pathname + target.search, {
    ...options,
    headers: Object.fromEntries(headers),
    credentials: 'same-origin',
    redirect: 'error',
  });
  if (!response.ok) {
    if (response.status === 401) window.sessionStorage.removeItem(SESSION_KEY);
    const error = new Error(`Research request failed (${response.status})`) as Error & { status: number };
    error.status = response.status;
    throw error;
  }
  return response;
}

export async function researchRequest<T = Record<string, unknown>>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  return (await (await researchFetch(path, options)).json()) as T;
}

export async function submitResearchIntake(
  intake_ref: ResearchRef,
  client_request_id: string,
): Promise<Record<string, unknown>> {
  const defaults = session()?.defaults;
  if (!defaults?.workspace_id || !defaults.configuration_ref)
    throw new Error('Approved native research configuration is unavailable');
  const body = {
    schema_version: '1.0.0',
    id: client_request_id,
    client_request_id,
    account_id: defaults.account_id,
    workspace_id: defaults.workspace_id,
    intake_ref,
    configuration_ref: defaults.configuration_ref,
    plan_source: defaults.plan_source ?? 'static',
    interaction_mode: 'interactive',
    ...(defaults.profile_id ? { profile_id: defaults.profile_id } : {}),
  };
  try {
    return await researchRequest('/api/v1/runs', { method: 'POST', body: JSON.stringify(body) });
  } catch (original) {
    const status = (original as { status?: number })?.status;
    if (status && status >= 400 && status < 500) throw original;
    // A lost response is reconciled; this function never blindly repeats POST.
    try {
      const found = await researchRequest<Record<string, unknown>>(
        `/api/v1/runs?client_request_id=${encodeURIComponent(client_request_id)}`,
      );
      if (
        !found ||
        Array.isArray(found) ||
        typeof found.run_id !== 'string' ||
        found.client_request_id !== client_request_id
      )
        throw original;
      return found;
    } catch {
      throw original;
    }
  }
}

export async function downloadResearchExport(
  runId: string,
  audience: 'researcher' | 'reviewer' = 'researcher',
): Promise<void> {
  const response = await researchFetch(`/api/v1/runs/${encodeURIComponent(runId)}/export?audience=${audience}`, {
    headers: { Accept: 'application/zip' },
  });
  if (!(response.headers.get('content-type') ?? '').includes('application/zip'))
    throw new Error('Research export encoding is unavailable');
  const url = URL.createObjectURL(await response.blob());
  try {
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'run_export.zip';
    anchor.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function logoutResearchSession(): Promise<void> {
  try {
    await researchRequest('/auth/research/logout', { method: 'POST' });
  } finally {
    window.sessionStorage.removeItem(SESSION_KEY);
  }
}
