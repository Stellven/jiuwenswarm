import { getApiBase } from '../../../utils/env';
import type { JsonRecord } from '../api';

export type CodexAuthStatus = {
  enabled?: boolean;
  state: 'ready' | 'signed_out' | 'signing_in' | 'subscription_required' | 'unavailable' | 'checking';
  plan?: string | null;
  error?: string | null;
  login_attempt_id?: string | null;
  auth_url?: string | null;
  user_code?: string | null;
  active_runs?: number;
};

export type PlannerEnvironment = { tlc: boolean; reason?: string; java?: string; tla2tools?: string };

export type TaskInputDocument = {
  format?: string;
  task_id?: string;
  contract_id?: string | null;
  objective?: string;
  notes?: string[];
  subject?: {
    engine?: { name?: string; revision?: string };
    model?: { name?: string; format?: string };
  };
  target?: { profile?: string; machine?: string; arch?: string; sm?: string; node_count?: number };
  acceptance_criteria?: Array<{ id: string; kind: string; description: string }>;
  constraints?: {
    allowed_effects?: string[];
    budget?: Record<string, number>;
  };
  [key: string]: unknown;
};

export type RequirementsEntry = {
  id: string;
  objective: string;
  contract_id?: string | null;
  notes: string[];
  problems: string[];
  document?: TaskInputDocument;
};

export type PlanState = 'pending' | 'running' | 'succeeded' | 'failed' | 'rejected' | 'interrupted';
export type PlanStatus = {
  state: PlanState;
  round?: number;
  rounds?: number;
  phase?: string | null;
  error?: string;
  nodes?: number;
  warnings?: string[];
  requirements_id?: string;
  contract_id?: string;
  created?: number;
  started?: number;
  finished?: number;
  problems?: string[];
};
export type PlanSummary = PlanStatus & { id: string };
export type TlcRun = {
  run: 'safety' | 'delivery';
  passed: boolean;
  seconds: number;
  states_generated: number | null;
  distinct_states: number | null;
  depth: number | null;
  checked: string[];
  error?: string;
  violation?: { property: string; kind: string; sentence: string };
};
export type ExecutionModel = {
  max_parallel: number;
  default_attempts: number;
  limits: Record<string, number>;
  exclusive: Record<string, string[]>;
};
export type RoundVerification = { passed: boolean; runs: TlcRun[]; execution_model: ExecutionModel } | null;
export type PlanRound = {
  round: number;
  finished: boolean;
  layer: 'ir' | 'parse' | 'static' | 'tla' | 'init' | 'passed' | null;
  problems: string[];
  warnings: string[];
  verification: RoundVerification;
  error?: string | null;
  nodes?: number | null;
  prompt_chars: number;
  reply_chars: number;
};
export type ComparisonRow = {
  reference: string;
  planned: string;
  kind: string;
  differences: Array<{ field: string; reference: unknown; planned: unknown }>;
};
export type Comparison = { rows: ComparisonRow[]; missing: string[]; extra: string[]; structurally_equivalent: boolean };
export type Candidate = {
  capsule: string;
  unit: string;
  version: string;
  kind?: string;
  change_kind?: string;
  must_include?: boolean;
  features: {
    hardware: { match: boolean | null; detail: string };
    name_match: number;
    acceptance: string | null;
    slices: string[];
    regions: string[];
    files: number;
  };
};
export type InterferencePair = { a: string; b: string; files: string[]; regions: string[]; weight: number };
export type MergeOption = { summary: string; stages: Array<{ id: string; members: string[] }> };
export type PlanStep = {
  id: string;
  kind: string;
  objective: string;
  depends_on: string[];
  capsules: string[];
  limits?: Record<string, number>;
  criteria?: string[];
  outputs?: Array<{ name?: string; port?: string; kind: string }>;
  workspace?: 'none' | 'read' | 'write';
};

export type GraphTlaSection = { id: string; label: string; line: number };
export type GraphTlaInfo = {
  present: boolean;
  path?: string;
  bytes: number;
  lines: number;
  sha256: string;
  parse_ms: number;
  roundtrip_consistent: boolean;
  parsed_nodes: number;
  preview: string;
  truncated: boolean;
  sections: GraphTlaSection[];
};

export type Selection = {
  task_id?: string;
  must_include?: string[];
  candidates: Candidate[];
  rejected: Array<{ capsule: string; rule: string; reason: string }>;
  risks: Array<{ unit: string; capsule: string; detail: string }>;
  interference: InterferencePair[];
  merge_options: Record<string, MergeOption>;
};
export type PlanIr = {
  steps?: PlanStep[];
  selected_capsules?: Array<{ capsule: string; why: string }>;
  unrealizable?: { why: string };
  units?: Array<{ id: string; capsules: string[] }>;
  preflight?: Array<{ unit: string; add: boolean; why: string }>;
  merge?: { option: string; why: string };
  priority?: string[][];
  criteria?: Record<string, string[]>;
  limits?: Record<string, Record<string, number>>;
};
export type PlanDetail = {
  selection: Selection | null;
  ir: PlanIr | null;
  derivation: Array<{ node: string; rule: string; detail: string }> | null;
  id: string;
  status: PlanStatus;
  requirements: TaskInputDocument | null;
  rounds: PlanRound[];
  graph: JsonRecord | null;
  plan: JsonRecord | null;
  node_contracts: JsonRecord | null;
  comparison: Comparison | null;
  record: JsonRecord | null;
  verification: (JsonRecord & { runs: TlcRun[]; execution_model: ExecutionModel }) | null;
  graph_tla_info?: GraphTlaInfo | null;
  outputs: Record<string, string>;
};
export type RoundText = { text: string; truncated: boolean; size: number };

export type AblationSimulation = {
  trials: number;
  seed?: number;
  transient_fail_prob?: number;
  blocked_before_execution?: boolean;
  delivered: number;
  stuck_or_failed: number;
  delivery_rate: number;
  stuck_rate: number;
  contract_violation_rate: number;
  authority_violations: number;
  race_violations: number;
  dangling_failures?: number;
  wasted_nodes_per_trial: number;
  wasted_nodes_per_failure?: number;
  wasted_turns_per_trial: number;
  wasted_turns_per_failure?: number;
  failure_reasons?: Record<string, number>;
};

export type AblationTraceStep = {
  state: number;
  action: string;
  st: Record<string, string>;
  att: Record<string, number>;
};

export type M1Limitation = {
  id: string;
  title: string;
  summary: string;
  source_refs: string[];
};

export type AblationCase = {
  case_id: string;
  class: 'A' | 'B';
  category: string;
  enforcement_mechanism: string;
  title: string;
  fault_kind: string | null;
  node_count: number;
  task_id: string | null;
  expected_tla_pass: boolean;
  m1_legacy?: {
    executed: boolean;
    checks?: Array<{ check_id: string; outcome: string; reason: string }>;
    summary?: { total_checks: number; passed: number; failed: number };
    problems?: string[];
    admitted: boolean;
    escaped_defect: boolean;
    latency_s: number;
    hazard_rate: number;
    max_attempts_per_node?: number;
    simulation: AblationSimulation;
  };
  static_only: {
    static_problems: string[];
    warnings: string[];
    admitted: boolean;
    escaped_defect: boolean;
    latency_s: number;
    hazard_rate: number;
    simulation: AblationSimulation;
  };
  tla_pipeline: {
    admitted: boolean;
    tlc_passed: boolean;
    tlc_problems: string[];
    runs: TlcRun[];
    total_distinct_states: number;
    total_states_generated: number;
    latency_s: number;
    parse_ms: number;
    roundtrip_exact: boolean;
    graph_tla_bytes: number;
    graph_tla_preview?: string;
    counterexample_trace?: AblationTraceStep[];
    simulation: AblationSimulation;
  };
};

export type AblationCategoryBreakdown = {
  category: string;
  mechanism: string;
  count: number;
  m1_escape_rate?: number;
  m1_hazard_rate_mean?: number;
  m1_wasted_nodes_mean?: number;
  m1_wasted_turns_mean?: number;
  static_escape_rate: number;
  tla_block_rate: number;
  static_hazard_rate_mean: number;
  static_wasted_nodes_mean: number;
  static_wasted_turns_mean: number;
  tla_verify_seconds_mean: number;
};

export type AblationScalabilityPoint = {
  k: number;
  unconstrained_states: number;
  unconstrained_seconds: number;
  unconstrained_passed: boolean;
  ordered_states: number;
  ordered_seconds: number;
  ordered_passed: boolean;
  state_reduction_ratio: number;
};

export type AblationRepairCase = {
  case_id: string;
  class: 'C';
  title: string;
  fault_label: string;
  m1_round1_problems?: string[];
  m1_admitted_buggy_round1?: boolean;
  m1_round1_simulation?: AblationSimulation;
  static_round1_problems: string[];
  static_admitted_buggy_round1: boolean;
  static_round1_simulation: AblationSimulation;
  tla_final_state: string;
  tla_rounds_taken: number;
  tla_total_latency_s: number;
  verified_json_emitted?: boolean;
  only_graph_tla_emitted?: boolean;
  round1_layer: string;
  round1_problems: string[];
  round1_trace?: AblationTraceStep[];
  feedback_excerpt?: string;
  changed_ir_fields?: string[];
  round2_layer?: string;
  round2_verification?: { passed: boolean; runs: TlcRun[] };
  tla_final_simulation?: AblationSimulation;
};

export type AblationSummary = {
  total_cases: number;
  class_a_count: number;
  class_b_count: number;
  class_c_count: number;
  m1_checks_executed_count?: number;
  m1_escaped_defects?: number;
  m1_escape_rate?: number;
  m1_class_b_hazard_rate_mean?: number;
  m1_class_b_wasted_nodes_mean?: number;
  m1_class_b_wasted_turns_mean?: number;
  a_delivery_rate_m1?: number;
  m1_false_positives?: number;
  static_escaped_defects: number;
  static_escape_rate: number;
  tla_caught_defects: number;
  tla_catch_rate: number;
  tla_caught_by_tlc_temporal: number;
  tla_caught_by_assume: number;
  tla_false_positives: number;
  tla_false_positive_rate: number;
  roundtrip_fidelity_count: number;
  roundtrip_fidelity_rate: number;
  static_class_b_hazard_rate_mean: number;
  tla_class_b_hazard_rate_mean: number;
  static_class_b_wasted_nodes_mean: number;
  static_class_b_wasted_turns_mean: number;
  a_delivery_rate_static: number;
  a_delivery_rate_tla: number;
  tla_class_a_latency_mean_s: number;
  tla_class_b_latency_mean_s: number;
  parse_taskgraph_tla_mean_ms: number;
  repair_success_count: number;
  repair_success_rate: number;
  scalability_k5_reduction: number;
};

export type AblationResults = {
  generated_at: string;
  m1_limitations?: M1Limitation[];
  environment: {
    os: string;
    python: string;
    java: string;
    tla2tools_jar: string;
    tla2tools_sha256: string;
    git_commit: string;
    simulation_trials_per_case: number;
    simulation_seed: number;
    transient_fail_prob: number;
    reproduce_command: string;
  };
  summary: AblationSummary;
  category_breakdown: AblationCategoryBreakdown[];
  scalability: AblationScalabilityPoint[];
  sample_graph_tla?: { case_id: string; title: string; bytes: number; source: string };
  cases: AblationCase[];
  repair_cases: AblationRepairCase[];
  live_trials: { enabled: boolean; status: string; trials: unknown[] };
};

export type AblationResponse = {
  available: boolean;
  report_available?: boolean;
  running: boolean;
  run_state: {
    state: 'idle' | 'running' | 'succeeded' | 'failed';
    started?: number;
    finished?: number;
    error?: string | null;
    generated_at?: string;
  };
  environment: PlannerEnvironment;
  results: AblationResults | null;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBase()}/api/factory/planner${path}`, init);
  if (!response.ok) {
    const value = await response.json().catch(() => ({}));
    const detail = value.detail;
    if (detail && typeof detail === 'object') {
      const problems = Array.isArray(detail.problems) ? `: ${detail.problems.join('; ')}` : '';
      throw new Error(`${detail.message ?? response.statusText}${problems}`);
    }
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  return response.json();
}

export const plannerApi = {
  codexStatus: () => request<CodexAuthStatus>('/codex/status'),
  codexLogin: (deviceCode = false) =>
    request<CodexAuthStatus>('/codex/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_code: deviceCode }),
    }),
  codexCancel: (loginAttemptId?: string | null) =>
    request<CodexAuthStatus>('/codex/cancel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ login_attempt_id: loginAttemptId ?? '' }),
    }),
  codexLogout: () => request<CodexAuthStatus>('/codex/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }),
  requirements: () => request<{ requirements: RequirementsEntry[]; environment: PlannerEnvironment }>('/requirements'),
  ablation: () => request<AblationResponse>('/ablation'),
  runAblation: () =>
    request<{ status: AblationResponse['run_state'] }>('/ablation/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }),
  runs: () => request<{ runs: PlanSummary[]; busy: string[] }>('/runs'),
  detail: (id: string) => request<PlanDetail>(`/runs/${encodeURIComponent(id)}`),
  ablationReportUrl: () => `${getApiBase()}/api/factory/planner/ablation/report.html`,
  graphJsonUrl: (id: string) => `${getApiBase()}/api/factory/planner/runs/${encodeURIComponent(id)}/graph.json`,
  graphTlaUrl: (id: string) => `${getApiBase()}/api/factory/planner/runs/${encodeURIComponent(id)}/graph.tla`,
  graphTlaText: async (id: string): Promise<string> => {
    const response = await fetch(`${getApiBase()}/api/factory/planner/runs/${encodeURIComponent(id)}/graph.tla`);
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    return response.text();
  },
  roundText: (id: string, round: number, name: 'prompt' | 'reply') =>
    request<RoundText>(`/runs/${encodeURIComponent(id)}/rounds/${round}/${name}`),
  start: (requirementsId: string) =>
    request<{ id: string }>('/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requirements_id: requirementsId }),
    }),
  startCustom: (requirements: Record<string, unknown>) =>
    request<{ id: string }>('/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requirements }),
    }),
};
