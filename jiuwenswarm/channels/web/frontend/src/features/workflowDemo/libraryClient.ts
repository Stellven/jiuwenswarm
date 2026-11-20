import { hasResearchSession, researchFetch } from '../../utils/researchClient';
import { readEventStream } from './factoryClient';

export interface LibraryPort {
  semantic_type: string;
  required?: boolean;
}

export interface LibraryPart {
  id: string;
  name: string;
  inputs: Record<string, LibraryPort>;
  outputs: Record<string, LibraryPort>;
  implementation: {
    type: string;
    entrypoint?: string;
    prompt_path?: string;
    [key: string]: unknown;
  };
  inspection?: {
    inputs?: { name: string; expected_filename?: string }[];
    outputs?: { name: string; expected_filename?: string }[];
    [key: string]: unknown;
  };
  source_evidence?: unknown;
  requirements?: unknown;
  verification?: unknown;
  [key: string]: unknown;
}

export interface LibraryWorkflow {
  schema: string;
  id: string;
  version: string;
  name: string;
  source: {
    repository?: string;
    repository_url?: string;
    revision?: string;
    commit?: string;
    checkout?: string;
    [key: string]: unknown;
  };
  subworkflows: LibraryPart[];
  composition?: {
    schema: string;
    origin?: string;
    executable?: boolean;
    execution_support?: string;
    inputs: Record<string, LibraryPort>;
    nodes: { id: string; part: string; bindings: Record<string, LibraryBinding>; optional?: boolean }[];
    outputs: Record<string, LibraryBinding>;
    edges?: { from: string; to: string; output?: string; input?: string; data?: string }[];
  };
  [key: string]: unknown;
}

export interface LibraryBinding {
  node: string;
  port: string;
}

export interface LibraryGraphNode {
  id: string;
  workflow: { id: string; version: string };
  subworkflow: string;
  bindings: Record<string, LibraryBinding>;
  parameters?: Record<string, unknown>;
  name?: string;
}

export interface LibraryGraph {
  id?: string;
  contract?: Record<string, unknown>;
  task_contract?: Record<string, unknown>;
  policy_ref?: { path: string; sha256: string };
  inputs?: Record<string, LibraryArtifact>;
  nodes: LibraryGraphNode[];
  edges?: { from: string; to: string; input?: string; output?: string; data?: string }[];
  outputs?: Record<string, LibraryBinding>;
  [key: string]: unknown;
}

export interface LibraryArtifact {
  id: string;
  kind: string;
  path: string;
  sha256: string;
  size: number;
  producer: string;
  metadata?: Record<string, unknown>;
}

export interface LibraryEvent {
  sequence: number;
  time?: string;
  timestamp?: string;
  type: string;
  node_id?: string;
  payload: Record<string, unknown>;
}

export interface LibraryAttempt {
  number: number;
  status: string;
  inputs?: Record<string, LibraryArtifact>;
  outputs?: Record<string, LibraryArtifact>;
  commands?: LibraryCommand[];
  error?: unknown;
}

export interface LibraryNodeState {
  id?: string;
  status: string;
  inputs?: Record<string, LibraryArtifact> | LibraryArtifact[];
  outputs?: Record<string, LibraryArtifact> | LibraryArtifact[];
  commands?: LibraryCommand[];
  attempts?: LibraryAttempt[];
  error?: unknown;
  [key: string]: unknown;
}

export interface LibraryDecision {
  workflow_id: string;
  selected_parts: string[];
  reason: string;
}

export interface LibraryMaterial {
  id: string;
  kind: string;
  name: string;
  path: string;
  sha256: string;
  integrity?: unknown;
}

export interface LibraryCommand {
  argv?: string[];
  cwd?: string;
  pid?: number | null;
  exit_code?: number | null;
  started_at?: string;
  finished_at?: string;
  stdout?: string;
  stderr?: string;
  stdout_path?: string;
  stderr_path?: string;
  [key: string]: unknown;
}

export interface LibraryModelAttempt {
  recorded_at: string;
  outcome: string;
  reason_code: string;
  observed_http_statuses: number[];
  receipt_sha256: string;
  live_probe: false;
  driver?: string;
  model?: string;
}

export interface LibraryCheckSummary {
  id: string;
  status: string;
  selection_source: string;
  read_only: true;
  created_at?: string;
  artifact_count?: number;
  run_dir?: string;
  verification_status?: string;
}

export interface LibraryCheck extends LibraryCheckSummary {
  run: LibraryJob;
  events: LibraryEvent[];
  verification: Record<string, unknown> | null;
  command_records: LibraryCommand[];
  recording_provenance: Record<string, unknown>;
  workflow_definitions?: LibraryWorkflow[];
  definition_errors?: unknown[];
}

export interface LibraryJob {
  id: string;
  status: string;
  created_at?: string;
  request?: Record<string, unknown>;
  materials?: LibraryMaterial[];
  events?: LibraryEvent[];
  workflow?: LibraryWorkflow;
  graph?: LibraryGraph;
  nodes?: LibraryNodeState[] | Record<string, LibraryNodeState>;
  artifacts?: LibraryArtifact[] | Record<string, LibraryArtifact>;
  edges?: { from: string; to: string; data?: string; status: string }[];
  unmet_requirements?: unknown[] | Record<string, unknown>;
  tool_calls?: unknown;
  decisions?: LibraryDecision[];
  invocations?: unknown;
  policy?: string;
  error?: unknown;
  product_ready?: boolean;
  [key: string]: unknown;
}

export type LibraryJobKind = 'imports' | 'plans' | 'executions';
export interface LibrarySource {
  path: string;
  content: string;
  sha256: string;
}

const base = '/api/v1/factory/library';

async function responseFor(path: string, init: RequestInit = {}): Promise<Response> {
  const transport = hasResearchSession() ? researchFetch : fetch;
  const response = await transport(`${base}${path}`, {
    ...init,
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...init.headers },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Workflow Library ${response.status}: ${text.slice(0, 1000) || response.statusText}`);
  }
  return response;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return (await responseFor(path, init)).json() as Promise<T>;
}

async function streamEvents(path: string, receive: (event: LibraryEvent) => void, signal?: AbortSignal) {
  const response = await responseFor(path, { signal, headers: { Accept: 'text/event-stream' } });
  await readEventStream(response, (frame) => {
    if (frame.event !== 'library' && frame.event !== 'message') return;
    const value = frame.data as LibraryEvent;
    if (value && typeof value.sequence === 'number' && typeof value.type === 'string') receive(value);
  });
}

export const libraryClient = {
  list: (signal?: AbortSignal) => request<{ workflows: LibraryWorkflow[] }>('', { signal }),
  imports: (signal?: AbortSignal) => request<{ jobs: LibraryJob[] }>('/imports', { signal }),
  importMaterial: (id: string, materialId: string, signal?: AbortSignal) =>
    request<LibrarySource>(`/imports/${encodeURIComponent(id)}/materials/${encodeURIComponent(materialId)}`, {
      signal,
    }),
  checks: (signal?: AbortSignal) => request<{ checks: LibraryCheckSummary[] }>('/checks', { signal }),
  modelConnection: (signal?: AbortSignal) =>
    request<{ attempt: LibraryModelAttempt | null }>('/model-connection', { signal }),
  check: (id: string, signal?: AbortSignal) => request<LibraryCheck>(`/checks/${encodeURIComponent(id)}`, { signal }),
  checkArtifact: (id: string, artifactId: string, signal?: AbortSignal) =>
    responseFor(`/checks/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(artifactId)}`, { signal }),
  checkProjectFile: (id: string, artifactId: string, path: string, signal?: AbortSignal) =>
    responseFor(
      `/checks/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(artifactId)}/file?${new URLSearchParams({ path }).toString()}`,
      { signal },
    ),
  import: (repository_url: string, revision?: string) =>
    request<LibraryJob>('/import', {
      method: 'POST',
      body: JSON.stringify({ repository_url, ...(revision?.trim() ? { revision: revision.trim() } : {}) }),
    }),
  policy: (signal?: AbortSignal) => request<{ content: string; sha256: string }>('/policy', { signal }),
  plan: (
    task: Record<string, unknown>,
    policy: string,
    previous_execution_id?: string,
    planner: 'agent' | 'contract' = 'agent',
  ) =>
    request<LibraryJob>('/plan', {
      method: 'POST',
      body: JSON.stringify({
        task,
        planner,
        ...(planner === 'agent' ? { policy, ...(previous_execution_id ? { previous_execution_id } : {}) } : {}),
      }),
    }),
  execute: (plan_id: string) => request<LibraryJob>('/execute', { method: 'POST', body: JSON.stringify({ plan_id }) }),
  startBuild: (task: Record<string, unknown>, signal?: AbortSignal) =>
    request<LibraryJob>('/build', { method: 'POST', body: JSON.stringify({ task }), signal }),
  builds: (signal?: AbortSignal) => request<{ jobs: LibraryJob[] }>('/builds', { signal }),
  build: (id: string, signal?: AbortSignal) => request<LibraryJob>(`/builds/${encodeURIComponent(id)}`, { signal }),
  buildStream: (id: string, after: number, receive: (event: LibraryEvent) => void, signal?: AbortSignal) =>
    streamEvents(`/builds/${encodeURIComponent(id)}/stream?after=${after}`, receive, signal),
  buildProduct: (id: string, signal?: AbortSignal) =>
    request<unknown>(`/builds/${encodeURIComponent(id)}/product`, { signal }),
  job: (kind: LibraryJobKind, id: string, signal?: AbortSignal) =>
    request<LibraryJob>(`/${kind}/${encodeURIComponent(id)}`, { signal }),
  stream: (
    kind: LibraryJobKind,
    id: string,
    after: number,
    receive: (event: LibraryEvent) => void,
    signal?: AbortSignal,
  ) => streamEvents(`/${kind}/${encodeURIComponent(id)}/events?after=${after}`, receive, signal),
  source: (workflow: LibraryWorkflow, path: string, signal?: AbortSignal) => {
    const query = new URLSearchParams({ workflow_id: workflow.id, version: workflow.version, path });
    return request<LibrarySource>(`/source?${query.toString()}`, { signal });
  },
  artifact: (runId: string, id: string, signal?: AbortSignal) =>
    responseFor(`/artifacts/${encodeURIComponent(runId)}/${encodeURIComponent(id)}`, { signal }),
  projectFile: (runId: string, id: string, path: string, signal?: AbortSignal) =>
    responseFor(
      `/artifacts/${encodeURIComponent(runId)}/${encodeURIComponent(id)}/file?${new URLSearchParams({ path }).toString()}`,
      { signal },
    ),
};

export function libraryTerminal(status: string): boolean {
  return ['completed', 'verified', 'failed', 'blocked'].includes(status);
}
