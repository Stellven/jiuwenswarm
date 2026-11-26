export type EngineRow = {
  schema: 'engine-bench/1';
  id: string;
  kind: 'performance' | 'load' | 'accuracy';
  date?: string;
  run?: string;
  arm?: string;
  comparison_group?: string | null;
  label?: 'measured' | 'indicative';
  engine?: { name?: string; image?: string; binary?: string; commit?: string; sha256?: string } | null;
  pack?: {
    name?: string;
    format?: string;
    bytes?: number;
    bits_per_weight?: number;
    census_digest?: string;
    census?: unknown;
  } | null;
  settings?: {
    b?: number;
    ub?: number;
    moe_cache_mib?: number;
    ctx?: number;
    np?: number;
    cpu_moe?: boolean | number;
    fitt?: number;
  } | null;
  request?: {
    name?: string;
    prompt_tokens?: number;
    n_predict?: number;
    state?: 'cold' | 'warm';
    repeat?: number;
    generated_tokens?: number;
    cached_tokens?: number;
    prefill_chunks?: number[];
  } | null;
  metrics?: Partial<Record<Metric, number>> | null;
  memory?: {
    peak_rss?: number;
    peak_cgroup_mib?: number;
    min_available?: number;
    device?: Partial<Record<Device, number>> | null;
    budget?: number;
    fit_margin?: number;
  } | null;
  quiet?: { load1?: number; processes?: unknown; eligible?: boolean | null; reason?: string } | null;
  source: EngineSource;
  sources?: EngineSource[];
  attempt_id?: string;
  test?: string;
  n?: number;
  acc?: number;
  reference_acc?: number;
  delta?: number;
  interval?: { lo?: number; hi?: number } | null;
  margin?: number;
  verdict?: string;
  error?: string | null;
};

export type EngineSource = { path: string; line?: number; record?: string | number; sha256?: string };
export type Benchmark = { schema: 'engine-bench/1'; status: 'ready' | 'unavailable'; rows: EngineRow[] };
export type Metric = 'ttft_ms' | 'decode_tps' | 'prefill_tps' | 'total_ms' | 'load_s' | 'server_prefill_ms';
export type Device = 'model' | 'kv' | 'compute' | 'moe_cache';

export const devices: [Device, string][] = [
  ['model', 'Model'],
  ['kv', 'KV cache'],
  ['compute', 'Compute'],
  ['moe_cache', 'MoE cache'],
];

export const numeric = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
export const fmt = (value: number, digits = 1) => value.toLocaleString('en-US', { maximumFractionDigits: digits });

export function cohort(row: EngineRow) {
  return row.comparison_group ?? row.run ?? 'Unknown run';
}

export function armLabel(row: EngineRow) {
  if (row.arm === 'A' && row.run === 'nov25-lab-abcde') return 'A · Nov 25, E0 on NVFP4, Q2_K-era lab';
  return [row.arm, row.engine?.name, row.pack?.format ?? row.pack?.name].filter(Boolean).join(' · ') || 'Unknown arm';
}

export function quietStatus(row: EngineRow) {
  if (row.quiet?.eligible === false) return `Excluded · ${row.quiet.reason || 'Quiet gate failed'}`;
  if (row.quiet?.eligible === true) return 'Quiet gate passed';
  return 'Quiet gate unrecorded';
}

export function evidenceLabel(row: EngineRow) {
  if (row.label === 'measured') return 'Measured';
  if (row.label === 'indicative') return 'Indicative';
  return 'Unmeasured';
}

export function sourceRef({ path, line, record }: EngineSource) {
  return `${path}${line == null ? '' : `:${line}`}${record == null ? '' : ` · ${record}`}`;
}

export function armKey(row: EngineRow) {
  const { engine, pack, settings } = row;
  return JSON.stringify([
    row.run,
    row.arm,
    engine?.sha256 ?? engine?.commit ?? engine?.image ?? engine?.binary ?? engine?.name,
    pack?.name,
    pack?.format,
    pack?.census_digest,
    settings?.b,
    settings?.ub,
    settings?.moe_cache_mib,
    settings?.ctx,
    settings?.np,
    settings?.cpu_moe,
    settings?.fitt,
  ]);
}

export function groupBy<T>(items: T[], key: (item: T) => string) {
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const id = key(item);
    const group = groups.get(id);
    if (group) group.push(item);
    else groups.set(id, [item]);
  }
  return groups;
}

export type Ratio = { candidate: EngineRow; base: EngineRow; value: number; label: string };
export function ratios(rows: EngineRow[], from = 'A', to?: string): Ratio[] {
  const eligible = rows.filter(
    (row) =>
      row.quiet?.eligible !== false &&
      !row.error &&
      row.label &&
      numeric(row.request?.prompt_tokens) &&
      numeric(row.request?.n_predict) &&
      row.request?.state &&
      numeric(row.metrics?.total_ms) &&
      row.metrics.total_ms > 0,
  );
  const baselines = eligible.filter(
    (row) =>
      row.arm === from &&
      (from !== 'A' || (row.run !== 'nov24-lab-abc' && /\bNVFP4\b/i.test(row.pack?.format ?? row.pack?.name ?? ''))),
  );
  return eligible.flatMap((candidate) => {
    if (candidate.arm === from || (to && candidate.arm !== to)) return [];
    const matched = baselines.filter(
      (base) =>
        base.request?.prompt_tokens === candidate.request?.prompt_tokens &&
        base.request?.n_predict === candidate.request?.n_predict &&
        base.request?.state === candidate.request?.state,
    );
    const local = matched.filter((base) => cohort(base) === cohort(candidate));
    const historical =
      from === 'A' && candidate.run === 'r8-lab' ? matched.filter((base) => base.run === 'nov25-lab-abcde') : [];
    const scope = local.length ? local : historical;
    const sameRepeat = scope.filter((base) => base.request?.repeat === candidate.request?.repeat);
    const choices = sameRepeat.length ? sameRepeat : scope;
    if (choices.length !== 1) return [];
    const base = choices[0];
    const sameBinary = Boolean(base.engine?.sha256 && base.engine.sha256 === candidate.engine?.sha256);
    const measured =
      sameBinary &&
      cohort(base) === cohort(candidate) &&
      base.label === 'measured' &&
      candidate.label === 'measured' &&
      base.quiet?.eligible === true &&
      candidate.quiet?.eligible === true;
    return [
      {
        candidate,
        base,
        value: base.metrics!.total_ms! / candidate.metrics!.total_ms!,
        label: measured ? 'Measured' : 'Indicative',
      },
    ];
  });
}
