import { getApiBase } from '../../utils/env';

export type JsonRecord = Record<string, unknown>;
export type Run = {
  id: string;
  name: string;
  kind: 'bundle' | 'live';
  task_id: string;
  status: string;
  updated: number;
  objective?: string;
};
export type EvidenceFile = {
  path: string;
  display_path?: string;
  artifact_ids?: string[];
  sha256: string | null;
  expected_sha256?: string | null;
  integrity: 'verified' | 'mismatch' | 'untracked' | 'missing';
  size: number;
};
export type StoryEvent = JsonRecord & {
  cursor: number;
  id: string;
  kind: string;
  summary: string;
  created: number;
  rev?: number;
};
export type RunDetail = {
  run: Run;
  records: Record<string, JsonRecord[]>;
  contract: JsonRecord;
  graph: JsonRecord;
  stack: unknown;
  telemetry: unknown;
  files: EvidenceFile[];
  events: StoryEvent[];
  summary: unknown;
  session?: SessionSnapshot | null;
};
export type SessionSnapshot = {
  status: 'running' | 'waiting' | 'finished' | 'idle' | 'unknown';
  elapsed_s: number | null;
  turn: number | null;
  step: { kind: 'job' | 'tool' | 'turn' | 'node'; label: string } | null;
  latest_message: { text: string; created: number | null } | null;
};
export type LaunchTemplate = {
  id: string;
  name: string;
  objective?: string;
  contract_id?: string;
  capsules?: string[];
};
export type RunList = { runs: Run[]; launch_templates: LaunchTemplate[]; launch_enabled: boolean };
export type FileContent = EvidenceFile & { content: string; truncated: boolean };

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBase()}/api/factory${path}`, init);
  if (!response.ok) {
    const value = await response.json().catch(() => ({}));
    throw new Error(value.detail || value.error || `${response.status} ${response.statusText}`);
  }
  return response.json();
}
export const factoryApi = {
  list: () => request<RunList>('/runs'),
  detail: (id: string) => request<RunDetail>(`/runs/${encodeURIComponent(id)}`),
  story: (id: string, since: number) =>
    request<{ events: StoryEvent[]; cursor: number; total: number; reset?: boolean }>(
      `/runs/${encodeURIComponent(id)}/story?since=${since}`,
    ),
  session: (id: string) => request<SessionSnapshot>(`/runs/${encodeURIComponent(id)}/session`),
  file: (id: string, path: string) =>
    request<FileContent>(`/runs/${encodeURIComponent(id)}/file?path=${encodeURIComponent(path)}`),
  launch: (template_id: string) =>
    request<{ id: string; task_id: string; pid: number }>('/launch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_id }),
    }),
};
