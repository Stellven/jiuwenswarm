import { getApiBase } from '../../../utils/env';
import type { CapsuleActivity, EvidenceFile } from '../api';

export type CapsuleCard = {
  name: string;
  title?: string | null;
  used_in_runs?: number;
  featured_analysis_at?: number | null;
  id: string;
  version: string;
  starred: boolean;
  kind: string;
  component: string | null;
  subcomponent: string | null;
  description: string;
  binding: string;
  capabilities: string[];
  digest: string | null;
  expected_digest: string | null;
  integrity: EvidenceFile['integrity'];
  contract_id: string | null;
  strata_mechanism: string | null;
  arm: string | null;
  // Atlas-aligned naming (factory/ccs/atlas-names.json); `name` stays the stable directory id.
  cc_title?: string | null;
  cc_kind?: string | null;
  atlas_cc_id?: string | null;
  cc_component?: string | null;
  cc_target?: string | null;
  cc_summary?: string | null;
  former_names?: string[];
};

export type CapsuleArtifact = {
  run_id: string;
  run_name: string;
  path: string;
  artifact_id: string;
  display_path?: string;
  kind: string;
  media_type: string;
  integrity: EvidenceFile['integrity'];
  sha256: string;
  created: number;
};

export type VerifyReceipt = CapsuleArtifact & {
  call: string;
  release: string | null;
  state: string;
  completeness: string;
  done: boolean | null;
  checks: unknown;
  limitations?: string | null;
};

export type CapsuleMeasurement = {
  run_id: string;
  run_name: string;
  arm: string;
  scope?: 'capsule' | 'combined';
  prompt_tokens: number;
  samples: number;
  ttft_s: number;
  decode_tps: number | null;
  peak_memory_bytes: number | null;
  load_time_s: number | null;
  delta_vs_stock_s: number | null;
  inverse_vs_stock: number | null;
  inverse_vs_cache: number | null;
  gap_closed: number | null;
  observation_ids: string[];
  binary_sha256?: string | null;
};

export type CapsuleAnalysis = {
  run_id: string;
  run_name: string;
  observation_id: string | null;
  report_artifact_id?: string;
  call: string | null;
  path: string | null;
  integrity: EvidenceFile['integrity'] | null;
  artifact_ids: string[];
  kind: string;
  created: number | null;
  limitations: string | null;
  values: unknown;
};

// Each item carries the run and capsule release that produced it; earlier releases' evidence is shown, labelled.
export type EvidenceOrigin = { run_id?: string; run_name?: string; version?: string | null; release?: string | null };

export type BuilderRun = {
  run_id: string;
  run_name: string;
  build: ({ binary_sha256: string; artifact: CapsuleArtifact | null } & EvidenceOrigin) | null;
  lab: (EvidenceOrigin & {
    binary_sha256: string | null;
    artifact: CapsuleArtifact | null;
    parity: boolean | null;
    activation: boolean | null;
    metrics: Record<string, number>;
    scope: string | null;
    limitations: string | null;
  }) | null;
  report: (CapsuleArtifact & EvidenceOrigin) | null;
};

export type CapsuleEvidence = {
  latest_verify_receipt: VerifyReceipt | null;
  latest_builder_run?: BuilderRun | null;
  artifacts: CapsuleArtifact[];
  analyses?: CapsuleAnalysis[];
  measurements: CapsuleMeasurement[];
  runs: { id: string; name: string; kind: string }[];
  node_activity?: Array<{
    run_id: string;
    run_name: string;
    node_id: string;
    live?: boolean;
    capsule: CapsuleActivity;
  }>;
};

export type CapsuleDetail = CapsuleCard & {
  materials: Record<string, string>;
  capability_descriptions?: Record<string, string>;
  sections: Partial<
    Record<
      'guide' | 'method' | 'ontology' | 'source_map' | 'validation' | 'verifier' | 'component' | 'profile' | 'analysis',
      string
    >
  >;
  ontology: unknown;
  component_spec: unknown;
  verifier: string | null;
  contract_clauses: string[];
  files: EvidenceFile[];
  evidence?: CapsuleEvidence;
};

export type CapsuleCatalog = {
  capsules: CapsuleCard[];
  contract: {
    id: string;
    raw: EvidenceFile | null;
    readable: EvidenceFile | null;
    clauses: { id: string; title: string; detail: string }[];
  } | null;
  owner_ontology: EvidenceFile[];
  kinds?: Record<string, { label: string; naming: string; plain: string }>;
};

export type CapsuleFile = EvidenceFile & { content: string; parsed: unknown; truncated: boolean };

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${getApiBase()}/api/factory/capsules${path}`, { signal });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : String(response.status));
  }
  return response.json();
}

export const capsuleApi = {
  catalog: (signal?: AbortSignal, usage = true) => request<CapsuleCatalog>(usage ? '' : '?usage=false', signal),
  detail: (name: string, signal?: AbortSignal) => request<CapsuleDetail>(`/${encodeURIComponent(name)}`, signal),
  file: (name: string, path: string, signal?: AbortSignal) =>
    request<CapsuleFile>(`/${encodeURIComponent(name)}/file?path=${encodeURIComponent(path)}`, signal),
};
