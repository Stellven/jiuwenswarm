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
  source_excerpt?: Record<string, string | number>;
  launch_verdict?: QuietVerdict;
  corrected_verdict?: QuietVerdict;
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

export type QuietVerdict = { status: string; reasons: string[] };
export type EngineSource = { path: string; line?: number; record?: string | number; sha256?: string };
export type Delivery = {
  completed: number;
  total: number;
  image_delivered: boolean;
  measured: boolean;
  decision?: { kind: string; reason?: string; id: string } | null;
};
export type Benchmark = {
  schema: 'engine-bench/1';
  status: 'ready' | 'unavailable';
  rows: EngineRow[];
  delivery?: Delivery;
};

export function deliveryHeadline(delivery?: Delivery) {
  if (!delivery?.total) return '';
  return [
    `${delivery.completed} of ${delivery.total} nodes complete`,
    delivery.image_delivered && 'Engine image delivered',
    delivery.measured && 'Lab measured',
  ]
    .filter(Boolean)
    .join(' · ');
}
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

export const finalRun = 'r8-final-bench';

const armTitles: Record<string, string> = {
  A: 'A · NVFP4 baseline',
  P: 'P · mixed 2-bit + prefill plan',
};

export function isReportArm(row: EngineRow) {
  return row.run === finalRun && row.kind !== 'accuracy' && (row.arm === 'A' || row.arm === 'P');
}

export function excluded(row: EngineRow) {
  return Boolean(
    row.error || (row.corrected_verdict ? row.corrected_verdict.status !== 'accepted' : row.quiet?.eligible === false),
  );
}

export function armLabel(row: EngineRow) {
  const title = isReportArm(row) && row.arm ? armTitles[row.arm] : undefined;
  if (title) return title;
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

export type Ratio = { candidate: EngineRow; baselines: EngineRow[]; value: number; totalSpeedup?: number };

export function ratios(rows: EngineRow[]): Ratio[] {
  const eligible = rows.filter(
    (row) =>
      isReportArm(row) &&
      row.kind === 'performance' &&
      !excluded(row) &&
      Boolean(row.request?.name) &&
      numeric(row.request?.prompt_tokens) &&
      Boolean(row.request?.state) &&
      numeric(row.metrics?.ttft_ms) &&
      row.metrics.ttft_ms > 0,
  );
  const baseline = eligible.filter((row) => row.arm === 'A');
  return eligible.flatMap((candidate) => {
    if (
      candidate.arm !== 'P' ||
      (candidate.corrected_verdict?.status ?? (candidate.quiet?.eligible ? 'accepted' : '')) !== 'accepted'
    )
      return [];
    const baselines = baseline.filter(
      (row) =>
        row.request?.name === candidate.request?.name &&
        row.request?.prompt_tokens === candidate.request?.prompt_tokens &&
        row.request?.state === candidate.request?.state,
    );
    if (!baselines.length) return [];
    const peers = eligible.filter((row) => row.arm === 'P' && row.request?.name === candidate.request?.name &&
      row.request?.state === candidate.request?.state);
    const totals = (samples: EngineRow[]) => samples.map((row) => row.metrics?.total_ms).filter(numeric);
    return [
      {
        candidate,
        baselines,
        value: median(baselines.map((row) => row.metrics!.ttft_ms!)) / median(peers.map((row) => row.metrics!.ttft_ms!)),
        totalSpeedup: totals(peers).length && totals(baselines).length
          ? median(totals(baselines)) / median(totals(peers)) : undefined,
      },
    ];
  });
}

export function median(values: number[]) {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

// Arms in lab order: A first, then the letters in order.
export function armOrder(a: EngineRow, b: EngineRow) {
  return armLabel(a).localeCompare(armLabel(b));
}
