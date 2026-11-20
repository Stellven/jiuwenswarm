import type { JsonRecord } from './api';

export type MeasurementRow = {
  arm: string;
  prompt: number;
  count: number;
  ttft: number;
  ttftMin: number;
  ttftMax: number;
  decode: number | null;
  memory: number | null;
  available: number | null;
  load: number | null;
  gap: number | null;
  inverseA: number | null;
  inverseAplus: number | null;
  outputHashes: number;
  sources: string[];
  artifacts: string[];
};
export function numeric(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}
export function median(values: (number | null)[]): number | null {
  const measured = values.filter((value): value is number => value !== null).sort((a, b) => a - b);
  const mid = Math.floor(measured.length / 2);
  return !measured.length ? null : measured.length % 2 ? measured[mid] : (measured[mid - 1] + measured[mid]) / 2;
}
function extremum(values: (number | null)[], mode: 'min' | 'max'): number | null {
  const measured = values.filter((value): value is number => value !== null);
  return measured.length ? Math[mode](...measured) : null;
}
export function aggregateMeasurements(observations: JsonRecord[]): MeasurementRow[] {
  const groups = new Map<string, JsonRecord[]>();
  for (const observation of observations) {
    const values = observation.values as JsonRecord | undefined;
    if (
      !values ||
      typeof values.arm !== 'string' ||
      observation.kind !== 'measurement' ||
      values.measurement_eligible === false
    )
      continue;
    if (
      values.warm === false ||
      values.discarded === true ||
      numeric(values.ttft_s) === null ||
      Number(values.ttft_s) <= 0
    )
      continue;
    const key = `${values.arm}:${values.prompt_tokens}`;
    groups.set(key, [
      ...(groups.get(key) || []),
      { ...values, source: observation.obs_id, artifact_refs: observation.source_artifacts },
    ]);
  }
  const rows: MeasurementRow[] = [...groups.values()].map((values) => ({
    arm: String(values[0].arm),
    prompt: Number(values[0].prompt_tokens) || 0,
    count: values.length,
    ttft: median(values.map((item) => numeric(item.ttft_s))) as number,
    ttftMin: extremum(
      values.map((item) => numeric(item.ttft_s)),
      'min',
    ) as number,
    ttftMax: extremum(
      values.map((item) => numeric(item.ttft_s)),
      'max',
    ) as number,
    decode: median(values.map((item) => numeric(item.decode_tps))),
    memory: extremum(
      values.map((item) => numeric(item.peak_memory_bytes)),
      'max',
    ),
    available: extremum(
      values.map((item) => numeric(item.min_mem_available_bytes)),
      'min',
    ),
    load: median(values.map((item) => numeric(item.load_time_s))),
    gap: null,
    inverseA: null,
    inverseAplus: null,
    outputHashes: new Set(values.map((item) => item.output_sha256).filter(Boolean)).size,
    sources: values.map((item) => String(item.source || '')),
    artifacts: [
      ...new Set(values.flatMap((item) => (Array.isArray(item.artifact_refs) ? (item.artifact_refs as string[]) : []))),
    ].filter((id) => /\/result\.json@sha256:/.test(id)),
  }));
  return rows
    .map((row) => {
      const stock = rows.find((item) => item.arm === 'A' && item.prompt === row.prompt)?.ttft;
      const strata = rows.find((item) => item.arm === 'S' && item.prompt === row.prompt)?.ttft;
      const cache = rows.find((item) => item.arm === 'A+' && item.prompt === row.prompt)?.ttft;
      return {
        ...row,
        gap:
          typeof stock === 'number' && typeof strata === 'number' && stock > strata
            ? (stock - row.ttft) / (stock - strata)
            : null,
        inverseA: typeof stock === 'number' ? stock / row.ttft : null,
        inverseAplus: typeof cache === 'number' ? cache / row.ttft : null,
      };
    })
    .sort((a, b) => a.prompt - b.prompt || a.arm.localeCompare(b.arm));
}
export function gapScale(rows: MeasurementRow[]) {
  const gaps = rows.flatMap((row) => (row.gap === null ? [] : [row.gap]));
  const low = Math.min(0, ...gaps);
  const high = Math.max(1, ...gaps);
  return { position: (gap: number) => ((gap - low) / (high - low)) * 100, zero: (-low / (high - low)) * 100 };
}
