import { getApiBase } from '../../../utils/env';
import type { EvidenceFile } from '../api';

export type CapsuleCard = {
  name: string;
  title?: string;
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

export type CapsuleEvidence = {
  latest_verify_receipt: VerifyReceipt | null;
  artifacts: CapsuleArtifact[];
  analyses?: CapsuleAnalysis[];
  measurements: CapsuleMeasurement[];
  runs: { id: string; name: string; kind: string }[];
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
  catalog: (signal?: AbortSignal) => request<CapsuleCatalog>('', signal),
  detail: (name: string, signal?: AbortSignal) => request<CapsuleDetail>(`/${encodeURIComponent(name)}`, signal),
  file: (name: string, path: string, signal?: AbortSignal) =>
    request<CapsuleFile>(`/${encodeURIComponent(name)}/file?path=${encodeURIComponent(path)}`, signal),
};
