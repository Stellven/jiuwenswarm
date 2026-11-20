import type { EvidenceFile, JsonRecord } from './api';

export const MEASUREMENT_ARMS = ['A', 'A+', 'C1', 'C2', 'C3', 'C4', 'C5', 'D', 'S'] as const;
export type MeasurementArm = (typeof MEASUREMENT_ARMS)[number];
export type MeasurementPhase = 'final' | 'reconnaissance';
export type MeasurementMetric = 'ttft_s' | 'inverse_a' | 'gap' | 'decode_tps' | 'peak_memory_bytes';

export type MeasurementSource = {
  line: number;
  path?: string;
  sha256?: string;
  expected_sha256?: string;
  integrity: 'verified' | 'ledger-match' | 'mismatch' | 'missing' | 'unavailable';
};

type MeasurementIdentity = {
  arm: MeasurementArm;
  phase: MeasurementPhase;
  prompt_tokens: number;
  prompt_sha256: string;
};

type Sample = MeasurementIdentity & {
  ttft_s: number;
  decode_tps: number | null;
  peak_memory_bytes?: number;
  source: MeasurementSource;
  memory_source?: MeasurementSource;
};

type Interval = { low: number; high: number; level: number; n: number; source_lines: number[] };
type Summary = MeasurementIdentity & {
  intervals: Partial<Record<MeasurementMetric, Interval>>;
  source: MeasurementSource;
};

export type MeasurementLedger = { samples: Sample[]; summaries: Summary[]; issues: MeasurementSource[] };
export type MetricValue = {
  value: number;
  n: number;
  sources: MeasurementSource[];
  interval?: Interval;
  intervalSource?: MeasurementSource;
  range?: [number, number];
  controlCounts?: Partial<Record<'A' | 'S', number>>;
};

export type MeasurementRow = {
  arm: MeasurementArm;
  metrics: Partial<Record<MeasurementMetric, MetricValue>>;
};

export type MeasurementPrompt = { tokens: number; hash: string };

type VerifiedArtifact = { artifact_id: string; sha256: string };
type FocusedProfile = { profileSha256: string; binarySha256: string; sourceCommit?: string };
type FocusedEffect = { estimate: number; ci: [number, number]; range: [number, number] };
type FocusedTiming = { ttft: number; decode: number };

type FocusedP4Row = {
  tokens: number;
  n: number;
  control: FocusedTiming;
  candidate: FocusedTiming;
  ttftSaved: FocusedEffect;
  decodeGained: FocusedEffect;
};

export type FocusedP4 = {
  key: string;
  subject: string;
  summary?: string;
  budgetMib: number;
  allocatedMib: number;
  manifest: VerifiedArtifact;
  analysis: VerifiedArtifact;
  verification: VerifiedArtifact;
  report: VerifiedArtifact;
  controlProfile: FocusedProfile;
  candidateProfile: FocusedProfile;
  rows: FocusedP4Row[];
};

const obj = (value: unknown): JsonRecord =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as JsonRecord) : {};
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const hash = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);

function verifiedArtifact(raw: unknown, files: EvidenceFile[], sourceIds: unknown[]) {
  const { artifact_id, sha256 } = obj(raw);
  if (typeof artifact_id !== 'string' || !hash(sha256) || !sourceIds.includes(artifact_id)) return;
  if (files.some((file) => file.integrity === 'verified' && file.sha256 === sha256 &&
    file.artifact_ids?.includes(artifact_id))) {
    return { artifact_id, sha256 };
  }
}

function profile(raw: unknown): FocusedProfile | undefined {
  const { profile_sha256, binary_sha256, source_commit } = obj(raw);
  if (!hash(profile_sha256) || !hash(binary_sha256)) return;
  return {
    profileSha256: profile_sha256,
    binarySha256: binary_sha256,
    sourceCommit: typeof source_commit === 'string' ? source_commit : undefined,
  };
}

function bounds(value: unknown): [number, number] | undefined {
  if (Array.isArray(value) && value.length === 2 && finite(value[0]) && finite(value[1]) && value[0] <= value[1]) {
    return [value[0], value[1]];
  }
}

function effect(raw: unknown): FocusedEffect | undefined {
  const { estimate, conditional_ci95, observed_range } = obj(raw);
  const ci = bounds(conditional_ci95);
  const range = bounds(observed_range);
  if (finite(estimate) && ci && range) return { estimate, ci, range };
}

function timing(raw: unknown): FocusedTiming | undefined {
  const { ttft_s, decode_tps } = obj(raw);
  if (finite(ttft_s) && ttft_s > 0 && finite(decode_tps) && decode_tps > 0) {
    return { ttft: ttft_s, decode: decode_tps };
  }
}

function focusedRow(raw: unknown): FocusedP4Row | undefined {
  const row = obj(raw);
  const tokens = row.prompt_tokens;
  const control = timing(row.control);
  const candidate = timing(row.candidate);
  const ttftSaved = effect(row.paired_ttft_seconds_saved_vs_Aplus);
  const decodeGained = effect(row.paired_decode_tps_gained_vs_Aplus);
  if ((tokens === 512 || tokens === 2048) && row.n === 10 && control && candidate && ttftSaved && decodeGained) {
    return { tokens, n: row.n, control, candidate, ttftSaved, decodeGained };
  }
}

export function focusedP4Reports(observations: JsonRecord[], files: EvidenceFile[]): FocusedP4[] {
  const views = new Map<string, FocusedP4>();
  for (const observation of observations) {
    if (observation.kind !== 'factory_iteration_report' && observation.kind !== 'factory_iteration_report_revision') continue;
    const iteration = obj(observation.values);
    const analysisRecord = obj(iteration.analysis);
    const focus = obj(analysisRecord.focused_comparison);
    const reportRecord = obj(iteration.report);
    const analysisCapsules = Array.isArray(analysisRecord.ccs) ? analysisRecord.ccs : [];
    const gapRelease = analysisCapsules.some((raw) => {
      const capsule = obj(raw);
      return capsule.id === 'factory.spark_gap_analysis' && hash(capsule.release);
    });
    if (iteration.schema !== 'spark-factory-iteration/1' || reportRecord.status !== 'verified-p4' ||
      focus.schema !== 'spark-p4-focused/1' || obj(iteration.lab).status !== 'complete' || !gapRelease) continue;
    const subject = focus.subject_arm;
    const { budget_mib: budgetMib, allocated_mib: allocatedMib } = focus;
    if (typeof subject !== 'string' || !/^(?:C[1-5]|D)(?:-[a-z0-9]+)*$/.test(subject) ||
      !finite(budgetMib) || !Number.isInteger(budgetMib) || !finite(allocatedMib) ||
      allocatedMib <= 0 || allocatedMib > budgetMib || !Array.isArray(focus.rows)) continue;
    const sourceIds = Array.isArray(observation.source_artifacts) ? observation.source_artifacts : [];
    const manifest = verifiedArtifact(obj(iteration.plan).manifest, files, sourceIds);
    const analysis = verifiedArtifact(analysisRecord.result_artifact, files, sourceIds);
    const verification = verifiedArtifact(focus.verification, files, sourceIds);
    const report = verifiedArtifact(reportRecord, files, sourceIds);
    const profiles = obj(focus.profiles);
    const controlProfile = profile(profiles['A+']);
    const candidateProfile = profile(profiles[subject]);
    if (!manifest || !analysis || !verification || !report || !controlProfile || !candidateProfile ||
      !Array.isArray(analysisRecord.output_artifact_ids) ||
      !analysisRecord.output_artifact_ids.includes(verification.artifact_id)) continue;
    const rows = focus.rows.map(focusedRow).filter((row): row is FocusedP4Row => Boolean(row));
    if (focus.rows.length !== 2 || rows.length !== 2 || rows[0].tokens === rows[1].tokens) continue;
    const key = `${report.artifact_id}:${report.sha256}:${manifest.sha256}`;
    views.set(key, {
      key, subject, budgetMib, allocatedMib, manifest, analysis, verification, report, controlProfile,
      summary: typeof reportRecord.summary === 'string' ? reportRecord.summary.trim() : undefined,
      candidateProfile, rows: rows.sort((a, b) => a.tokens - b.tokens),
    });
  }
  return [...views.values()];
}

export function promptOptions(data: MeasurementLedger, phase: MeasurementPhase): MeasurementPrompt[] {
  const prompts = new Map<string, MeasurementPrompt>();
  for (const sample of data.samples) {
    if (sample.phase === phase) {
      const prompt = { tokens: sample.prompt_tokens, hash: sample.prompt_sha256 };
      prompts.set(promptKey(prompt), prompt);
    }
  }
  return [...prompts.values()].sort((a, b) => a.tokens - b.tokens || a.hash.localeCompare(b.hash));
}

export function promptKey(prompt: MeasurementPrompt) {
  return `${prompt.tokens}:${prompt.hash}`;
}

function sampleMetric(
  samples: Sample[],
  metric: 'ttft_s' | 'decode_tps' | 'peak_memory_bytes',
): MetricValue | undefined {
  const distinct = new Map<number, { value: number; source: MeasurementSource }>();
  for (const sample of samples) {
    const source = metric === 'peak_memory_bytes' ? sample.memory_source : sample.source;
    const value = sample[metric];
    if (source && typeof value === 'number') distinct.set(source.line, { value, source });
  }
  const values = [...distinct.values()].sort((a, b) => a.value - b.value);
  if (!values.length) return;
  const middle = Math.floor(values.length / 2);
  const value =
    metric === 'peak_memory_bytes'
      ? values[values.length - 1].value
      : (values[middle].value + values[Math.floor((values.length - 1) / 2)].value) / 2;
  return {
    value,
    n: values.length,
    sources: values.map((item) => item.source),
    range: metric === 'ttft_s' ? [values[0].value, values[values.length - 1].value] : undefined,
  };
}

function matched(identity: MeasurementIdentity, phase: MeasurementPhase, prompt: MeasurementPrompt) {
  return identity.phase === phase && identity.prompt_tokens === prompt.tokens && identity.prompt_sha256 === prompt.hash;
}

export function aggregateMeasurements(
  ledger: MeasurementLedger,
  phase: MeasurementPhase,
  prompt: MeasurementPrompt,
): MeasurementRow[] {
  const samples = ledger.samples.filter((sample) => matched(sample, phase, prompt));
  const summaries = ledger.summaries.filter((summary) => matched(summary, phase, prompt));
  const rows: MeasurementRow[] = MEASUREMENT_ARMS.map((arm) => {
    const group = samples.filter((sample) => sample.arm === arm);
    return {
      arm,
      metrics: {
        ttft_s: sampleMetric(group, 'ttft_s'),
        decode_tps: sampleMetric(group, 'decode_tps'),
        peak_memory_bytes: sampleMetric(group, 'peak_memory_bytes'),
      },
    };
  });
  const stock = rows.find((row) => row.arm === 'A')?.metrics.ttft_s;
  const strata = rows.find((row) => row.arm === 'S')?.metrics.ttft_s;
  for (const row of rows) {
    const ttft = row.metrics.ttft_s;
    if (ttft && stock) {
      row.metrics.inverse_a = {
        value: stock.value / ttft.value,
        n: ttft.n,
        controlCounts: { A: stock.n },
        sources: [...ttft.sources, ...stock.sources],
      };
      if (strata && stock.value > strata.value) {
        row.metrics.gap = {
          value: (stock.value - ttft.value) / (stock.value - strata.value),
          n: ttft.n,
          controlCounts: { A: stock.n, S: strata.n },
          sources: [...ttft.sources, ...stock.sources, ...strata.sources],
        };
      }
    }
    for (const summary of summaries.filter((item) => item.arm === row.arm)) {
      for (const [key, interval] of Object.entries(summary.intervals)) {
        const metric = row.metrics[key as MeasurementMetric];
        const sourceLines = new Set(metric?.sources.map((source) => source.line));
        if (
          metric &&
          metric.n === interval.n &&
          sourceLines.size === interval.source_lines.length &&
          interval.source_lines.every((line) => sourceLines.has(line))
        ) {
          metric.interval = interval;
          metric.intervalSource = summary.source;
        }
      }
    }
  }
  return rows;
}

export function chartScale(rows: MeasurementRow[], metric: MeasurementMetric) {
  const extent = rows.flatMap((row) => {
    const at = row.metrics[metric];
    return at ? [at.value, ...(at.interval ? [at.interval.low, at.interval.high] : [])] : [];
  });
  const low = Math.min(0, ...extent);
  const high = Math.max(metric === 'gap' ? 1 : 0, ...extent);
  const position = (value: number) => ((value - low) / (high - low || 1)) * 100;
  return { position, zero: position(0) };
}
