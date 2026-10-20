import type { ResearchRef } from '../../utils/researchClient';

export interface ResearchArtifact {
  path: string;
  mediaType: string;
  ref: ResearchRef;
  content: string;
}

export interface ResearchArtifactSection {
  key: string;
  value: unknown;
}

export interface StructuredResearchArtifact {
  kind: 'brief' | 'intent' | 'measurements' | 'verdict';
  sections: ResearchArtifactSection[];
  metrics?: ResearchMetricRow[];
}

export interface ResearchMetricRow {
  id: string;
  baseline: number | null;
  treatment: number | null;
  baselineReason?: string | null;
  treatmentReason?: string | null;
  unit?: string;
  delta?: number | null;
  classification?: string;
  details: unknown;
}

const briefFields = [
  'objective',
  'domain_lane',
  'in_scope',
  'out_of_scope',
  'mandatory_requirements',
  'optional_preferences',
  'constraints',
  'target_metrics',
  'deliverables',
  'acceptance_expectations',
  'evidence_obligations',
  'assumptions',
  'unresolved_items',
  'confirmation',
];
const intentFields = [
  'context',
  'in_scope',
  'out_of_scope',
  'constraints',
  'preferences',
  'user_targets',
  'uncertainties',
  'readiness',
];

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function measuredValue(value: unknown): value is number | null {
  return value === null || (typeof value === 'number' && Number.isFinite(value));
}

function metricRows(value: Record<string, unknown>): ResearchMetricRow[] | null {
  const findings = value.id === 'evaluation_verdict';
  const rows = findings ? value.findings : value.metrics;
  if (!Array.isArray(rows) || rows.length === 0) return null;
  const result: ResearchMetricRow[] = [];
  const ids = new Set<string>();
  for (const row of rows) {
    if (!record(row) || typeof row.metric_id !== 'string' || !row.metric_id || ids.has(row.metric_id)) return null;
    ids.add(row.metric_id);
    if (findings) {
      if (
        !measuredValue(row.baseline_value) ||
        !measuredValue(row.treatment_value) ||
        typeof row.classification !== 'string' ||
        !['PASS', 'FAIL', 'INCONCLUSIVE', 'CONDITIONALLY_ACCEPTABLE'].includes(row.classification)
      )
        return null;
      result.push({
        id: row.metric_id,
        baseline: row.baseline_value,
        treatment: row.treatment_value,
        classification: row.classification,
        details: row,
      });
    } else {
      if (
        !record(row.baseline) ||
        !record(row.treatment) ||
        !measuredValue(row.baseline.value) ||
        !measuredValue(row.treatment.value) ||
        !measuredValue(row.delta) ||
        typeof row.unit !== 'string'
      )
        return null;
      const reason = (entry: Record<string, unknown>) =>
        entry.unmeasured_reason === null || typeof entry.unmeasured_reason === 'string';
      if (!reason(row.baseline) || !reason(row.treatment)) return null;
      result.push({
        id: row.metric_id,
        baseline: row.baseline.value,
        treatment: row.treatment.value,
        baselineReason: row.baseline.unmeasured_reason as string | null,
        treatmentReason: row.treatment.unmeasured_reason as string | null,
        unit: row.unit,
        delta: row.delta,
        details: row,
      });
    }
  }
  return result;
}

/** A faithful display projection, never schema validation or acceptance. */
export function structuredResearchArtifact(content: string): StructuredResearchArtifact | null {
  let value: unknown;
  try {
    value = JSON.parse(content);
  } catch {
    return null;
  }
  if (!record(value)) return null;
  if (value.schema_version === '2.0.0' && ['benchmark_payload', 'evaluation_verdict'].includes(String(value.id))) {
    const metrics = metricRows(value);
    if (!metrics) return null;
    const kind = value.id === 'benchmark_payload' ? 'measurements' : 'verdict';
    const fields =
      kind === 'measurements'
        ? ['repeat_count', 'seed', 'run_order']
        : ['classification', 'completeness', 'plausibility', 'blockers', 'residual_risks', 'followups'];
    return { kind, metrics, sections: fields.filter((key) => key in value).map((key) => ({ key, value: value[key] })) };
  }
  if (value.schema_version === '2.0.0' && record(value.objective) && Array.isArray(value.mandatory_requirements)) {
    return {
      kind: 'brief',
      sections: briefFields.filter((key) => key in value).map((key) => ({ key, value: value[key] })),
    };
  }
  if (value.schema_version === '1.0.0' && record(value.interpretation)) {
    const interpretation = value.interpretation;
    if (!['problem', 'desired_change', 'requested_result'].every((key) => key in interpretation)) return null;
    return {
      kind: 'intent',
      sections: [
        ...['problem', 'desired_change', 'requested_result'].map((key) => ({ key, value: interpretation[key] })),
        ...intentFields.filter((key) => key in value).map((key) => ({ key, value: value[key] })),
      ],
    };
  }
  return null;
}

export function artifactStanding(artifact: ResearchArtifact, accepted: ResearchRef[], candidates: ResearchRef[]) {
  const matches = (ref: ResearchRef) => ref.id === artifact.ref.id && ref.sha256 === artifact.ref.sha256;
  return accepted.some(matches) ? 'accepted' : candidates.some(matches) ? 'candidate' : 'evidence';
}

export function artifactText(value: unknown): { text: string; detail: unknown } {
  if (!record(value))
    return { text: typeof value === 'string' ? value : (JSON.stringify(value, null, 2) ?? ''), detail: null };
  const primary = ['text', 'target_text', 'description', 'question', 'reason', 'name'].find(
    (key) => typeof value[key] === 'string',
  );
  if (!primary) return { text: JSON.stringify(value, null, 2), detail: null };
  const { [primary]: text, ...detail } = value;
  return { text: text as string, detail: Object.keys(detail).length ? detail : null };
}
