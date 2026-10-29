/** Native M1 client. Authentication scopes and acceptance remain server-owned. */
import i18n from '../i18n';

export interface ResearchRef {
  id: string;
  sha256: string;
}
export interface ResearchDefaults {
  account_id: string;
  workspace_id: string | null;
  configuration_ref: ResearchRef | null;
  inputs_ready?: boolean;
  local_chat_ready?: boolean;
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
const STATUS_CACHE_MS = 5_000;
const CONNECTION_TIMEOUT_MS = 15_000;
let runtimeRead: { identity: string; promise: Promise<ResearchRuntime> } | null = null;
let runtimeSnapshot: { identity: string; value: ResearchRuntime; capturedAt: number } | null = null;

function sessionIdentity(value: ResearchSession): string {
  const { defaults } = value;
  return JSON.stringify([value.token, defaults.account_id, defaults.workspace_id,
    defaults.configuration_ref?.id, defaults.configuration_ref?.sha256]);
}

async function boundedConnection<T>(operation: (signal: AbortSignal) => Promise<T>, messageKey: string): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), CONNECTION_TIMEOUT_MS);
  try {
    return await operation(controller.signal);
  } catch (error) {
    if (controller.signal.aborted) throw new Error(i18n.t(messageKey));
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

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

export interface ResearchRuntime {
  configured: boolean;
  ready: boolean;
  defaults: ResearchDefaults;
  example_available: boolean;
}

/** Refresh server-owned defaults after initialization without another login. */
export async function refreshResearchRuntime({ force = false }: { force?: boolean } = {}): Promise<ResearchRuntime> {
  const current = session();
  if (!current) throw new Error('Native research authentication required');
  const identity = sessionIdentity(current);
  if (runtimeRead?.identity === identity) return runtimeRead.promise;
  if (!force && runtimeSnapshot?.identity === identity && runtimeSnapshot.value.ready
      && Date.now() - runtimeSnapshot.capturedAt < STATUS_CACHE_MS) return runtimeSnapshot.value;
  const promise = (async () => {
    const value = await boundedConnection(
      (signal) => researchRequest<ResearchRuntime>('/api/v1/workflow/runtime', { signal }),
      'researchWorkflow.runtimeTimeout',
    );
    const actual = session();
    const next = actual && { ...actual, defaults: value.defaults };
    if (!actual || sessionIdentity(actual) !== identity || !validSession(next)
        || value.defaults.account_id !== actual.defaults.account_id)
      throw new Error('Research runtime belongs to another or invalid session');
    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(next));
    runtimeSnapshot = value.ready ? { identity: sessionIdentity(next), value, capturedAt: Date.now() } : null;
    window.dispatchEvent(new CustomEvent('research.runtime.changed'));
    return value;
  })();
  runtimeRead = { identity, promise };
  try {
    return await promise;
  } finally {
    if (runtimeRead?.promise === promise) runtimeRead = null;
  }
}

/** Upload the real tutorial note and prefill a request; never dispatch a run. */
export async function prepareResearchExample(sessionId: string): Promise<string> {
  await refreshResearchRuntime();
  const example = await researchRequest<{ filename: string; request: string; guide: string; guide_ref: ResearchRef }>('/api/v1/workflow/example');
  const uploads = await researchRequest<ResearchUpload[]>(`/api/v1/inputs?scope_id=${encodeURIComponent(researchWorkspace())}`);
  rememberResearchUploads(uploads);
  const existing = uploads.find((item) => item.status === 'uploaded' && item.kind === 'docs' && item.content_sha256 === example.guide_ref.sha256);
  const uploaded = existing ?? await uploadResearchInput('docs', new File([example.guide], example.filename, { type: 'text/markdown' }));
  if (uploaded.content_sha256 !== example.guide_ref.sha256) throw new Error('Research example upload identity differs');
  selectResearchInputs(sessionId, [...selectedResearchInputs(sessionId), uploaded.id]);
  selectResearchInteraction(sessionId, 'research');
  window.dispatchEvent(new CustomEvent('research.runtime.changed'));
  return example.request;
}

export function hasResearchInputs(): boolean {
  const defaults = session()?.defaults;
  return defaults?.inputs_ready ?? defaults?.configuration_ref != null;
}

export function hasLocalChat(): boolean {
  return session()?.defaults.local_chat_ready === true;
}

export type ResearchInteraction = 'conversation' | 'research';

function interactionChoiceKey(sessionId: string): string {
  return `ai4r.interaction:v2:${inputOwnerScope()}:${sessionId}`;
}

/** Legacy values also held inferred defaults, so only versioned explicit choices opt in. */
function explicitResearchInteraction(sessionId: string): ResearchInteraction | null {
  try {
    const raw = window.sessionStorage.getItem(interactionChoiceKey(sessionId));
    const value = raw ? JSON.parse(raw) : null;
    if (value?.version === 2 && value.explicit === true
        && (value.mode === 'conversation' || value.mode === 'research')) return value.mode;
  } catch { /* Storage is optional; permission is never inferred from it. */ }
  return null;
}

/** A configured AI4R workspace uses its real workflow unless the user explicitly chooses direct chat. */
export function researchInteraction(sessionId: string): ResearchInteraction {
  return explicitResearchInteraction(sessionId)
    ?? (hasResearchConfiguration() || !hasLocalChat() ? 'research' : 'conversation');
}

export function selectResearchInteraction(sessionId: string, mode: ResearchInteraction, explicit = true): void {
  const key = interactionChoiceKey(sessionId);
  if (explicit) window.sessionStorage.setItem(key, JSON.stringify({ version: 2, explicit: true, mode }));
  else window.sessionStorage.removeItem(key);
  window.sessionStorage.removeItem(`ai4r.interaction:${sessionId}`);
}

export function researchWorkspace(): string {
  const workspace = session()?.defaults.workspace_id;
  if (!workspace) throw new Error('Approved native workspace is unavailable');
  return workspace;
}
export function researchAccount(): string {
  const account = session()?.defaults.account_id;
  if (!account) throw new Error('Native research authentication required');
  return account;
}

function runHandleKey(): string {
  const current = session();
  if (!current) throw new Error('Native research authentication required');
  return 'ai4r.run-handles:' + JSON.stringify([current.defaults.account_id, current.defaults.workspace_id]);
}
function savedRunHandles(key: string): string {
  try {
    const value = window.localStorage.getItem(key);
    if (value !== null) return value;
  } catch { /* Session storage remains usable when persistent storage is blocked. */ }
  return window.sessionStorage.getItem(key) ?? '[]';
}
export function researchRunHandles(sessionId: string): string[] {
  try {
    const rows: unknown = JSON.parse(savedRunHandles(runHandleKey()));
    if (!Array.isArray(rows)) return [];
    return rows
      .filter((row) => row && row.sessionId === sessionId && typeof row.runId === 'string')
      .map((row) => row.runId);
  } catch {
    return [];
  }
}
export function rememberResearchRun(sessionId: string, runId: string, requestId?: string): void {
  const key = runHandleKey();
  let rows: { sessionId: string; runId: string; requestId?: string }[] = [];
  try {
    const value = JSON.parse(savedRunHandles(key));
    if (Array.isArray(value))
      rows = value.filter((row) => row && typeof row.sessionId === 'string' && typeof row.runId === 'string');
  } catch {
    /* Corrupt local pointers never become research authority. */
  }
  const prior = rows.find((row) => row.sessionId === sessionId && row.runId === runId);
  if (!prior) rows.push({ sessionId, runId, ...(requestId ? { requestId } : {}) });
  else if (requestId) prior.requestId = requestId;
  // Local pointers contain no bearer, prompt, artifact bytes or authority.
  try { window.localStorage.setItem(key, JSON.stringify(rows)); }
  catch { window.sessionStorage.setItem(key, JSON.stringify(rows)); }
}

export function researchRunRequest(runId: string): { sessionId: string; requestId: string } | null {
  try {
    const rows = JSON.parse(savedRunHandles(runHandleKey()));
    if (!Array.isArray(rows)) return null;
    const row = rows.find((item) => item && item.runId === runId && typeof item.sessionId === 'string' && typeof item.requestId === 'string');
    return row ? { sessionId: row.sessionId, requestId: row.requestId } : null;
  } catch { return null; }
}

const inputSelections = new Map<string, string[]>();
const inputSelectionVersions = new Map<string, Map<string, number>>();
let inputSelectionVersion = 0;
const knownUploads = new Map<string, Map<string, ResearchUpload>>();
function inputOwnerScope(): string {
  const defaults = session()?.defaults;
  return JSON.stringify([defaults?.account_id ?? null, defaults?.workspace_id ?? null]);
}
/** Display metadata only, captured from actual authenticated upload responses. */
export function rememberResearchUploads(rows: ResearchUpload[], replace = false): void {
  const key = inputOwnerScope();
  const uploads = replace ? new Map<string, ResearchUpload>() : knownUploads.get(key) ?? new Map<string, ResearchUpload>();
  for (const row of rows) uploads.set(row.id, { ...row });
  knownUploads.set(key, uploads);
}
export function forgetResearchUpload(id: string): void {
  knownUploads.get(inputOwnerScope())?.delete(id);
}
const inputBusy = new Set<string>();
export function selectedResearchInputs(sessionId: string): string[] {
  if (inputBusy.has(sessionId)) throw new Error('Wait for the controlled upload to finish');
  return [...(inputSelections.get(sessionId) ?? [])];
}
export function selectResearchInputs(sessionId: string, ids: string[]): void {
  const previous = inputSelectionVersions.get(sessionId);
  const unique = [...new Set(ids)];
  inputSelectionVersions.set(sessionId, new Map<string, number>(unique.map((id) =>
    [id, previous?.get(id) ?? ++inputSelectionVersion])));
  inputSelections.set(sessionId, unique);
  window.dispatchEvent?.(
    new CustomEvent('research.inputs.changed', { detail: { sessionId, ids: inputSelections.get(sessionId) } }),
  );
}
/** Draft edits use the current selection even when an upload completes asynchronously. */
export function updateResearchInputs(sessionId: string, update: (ids: string[]) => string[]): void {
  selectResearchInputs(sessionId, update([...(inputSelections.get(sessionId) ?? [])]));
}
export function captureResearchInputs(
  sessionId: string, explicitRefs?: string[],
): import('../types/websocket').ResearchInputSnapshot {
  const selected = selectedResearchInputs(sessionId);
  const uploadRefs = explicitRefs ? [...explicitRefs] : selected;
  const versions = inputSelectionVersions.get(sessionId);
  return {
    sourceSessionId: sessionId, uploadRefs,
    ownerScope: inputOwnerScope(),
    files: uploadRefs.flatMap((id) => {
      const row = knownUploads.get(inputOwnerScope())?.get(id);
      return row?.status === 'uploaded' ? [{ id, filename: row.filename }] : [];
    }),
    selectionVersions: Object.fromEntries(uploadRefs.flatMap((id) => {
      const version = versions?.get(id);
      return version === undefined ? [] : [[id, version]];
    })),
    interaction: researchInteraction(sessionId),
    interactionExplicit: explicitResearchInteraction(sessionId) !== null,
  };
}
/** Consume only the sent selection generation; later selections remain available. */
export function consumeResearchInputs(
  sessionId: string, snapshot: import('../types/websocket').ResearchInputSnapshot,
): void {
  const versions = inputSelectionVersions.get(sessionId);
  selectResearchInputs(sessionId, (inputSelections.get(sessionId) ?? []).filter((id) =>
    !snapshot.uploadRefs.includes(id) || snapshot.selectionVersions[id] === undefined
      || versions?.get(id) !== snapshot.selectionVersions[id]));
}
export function migrateResearchInputs(
  sessionId: string, snapshot: import('../types/websocket').ResearchInputSnapshot,
): void {
  selectResearchInteraction(sessionId, snapshot.interaction, snapshot.interactionExplicit === true);
  selectResearchInputs(sessionId, [...(inputSelections.get(sessionId) ?? []), ...snapshot.uploadRefs]);
  const versions = inputSelectionVersions.get(sessionId)!;
  for (const id of snapshot.uploadRefs) {
    if (snapshot.selectionVersions[id] !== undefined) versions.set(id, snapshot.selectionVersions[id]);
  }
  if (sessionId !== snapshot.sourceSessionId) consumeResearchInputs(snapshot.sourceSessionId, snapshot);
}
/** A confirmed rejection returns still-known uploads without replacing later draft choices. */
export function restoreResearchInputs(
  sessionId: string, snapshot: import('../types/websocket').ResearchInputSnapshot,
): void {
  if (snapshot.ownerScope !== inputOwnerScope()) return;
  const uploads = knownUploads.get(inputOwnerScope());
  const available = snapshot.uploadRefs.filter((id) => uploads?.get(id)?.status === 'uploaded');
  selectResearchInputs(sessionId, [...(inputSelections.get(sessionId) ?? []), ...available]);
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
  const extension = file.name.includes('.') ? file.name.slice(file.name.lastIndexOf('.')).toLowerCase() : '';
  if (kind === 'docs' && !['.txt', '.md', '.markdown', '.pdf'].includes(extension))
    throw new Error('UPLOAD_DOCUMENT_TYPE');
  if (kind === 'repo' && extension !== '.zip') throw new Error('UPLOAD_REPOSITORY_TYPE');
  if (hasLocalChat() && file.size > 20 * 1024 * 1024) throw new Error('UPLOAD_TOO_LARGE');
  let filename = file.name;
  if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(filename)) {
    const stem = (extension ? filename.slice(0, -extension.length) : filename)
      .normalize('NFKD').replace(/[^A-Za-z0-9_.-]+/g, '_').replace(/^[^A-Za-z0-9]+/, '').slice(0, 80) || 'document';
    const suffix = crypto.getRandomValues(new Uint32Array(1))[0].toString(16).padStart(8, '0');
    filename = `${stem}-${suffix}${extension.replace(/[^a-z0-9.]/g, '').slice(0, 16)}`;
  }
  const body = new FormData();
  body.set('scope_id', researchWorkspace());
  body.set('file', file, filename);
  const uploaded = await researchRequest<ResearchUpload>(`/api/v1/inputs/${kind}`, { method: 'POST', body });
  rememberResearchUploads([uploaded]);
  return uploaded;
}

export async function bootstrapResearchSession(): Promise<boolean> {
  if (bootstrapPromise) return bootstrapPromise;
  const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ''));
  const explicitChallenge = fragment.get('research_bootstrap');
  const existing = session();
  // Session changes and mounted controls reuse the existing grant. Only a new
  // explicit login URL, or recovery after the grant was removed, exchanges it.
  if (!explicitChallenge && existing) return true;
  const challenge =
    explicitChallenge || window.sessionStorage.getItem(BOOTSTRAP_KEY);
  if (!challenge) return false;
  bootstrapPromise = (async () => {
    const value: unknown = await boundedConnection(async (signal) => {
      const response = await fetch('/auth/research/bootstrap', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ challenge }),
        signal,
      });
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          window.sessionStorage.removeItem(BOOTSTRAP_KEY);
          window.sessionStorage.removeItem(SESSION_KEY);
          runtimeSnapshot = null;
        }
        throw new Error('Native research authentication failed');
      }
      return await response.json();
    }, 'researchWorkflow.connectionTimeout');
    if (!validSession(value)) {
      throw new Error('Native research authentication is invalid');
    }
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
    runtimeSnapshot = null;
    const reusable = (value as ResearchSession & { reusable_bootstrap?: boolean }).reusable_bootstrap === true;
    if (reusable) window.sessionStorage.setItem(BOOTSTRAP_KEY, challenge);
    else window.sessionStorage.removeItem(BOOTSTRAP_KEY);
    window.sessionStorage.setItem(
      SESSION_KEY,
      JSON.stringify({ ...value, ...(reusable ? { bootstrap: challenge } : {}) }),
    );
      window.dispatchEvent(new CustomEvent('research.runtime.changed'));
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
    if (response.status === 401) {
      window.sessionStorage.removeItem(SESSION_KEY);
      runtimeSnapshot = null;
    }
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
    runtimeSnapshot = null;
  }
}
