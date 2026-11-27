import { getApiBase } from '../../utils/env';
import type { CuratedReplay } from './views/storyModel.ts';
import type { CheckOutput, Controls, NodeCheckIndex, OperatorOp } from './views/checkModel.ts';

export type JsonRecord = Record<string, unknown>;
export type Run = {
  id: string;
  name: string;
  kind: 'bundle' | 'live';
  source_name?: string;
  read_only?: boolean;
  featured?: boolean;
  task_id: string;
  objective?: string;
  status: string;
  /** Original task creation in Unix seconds, retained in native replay exports. */
  created?: number;
  updated: number;
  /** Curated demo replays are pinned first in the run list. */
  demo?: boolean;
  demo_order?: number;
  contract_demo?: boolean;
  live_demo?: boolean;
  original_run_id?: string;
  demo_replay_id?: string;
  /** web-* launch scratch homes and synthetic smoke homes. */
  scratch?: boolean;
  /** An older export snapshot of a task that has a newer export. */
  duplicate?: boolean;
};
export type EvidenceFile = {
  path: string;
  display_path?: string;
  media_type?: string;
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
  replayed_from?: unknown;
  correction?: CorrectionEvent;
};
export type RunDetail = {
  run: Run;
  records: Record<string, JsonRecord[]>;
  contract: JsonRecord;
  graph: JsonRecord;
  /** Original plan for bundled runs whose curated graph is a story projection. */
  recorded_plan?: JsonRecord | null;
  stack: unknown;
  telemetry: unknown;
  files: EvidenceFile[];
  events: StoryEvent[];
  engine_log?: StoryEvent[];
  summary: unknown;
  session?: SessionSnapshot | null;
  curated?: CuratedReplay | null;
  published_report?: CuratedReplay['presentation_header'] | null;
  planner_plan?: PlannerPlan | null;
  /** Per plan node: node contract CCs, verified outputs and their host node_check records. */
  node_checks?: NodeCheckIndex;
  /** Live homes only: what an operator may do now. */
  controls?: Controls;
  run_state?: RunState;
  cc_overview?: Record<string, CapsuleOverview[]>;
  scheduler_models?: string[];
  correction_overview?: Record<string, CorrectionCounts>;
};
export type PlannerSource = {
  id?: string;
  path?: string | null;
  digest?: string | null;
  kind?: string | null;
  created?: number | null;
  revision?: number | null;
};
export type PlannerFinal = PlannerSource & {
  preliminary_digest?: string | null;
  preliminary?: JsonRecord | null;
  preliminary_source?: PlannerSource | null;
  final?: JsonRecord | null;
  diff?: JsonRecord[] | null;
  rationale?: string | null;
  never_weaker: { status: 'admitted' | 'unverified'; source?: PlannerSource | null };
};
export type PlannerNode = {
  node_id: string;
  title?: string | null;
  change: 'added' | 'removed' | 'reordered' | 'unchanged';
  change_source?: PlannerSource | null;
  draft: JsonRecord | null;
  draft_source?: PlannerSource | null;
  suggested_ccs: string[];
  finals: PlannerFinal[];
  refusals: Array<PlannerSource & { problems?: unknown; rationale?: string | null }>;
};
export type PlannerPlan = {
  artifact: EvidenceFile;
  source: PlannerSource & { planner?: string };
  plan_order: string[];
  run_order: string[];
  read_receipts: JsonRecord[];
  nodes: PlannerNode[];
};
export type RunState = {
  state: string;
  outcome?: string;
  reason?: string;
  by?: string;
  since?: number | string;
  node_id?: string;
  job?: {
    attempt_id?: string;
    effect?: string;
    state?: string;
    since?: number | string;
    elapsed_seconds?: number;
    replayed_from?: unknown;
  };
  source?: string;
  markers?: Record<string, { text: string; mtime: number }>;
};
export type CapsuleOverview = {
  id: string;
  version?: string;
  kind?: string;
  title?: string;
  purpose?: string;
  verdict?: string;
};
export type NodeOutput = {
  id: string;
  name: string;
  kind: string;
  artifact_ids?: string[];
  evidence_ids?: string[];
  summary?: unknown;
  replayed_from?: unknown;
  source?: unknown;
};
export type NodeCapsule = CapsuleOverview & {
  materials?: Record<string, string>;
  sections?: Record<string, string>;
  files?: EvidenceFile[];
  catalog_name?: string;
  material_source?: 'sealed' | 'catalog';
  material_version?: string;
  material_digest?: string;
  calls?: { count: number; first?: unknown; last?: unknown; failures?: number | unknown[]; records?: unknown[] };
  runs?: JsonRecord[];
  outputs?: NodeOutput[];
  checks?: CheckOutput[];
  comparison?: unknown;
  evidence_fact?: { text: string; source: unknown };
};
export type NodeContract = {
  preliminary?: JsonRecord | null;
  final?: JsonRecord | null;
  briefing?: unknown;
  refusals?: unknown;
  scheduler?: unknown;
  rationale?: unknown;
  source?: unknown;
  final_source?: unknown;
};
export type CorrectionCounts = { findings: number; notes: number; repairs: number };
export type CorrectionEvent = {
  finding_key?: string;
  id: string;
  kind: 'finding' | 'note' | 'repair' | 'passing_check';
  created: number;
  source: string;
  node_id: string;
  text: string;
  output?: string;
  check_id?: string;
  by?: string;
  actor?: 'reviewer' | 'verifier' | 'host' | 'scheduler' | 'operator' | 'worker';
  reviewer?: string;
  file?: string;
  line?: number;
  severity?: string;
  verdict?: string;
  reviewer_verdict?: string;
  advisory?: boolean;
  status?: 'open' | 'verified_repair';
  host_passed?: boolean;
  verifier_passed?: boolean;
  finding_ids?: string[];
  note_ids?: string[];
  evidence_ids?: string[];
};
export type NodeCorrection = { counts: CorrectionCounts; events: CorrectionEvent[] };
export type NodeDetail = {
  node_id: string;
  contract?: NodeContract;
  capsules: NodeCapsule[];
  corrections?: NodeCorrection;
  outputs?: NodeOutput[];
  runs?: JsonRecord[];
};
export type NodeDiff = { content: string; source?: unknown; path?: string; base?: string; head?: string; truncated?: boolean };
export type RunOperation = 'pause' | 'resume' | 'revise-preview' | 'revise-apply';
export type RunOperationResult = JsonRecord & { pid?: number };

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
export type RunList = {
  runs: Run[];
  launch_templates: LaunchTemplate[];
  launch_enabled: boolean;
  live_demos_enabled?: boolean;
};
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
  detail: (id: string, signal?: AbortSignal) => request<RunDetail>(`/runs/${encodeURIComponent(id)}`, { signal }),
  story: (id: string, since: number) =>
    request<{ events: StoryEvent[]; cursor: number; total: number; reset?: boolean }>(
      `/runs/${encodeURIComponent(id)}/story?since=${since}`,
    ),
  state: (id: string) => request<{ run_state: RunState; controls: Controls }>(`/runs/${encodeURIComponent(id)}/state`),
  session: (id: string) => request<SessionSnapshot>(`/runs/${encodeURIComponent(id)}/session`),
  node: (id: string, nodeId: string, signal?: AbortSignal) =>
    request<NodeDetail>(`/runs/${encodeURIComponent(id)}/nodes/${encodeURIComponent(nodeId)}`, { signal }),
  diff: (id: string, nodeId: string, output: string, signal?: AbortSignal) =>
    request<NodeDiff>(
      `/runs/${encodeURIComponent(id)}/nodes/${encodeURIComponent(nodeId)}/diff?output=${encodeURIComponent(output)}`,
      { signal },
    ),
  material: (id: string, nodeId: string, cc: string, path: string, signal?: AbortSignal) =>
    request<FileContent & { parsed: unknown }>(
      `/runs/${encodeURIComponent(id)}/nodes/${encodeURIComponent(nodeId)}/material?cc=${encodeURIComponent(cc)}&path=${encodeURIComponent(path)}`,
      { signal },
    ),
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
  runOperation: (id: string, action: RunOperation, reason: string) => {
    const revise = action === 'revise-preview' || action === 'revise-apply';
    return request<RunOperationResult>(`/runs/${encodeURIComponent(id)}/${revise ? 'revise' : action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason, confirm: true, ...(revise && { dry_run: action === 'revise-preview' }) }),
    });
  },
};
