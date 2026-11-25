import { getApiBase } from '../../utils/env';
import type { CuratedReplay } from './views/storyModel.ts';
import type { Controls, NodeCheckIndex, OperatorOp } from './views/checkModel.ts';

export type JsonRecord = Record<string, unknown>;
export type Run = {
  id: string;
  name: string;
  kind: 'bundle' | 'live';
  source_name?: string;
  task_id: string;
  objective?: string;
  status: string;
  updated: number;
  /** Curated demo replays are pinned first in the run list. */
  demo?: boolean;
  demo_order?: number;
  /** web-* launch scratch homes and synthetic smoke homes. */
  scratch?: boolean;
  /** An older export snapshot of a task that has a newer export. */
  duplicate?: boolean;
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
  curated?: CuratedReplay | null;
  /** Per plan node: node contract CCs, verified outputs and their host node_check records. */
  node_checks?: NodeCheckIndex;
  /** Live homes only: what an operator may do now. */
  controls?: Controls;
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
  file: (id: string, path: string, signal?: AbortSignal) =>
    request<FileContent>(`/runs/${encodeURIComponent(id)}/file?path=${encodeURIComponent(path)}`, { signal }),
  launch: (template_id: string) =>
    request<{ id: string; task_id: string; pid: number }>('/launch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_id }),
    }),
  operator: (id: string, node: string, op: OperatorOp, reason: string) =>
    request<{ graph_rev: number; held: string[] }>(
      `/runs/${encodeURIComponent(id)}/nodes/${encodeURIComponent(node)}/${op}`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reason }) },
    ),
  resume: (id: string) =>
    request<{ id: string; task_id: string; pid: number }>(`/runs/${encodeURIComponent(id)}/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    }),
};
