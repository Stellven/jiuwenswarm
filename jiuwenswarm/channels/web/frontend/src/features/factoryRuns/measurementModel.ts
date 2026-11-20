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
