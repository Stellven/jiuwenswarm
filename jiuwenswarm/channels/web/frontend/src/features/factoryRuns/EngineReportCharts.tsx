import { useState } from 'react';
import type { ReactNode } from 'react';
import { armKey, armLabel, armOrder, devices, excluded, fmt, groupBy, median, numeric } from './engineBenchModel';
import type { EngineRow, Metric, Ratio } from './engineBenchModel';

export type Inspect = (row: EngineRow, related?: EngineRow[]) => void;

export function RowValue({
  row,
  related,
  ariaLabel,
  inspect,
  children,
}: {
  row: EngineRow;
  related?: EngineRow[];
  ariaLabel?: string;
  inspect: Inspect;
  children: string;
}) {
  return (
    <button
      type="button"
      className="engine-value"
      onClick={() => inspect(row, related)}
      data-testid="factory-runs-engine-row-value"
      data-variant={row.id}
      aria-label={ariaLabel ?? `${children}. Open measurement sources`}
    >
      {children}
    </button>
  );
}

export function Panel({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section className="factory-story-card engine-panel" data-testid={`factory-runs-engine-${id}`}>
      <h2>{title}</h2>
      {children}
    </section>
  );
}

export function Empty({ children = 'No data available.' }: { children?: ReactNode }) {
  return <p className="engine-empty">{children}</p>;
}

export function LengthPlot({
  rows,
  metric,
  unit,
  scale = 1,
  inspect,
}: {
  rows: EngineRow[];
  metric: Metric;
  unit: string;
  scale?: number;
  inspect: Inspect;
}) {
  const [shownState, setShownState] = useState<'warm' | 'cold'>('warm');
  const all = rows
    .filter((row) => !excluded(row))
    .flatMap((row) => {
      const tokens = row.request?.prompt_tokens;
      const value = row.metrics?.[metric];
      return numeric(tokens) && numeric(value) ? [{ row, tokens, score: value / scale }] : [];
    });
  if (!all.length) return <Empty />;
  const states = new Set(all.map(({ row }) => row.request?.state));
  export function AccuracyPlot({ rows, inspect }: { rows: EngineRow[]; inspect: Inspect }) {
  return (
    <ul className="engine-accuracy">
      {rows.map((row) => (
        <li key={row.id}>
          <div className="engine-memory-values">
            {numeric(row.reference_acc) && (
              <RowValue row={row} inspect={inspect}>NVFP4 {fmt(row.reference_acc * 100)}%</RowValue>
            )}
            {numeric(row.acc) && (
              <RowValue row={row} inspect={inspect}>Mixed 2-bit {fmt(row.acc * 100)}%</RowValue>
            )}
            {numeric(row.n) && <span>{row.n} questions</span>}
          </div>
        </li>
      ))}
    </ul>
  );
}
