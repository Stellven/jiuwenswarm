import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import type { JsonRecord } from './api';

type Row = {
  arm: string;
  prompt: number;
  count: number;
  ttft: number | null;
  decode: number | null;
  memory: number | null;
  load: number | null;
  gap: number | null;
  sources: string[];
};
function numeric(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}
function mean(values: (number | null)[]): number | null {
  const measured = values.filter((value): value is number => value !== null);
  return measured.length ? measured.reduce((sum, value) => sum + value, 0) / measured.length : null;
}
function format(value: number | null) {
  return value === null ? '—' : value.toFixed(3);
}

export function Measurements({ observations }: { observations: JsonRecord[] }) {
  const { t } = useTranslation();
  const rows = useMemo(() => {
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
      if (values.warm === false || values.discarded === true) continue;
      const key = `${values.arm}:${values.prompt_tokens}`;
      groups.set(key, [...(groups.get(key) || []), { ...values, source: observation.obs_id }]);
    }
    const result: Row[] = [...groups.values()].map((values) => ({
      arm: String(values[0].arm),
      prompt: Number(values[0].prompt_tokens) || 0,
      count: values.length,
      ttft: mean(values.map((item) => numeric(item.ttft_s))),
      decode: mean(values.map((item) => numeric(item.decode_tps))),
      memory: mean(values.map((item) => numeric(item.peak_memory_bytes))),
      load: mean(values.map((item) => numeric(item.load_time_s))),
      gap: null,
      sources: values.map((item) => String(item.source || '')),
    }));
    return result
      .map((row) => {
        const stock = result.find((item) => item.arm === 'A' && item.prompt === row.prompt)?.ttft;
        const strata = result.find((item) => item.arm === 'S' && item.prompt === row.prompt)?.ttft;
        return {
          ...row,
          gap:
            typeof stock === 'number' && typeof strata === 'number' && row.ttft !== null && stock !== strata
              ? (stock - row.ttft) / (stock - strata)
              : null,
        };
      })
      .sort((a, b) => a.prompt - b.prompt || a.arm.localeCompare(b.arm));
  }, [observations]);
  return (
    <section data-testid="factory-runs-measurements">
      <p className="factory-muted" data-testid="factory-runs-gap-formula">
        {t('factoryRuns.gapFormula')}
      </p>
      <p className="factory-muted" data-testid="factory-runs-measurement-method">
        {t('factoryRuns.measurementMethod')}
      </p>
      <div className="factory-table-scroll">
        <table className="factory-measurements" data-testid="factory-runs-measurement-table">
          <thead>
            <tr>
              {['arm', 'promptTokens', 'repeats', 'ttft', 'decode', 'memory', 'loadTime', 'gapClosed'].map((key) => (
                <th key={key}>{t(`factoryRuns.${key}`)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={`${row.arm}-${row.prompt}`}
                data-testid="factory-runs-measurement-row"
                data-variant={`${row.arm}-${row.prompt}`}
                title={row.sources.join('\n')}
              >
                <td>{row.arm}</td>
                <td>{row.prompt}</td>
                <td>{row.count}</td>
                <td>{format(row.ttft)}</td>
                <td>{format(row.decode)}</td>
                <td>{format(row.memory === null ? null : row.memory / 2 ** 30)}</td>
                <td>{format(row.load)}</td>
                <td>{row.gap === null ? '—' : `${(row.gap * 100).toFixed(1)}%`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows.length && <p data-testid="factory-runs-measurements-empty">{t('factoryRuns.noEvidence')}</p>}
      <div className="factory-gap-chart" data-testid="factory-runs-gap-chart">
        {rows
          .filter((row) => row.gap !== null)
          .map((row) => (
            <div key={`${row.arm}-${row.prompt}`}>
              <span>
                {row.arm} · {row.prompt}
              </span>
              <div className="factory-gap-track">
                <span style={{ width: `${Math.max(0, Math.min(100, (row.gap || 0) * 100))}%` }} />
              </div>
              <span>{((row.gap || 0) * 100).toFixed(1)}%</span>
            </div>
          ))}
      </div>
    </section>
  );
}
