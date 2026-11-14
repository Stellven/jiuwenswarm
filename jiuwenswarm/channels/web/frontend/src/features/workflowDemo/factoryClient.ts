import { hasResearchSession, researchFetch } from '../../utils/researchClient';

export interface StagePort {
  name: string;
  kind: string;
  required?: boolean;
}

export interface StageDeclaration {
  id: string;
  name: string;
  workflow_id: string;
  subworkflow_id: string;
  entrypoint: string;
  inputs: StagePort[];
  outputs: StagePort[];
  tools: string[];
  environment: unknown;
  verifier: unknown;
}

export interface FactoryCatalog {
  goals: string[];
  groups: { id: string; name: string }[];
  subworkflows: { id: string; name: string; workflow_id: string; stages: StageDeclaration[] }[];
  stages: StageDeclaration[];
}

export interface Artifact {
  id: string;
  kind: string;
  path: string;
  sha256: string;
  size: number;
  producer: string;
}

export interface CodeDiffFile {
  source_path: string;
  generated_path: string;
  source_code: string;
  generated_code: string;
  language?: string;
}

export interface CodeDiffArtifact {
  schema: 'strata.code.diff.v1';
  files: CodeDiffFile[];
}

export function parseCodeDiff(text: string): CodeDiffArtifact {
  const value: unknown = JSON.parse(text);
  if (!value || typeof value !== 'object') throw new Error('Invalid code diff artifact');
  const data = value as Partial<CodeDiffArtifact>;
  if (data.schema !== 'strata.code.diff.v1' || !Array.isArray(data.files) || data.files.length === 0)
    throw new Error('Invalid code diff artifact schema');
  for (const file of data.files) {
    if (!file || typeof file !== 'object') throw new Error('Invalid code diff file');
    for (const field of ['source_path', 'generated_path', 'source_code', 'generated_code'] as const) {
      if (typeof file[field] !== 'string' || !file[field].trim()) throw new Error(`Code diff file requires ${field}`);
    }
    if (file.language !== undefined && typeof file.language !== 'string')
      throw new Error('Invalid code diff file language');
  }
  return data as CodeDiffArtifact;
}

export interface CommandRecord {
  argv: string[];
  cwd: string;
  exit_code: number | null;
  stdout_path?: string;
  stderr_path?: string;
  stdout?: string;
  stderr?: string;
}

export interface FactoryAttempt {
  number: number;
  status: string;
  started_at: string;
  finished_at?: string | null;
  commands: CommandRecord[];
  inputs: Artifact[];
  outputs: Artifact[];
  error?: unknown;
  verification?: unknown;
}

export interface FactoryNode {
  id: string;
  stage_id: string;
  name: string;
  workflow_id: string;
  subworkflow_id: string;
  status: string;
  attempts: FactoryAttempt[];
}

export interface FactoryEdge {
  from: string;
  to: string;
  data: string;
}

export interface EngineeringOracleCase {
  input: string;
  operation?: string;
  expected: Record<string, unknown>;
  atol?: number;
  rtol?: number;
}

export interface EngineeringTask {
  description: string;
  source_scope?: string[];
  capabilities?: string[];
  oracle?: { cases: EngineeringOracleCase[] };
  acceptance: {
    source_project?: boolean;
    cpu_validation?: boolean;
    full_model_inference?: boolean;
    native_execution?: boolean;
    compare_original?: boolean;
  };
}

export function parseEngineeringTask(text: string): EngineeringTask {
  const value: unknown = JSON.parse(text);
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new Error('Engineering task must be an object');
  const task = value as Record<string, unknown>;
  if (
    Object.keys(task).some(
      (key) => !['description', 'source_scope', 'capabilities', 'acceptance', 'oracle'].includes(key),
    )
  )
    throw new Error('Engineering task contains unsupported fields');
  if (typeof task.description !== 'string' || !task.description.trim())
    throw new Error('Engineering task requires a description');
  for (const field of ['source_scope', 'capabilities']) {
    if (
      task[field] !== undefined &&
      (!Array.isArray(task[field]) || !task[field].every((item) => typeof item === 'string' && item.trim()))
    )
      throw new Error(`Engineering task ${field} must be a list of nonempty strings`);
  }
  if (!task.acceptance || typeof task.acceptance !== 'object' || Array.isArray(task.acceptance))
    throw new Error('Engineering task requires acceptance criteria');
  const acceptance = task.acceptance as Record<string, unknown>;
  const criteria = ['source_project', 'cpu_validation', 'full_model_inference', 'native_execution', 'compare_original'];
  if (
    Object.keys(acceptance).length === 0 ||
    Object.keys(acceptance).some((key) => !criteria.includes(key) || typeof acceptance[key] !== 'boolean')
  )
    throw new Error('Engineering task acceptance criteria must contain supported boolean fields');
  if (task.oracle !== undefined) {
    if (!task.oracle || typeof task.oracle !== 'object' || Array.isArray(task.oracle))
      throw new Error('Engineering task oracle must be an object');
    const oracle = task.oracle as Record<string, unknown>;
    if (
      Object.keys(oracle).some((key) => key !== 'cases') ||
      !Array.isArray(oracle.cases) ||
      oracle.cases.length < 1 ||
      oracle.cases.length > 16
    )
      throw new Error('Engineering task oracle requires 1 to 16 cases');
    for (const value of oracle.cases) {
      if (!value || typeof value !== 'object' || Array.isArray(value))
        throw new Error('Engineering task oracle case must be an object');
      const entry = value as Record<string, unknown>;
      if (Object.keys(entry).some((key) => !['input', 'operation', 'expected', 'atol', 'rtol'].includes(key)))
        throw new Error('Engineering task oracle case contains unsupported fields');
      if (typeof entry.input !== 'string' || !entry.input.trim())
        throw new Error('Engineering task oracle case requires input');
      if (entry.operation !== undefined && (typeof entry.operation !== 'string' || !entry.operation.trim()))
        throw new Error('Engineering task oracle operation must be a nonempty string');
      if (!entry.expected || typeof entry.expected !== 'object' || Array.isArray(entry.expected))
        throw new Error('Engineering task oracle expected must be an object');
      for (const field of ['atol', 'rtol']) {
        const tolerance = entry[field];
        if (tolerance !== undefined && (typeof tolerance !== 'number' || !Number.isFinite(tolerance) || tolerance < 0))
          throw new Error(`Engineering task oracle ${field} must be finite and nonnegative`);
      }
    }
  }
  return value as EngineeringTask;
}

export interface FactoryRequest {
  goals: string[];
  repository_url: string;
  revision?: string;
  model_path?: string;
  target_backend: 'ascend' | 'cpu' | 'cuda';
  task?: EngineeringTask;
  options?: Record<string, unknown>;
}

export interface GraphRevision {
  revision: number;
  time?: string;
  reason: string;
  nodes: FactoryNode[] | string[];
  edges: FactoryEdge[];
}

export interface FactoryRun {
  id: string;
  status: string;
  request: FactoryRequest;
  created_at: string;
  updated_at: string;
  nodes: FactoryNode[];
  edges: FactoryEdge[];
  artifacts: Artifact[];
  graph_revisions: GraphRevision[];
  error?: unknown;
  sequence: number;
}

export interface FactoryEvent {
  sequence: number;
  time: string;
  type: string;
  node_id?: string;
  payload: Record<string, unknown>;
}

export interface FactoryEvents {
  events: FactoryEvent[];
  sequence: number;
  status: string;
}

const base = '/api/v1/factory';

async function responseFor(path: string, init: RequestInit = {}): Promise<Response> {
  const transport = hasResearchSession() ? researchFetch : fetch;
  const response = await transport(`${base}${path}`, {
    ...init,
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...init.headers },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Factory API ${response.status}: ${body.slice(0, 500) || response.statusText}`);
  }
  return response;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  return (await responseFor(path, init)).json() as Promise<T>;
}

export interface FactoryStreamFrame {
  event: string;
  data: unknown;
}

export async function readEventStream(response: Response, receive: (frame: FactoryStreamFrame) => void): Promise<void> {
  if (!response.body) throw new Error('Factory execution stream has no response body');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let ended = false;
  const frame = (text: string) => {
    const lines = text.split('\n');
    const event =
      lines
        .find((line) => line.startsWith('event:'))
        ?.slice(6)
        .trim() ?? 'message';
    const data = lines
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart())
      .join('\n');
    if (data) receive({ event, data: JSON.parse(data) as unknown });
  };
  try {
    while (!ended) {
      const { done, value } = await reader.read();
      ended = done;
      buffer = (buffer + decoder.decode(value, { stream: !done })).replace(/\r\n/g, '\n');
      let boundary = buffer.indexOf('\n\n');
      while (boundary >= 0) {
        frame(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf('\n\n');
      }
      if (done) {
        if (buffer.trim()) frame(buffer);
        break;
      }
    }
  } finally {
    if (!ended) await reader.cancel();
    reader.releaseLock();
  }
}

export const factoryClient = {
  catalog: (signal?: AbortSignal) => request<FactoryCatalog>('/catalog', { signal }),
  start: (body: FactoryRequest, signal?: AbortSignal) =>
    request<FactoryRun>('/runs', { method: 'POST', body: JSON.stringify(body), signal }),
  run: (id: string, signal?: AbortSignal) => request<FactoryRun>(`/runs/${encodeURIComponent(id)}`, { signal }),
  events: (id: string, after: number, signal?: AbortSignal) =>
    request<FactoryEvents>(`/runs/${encodeURIComponent(id)}/events?after=${after}`, { signal }),
  stream: async (id: string, after: number, receive: (frame: FactoryStreamFrame) => void, signal?: AbortSignal) =>
    readEventStream(
      await responseFor(`/runs/${encodeURIComponent(id)}/stream?after=${after}`, {
        signal,
        headers: { Accept: 'text/event-stream' },
      }),
      receive,
    ),
  artifact: (runId: string, id: string) =>
    responseFor(`/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(id)}`),
  artifactText: async (runId: string, id: string, signal?: AbortSignal) =>
    (await responseFor(`/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(id)}`, { signal })).text(),
  artifactUrl: (runId: string, id: string) =>
    `${base}/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(id)}`,
};

export function isTerminal(status: string): boolean {
  return ['completed', 'blocked', 'failed'].includes(status);
}

export function statusColor(status: string): 'pending' | 'running' | 'verified' | 'failed' | 'blocked' {
  if (status === 'completed' || status === 'verified') return 'verified';
  if (status === 'failed') return 'failed';
  if (status === 'blocked') return 'blocked';
  if (status === 'running' || status === 'planning') return 'running';
  return 'pending';
}

export function pretty(value: unknown): string {
  if (value === undefined || value === null) return '';
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}
