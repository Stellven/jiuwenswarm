import { getApiBase } from '../../utils/env';

export type JsonRecord = Record<string, unknown>;
export type Run = {
  id: string;
  name: string;
  kind: 'bundle' | 'live';
  task_id: string;
  objective?: string;
  status: string;
  updated: number;
};
export type EvidenceFile = {
  path: string;
  display_path?: string;
  artifact_ids?: string[];
  sha256: string;
  expected_sha256?: string;
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
};
export type RunList = { runs: Run[]; launch_templates: { id: string; name: string }[]; launch_enabled: boolean };
export type FileContent = EvidenceFile & { content: string; truncated: boolean };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
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
  file: (id: string, path: string, signal?: AbortSignal) =>
    request<FileContent>(`/runs/${encodeURIComponent(id)}/file?path=${encodeURIComponent(path)}`, { signal }),
  launch: (template_id: string) =>
    request<{ id: string; task_id: string; pid: number }>('/launch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_id }),
    }),
};
