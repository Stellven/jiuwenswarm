/** Public CC workbench contract. Never accepts raw worker/fixture/model packets. */
/** Root slot phase when the readiness projection carries it (W4 durable slots). */
export type CcSlotPhase = 'READY' | 'BLOCKED' | 'CLAIMED' | 'LAUNCHED' | 'PREPARING' | 'FAILED';
export interface CcActionGate {
  allowed: boolean;
  revision?: string;
  blocker: string | null;
  phase?: CcSlotPhase;
}
/** Public view of one paired batched benchmark report (ai4r-rsi-capsule-benchmark-report:1). */
export interface CcBenchmark {
  report_ref: { id: string; sha256: string } | null;
  /** 1 − geomean(candidate/parent median ratio); negative means slower. */
  relative_gain: number | null;
  /** 95% bootstrap interval of the candidate/parent ratio [lower, upper]. */
  ratio_confidence_interval: [number, number] | null;
  gates: { minimum_gain: boolean | null; ci_upper_bound: boolean | null; max_workload_regression: boolean | null };
  objective_met: boolean | null;
  protected_jobs: number | null;
  repetitions: number | null;
  workloads: { id: string; median_ratio: number | null }[] | null;
}
export type CcLatencyMethod = 'paired_batched_benchmark' | 'single_job_floor';
/** Why a candidate's paired benchmark ran or not (lineage:2); null when unrecorded. */
export interface CcBenchmarkStatus {
  status: 'ran' | 'not_run' | 'skipped';
  reason: string | null;
}
/** The parent A/A run (candidate = parent): benchmark self-noise, never a gain. */
export interface CcBenchmarkBaselineStatus {
  kind: 'parent_a_a' | null;
  status: 'measured' | 'skipped' | 'failed';
  reason: string | null;
}
/**
 * ai4r-cc-rsi-lineage:1 — every value is measured or null (unknown); never defaulted.
 * ai4r-cc-rsi-lineage:2 adds the benchmark fields below (absent on :1 rows).
 */
export interface CcLoopIteration {
  iteration: number;
  node_id: string | null;
  candidate_ref: { id: string; sha256: string } | null;
  status: 'passed' | 'failed' | 'evaluation_failed' | 'not_evaluated' | 'unknown';
  kept: boolean | null;
  best: boolean;
  passed_count: number | null;
  case_count: number | null;
  correctness_parent: number | null;
  correctness_candidate: number | null;
  latency_ratio: number | null;
  noise_floor_ratio: number | null;
  above_noise: boolean | null;
  improved: boolean | null;
  regressed: boolean | null;
  summary: string | null;
  feedback: string | null;
  rationale: string | null;
  failing_cases: { id: string; fixture_set: 'public' | 'held_out' | null }[] | null;
  failure: { exception_type: string | null; message: string | null } | null;
  model_calls: number | null;
  elapsed_s: number | null;
  latency_method?: CcLatencyMethod | null;
  benchmark?: CcBenchmark | null;
  /** Why an improvement may be claimed; null means no claim. */
  improvement_basis?: 'correctness' | 'paired_batched_benchmark' | null;
  benchmark_status?: CcBenchmarkStatus | null;
}
export interface CcRunLineage {
  schema: 'ai4r-cc-rsi-lineage:1' | 'ai4r-cc-rsi-lineage:2';
  /** Parent A/A report (benchmark self-noise on the host); never a candidate gain. */
  benchmark_baseline?: CcBenchmark | null;
  benchmark_baseline_status?: CcBenchmarkBaselineStatus | null;
  max_iterations: number | null;
  completed_iterations: number | null;
  stop_reason: 'max_iterations' | 'no_progress' | 'budget' | 'deadline' | 'error' | null;
  model_backend: { kind: string | null; model: string | null; pinned_sha256: string | null } | null;
  model_calls: number | null;
  parent_node_id: string | null;
  best_iteration: number | null;
  best_node_id: string | null;
  parent: {
    status: CcLoopIteration['status'];
    passed_count: number | null;
    case_count: number | null;
    protected_wall_s: number | null;
    failure: CcLoopIteration['failure'];
  };
  iterations: CcLoopIteration[];
}
export interface CcTarget {
  id: string;
  name: string;
  parent_hash: string | null;
  active_hash: string | null;
  run: CcActionGate;
}
export interface CcBudget {
  elapsed_seconds: number | null;
  limit_seconds: number | null;
  setup_calls: number | null;
  diagnosis_calls: number | null;
  proposal_calls: number | null;
  generation_call_limit: number | null;
  cost: number | null;
  currency: string | null;
}
export interface CcRun {
  id: string;
  target_id: string;
  stage: string;
  status: string;
  blockers: string[];
  budget: CcBudget;
  activity: { id: string; at: string; stage: string; status: string; summary: string }[];
  /** Absent on legacy single-attempt records (historical Screening, R1/R2). */
  lineage?: CcRunLineage;
  progress?: {
    observed_at: number;
    iteration: number | null;
    max_iterations: number | null;
    completed_iterations: number | null;
    model_calls: number | null;
    executions: number | null;
    execution_limit: number | null;
    stale: boolean;
    source: 'engine' | 'observation';
  };
}
export interface CcNode {
  id: string;
  target_id: string;
  run_id: string | null;
  parent_id: string | null;
  hash: string;
  label: string;
  evaluation_status: string;
  security_status?: 'NOT_APPLICABLE' | 'UNQUALIFIED' | 'SECURITY_DEFERRED' | 'QUALIFIED';
  admission_status: string;
  activation_status: string;
  correctness: string | null;
  speed: string | null;
  noise: string | null;
  evidence_refs: { id: string; sha256: string }[];
  operator_receipts: {
    action: 'admit' | 'activate';
    actor: string;
    at: string;
    receipt_ref: { id: string; sha256: string };
  }[];
  admit: CcActionGate;
  activate: CcActionGate;
}
export interface CcSnapshot {
  schema_version: '1';
  revision: string;
  generated_at: string | null;
  availability: string;
  blocker: string | null;
  targets: CcTarget[];
  runs: CcRun[];
  nodes: CcNode[];
}
export interface CcCandidateDetail {
  node_id: string;
  candidate_hash: string;
  path: string;
  parent_code: string | null;
  candidate_code: string | null;
  rationale: string | null;
  blocker: string | null;
}
export interface CcActionReceipt {
  action: 'admit' | 'activate';
  node_id: string;
  candidate_hash: string;
  actor: string;
  receipt_ref: { id: string; sha256: string };
}
export interface CcRunReceipt {
  client_request_id: string;
  target_id: string;
  revision: string;
  run_id: string;
  status: 'ACCEPTED_UNQUALIFIED';
  security_status: 'SECURITY_DEFERRED';
  receipt_ref: { id: string; sha256: string };
}

/** Installed Source catalog only; never a Library baseline or execution grant. */
export interface CcSourceTarget {
  capsule_name: string;
  scope: string;
  metrics: string[];
  parent_code_sha256: string | null;
  checks_sha256: string | null;
  public_fixture_count: number;
  source_available: boolean;
  public_evaluation_available: boolean;
  adapter_blocker: string;
  source_evolution_rsi: string;
  source_evolution_may_change: string[] | null;
  target_id?: string;
  revision?: string | null;
  run_id?: string | null;
  development_grant_status: 'READY' | 'BLOCKED' | 'NOT_ESTABLISHED';
  run?: CcActionGate;
}
export interface CcSourceCatalog {
  schema_version: '1';
  workspace_id: string;
  targets: CcSourceTarget[];
}
