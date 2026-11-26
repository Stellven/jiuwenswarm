import { useState } from 'react';
import type { ReactNode } from 'react';
import { armKey, armLabel, armOrder, devices, excluded, fmt, groupBy, median, numeric } from './engineBenchModel';
import type { EngineRow, Metric, Ratio } from './engineBenchModel';

export type Inspect = (row: EngineRow, related?: EngineRow[]) => void;

export function RowValue({
  row,
  related,
  inspect,
  children,
}: {
  row: EngineRow;
  related?: EngineRow[];
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
      aria-label={`${children}. Open measurement sources`}
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
  const all = rows.flatMap((row) => {
    const tokens = row.request?.prompt_tokens;
    const value = row.metrics?.[metric];
    return numeric(tokens) && numeric(value) ? [{ row, tokens, score: value / scale }] : [];
  });
  if (!all.length) return <Empty />;
  const states = new Set(all.map(({ row }) => row.request?.state));
  const points = states.has(shownState) ? all.filter(({ row }) => row.request?.state === shownState) : all;
  const lengths = [...new Set(points.map((point) => point.tokens))].sort((a, b) => a - b);
  const groups = [...groupBy(points, ({ row }) => JSON.stringify([armKey(row), row.request?.state])).values()].sort(
    (a, b) => armOrder(a[0].row, b[0].row),
  );
  const x = (length: number) => 96 + (lengths.indexOf(length) * 524) / Math.max(1, lengths.length - 1);
  const max = Math.max(1, ...points.map((point) => point.score));
  const y = (value: number) => 195 - (value * 174) / max;
  const digits = max >= 100 ? 0 : 1;
  return (
    <>
      {states.has('warm') && states.has('cold') && (
        <div className="engine-toggle" role="group" aria-label="Request state">
          {(['warm', 'cold'] as const).map((state) => (
            <button
              key={state}
              type="button"
              aria-pressed={shownState === state}
              onClick={() => setShownState(state)}
              data-testid="factory-runs-engine-state"
              data-variant={state}
            >
              {state === 'warm' ? 'Warm (pages cached)' : 'Cold (pages evicted)'}
            </button>
          ))}
        </div>
      )}
      <div className="engine-plot-scroll">
        <svg
          className="engine-plot"
          viewBox="0 0 680 245"
          aria-label={`${unit} by rendered prompt tokens`}
          role="group"
        >
          {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
            <g key={tick}>
              <line className="engine-gridline" x1="96" x2="637" y1={y(max * tick)} y2={y(max * tick)} />
              <text x="88" y={y(max * tick) + 5} textAnchor="end">
                {`${fmt(max * tick, digits)} ${unit}`}
              </text>
            </g>
          ))}
          {lengths.map((length) => (
            <text key={length} x={x(length)} y="217" textAnchor="middle">
              {fmt(length)}
            </text>
          ))}
          <text x="350" y="240" textAnchor="middle">
            Rendered prompt tokens
          </text>
          {groups.map((group) => {
            const first = group[0];
            const state = first.row.request?.state;
            const accepted = group.filter(({ row }) => !excluded(row));
            const byLength = [...groupBy(accepted, ({ tokens }) => String(tokens)).values()].sort(
              (a, b) => a[0].tokens - b[0].tokens,
            );
            const path = byLength
              .map((observations) => {
                const middle = median(observations.map(({ score }) => score));
                return `${x(observations[0].tokens)},${y(middle)}`;
              })
              .join(' ');
            return (
              <g key={first.row.id} className="engine-series" data-arm={first.row.arm}>
                {byLength.length > 1 && (
                  <polyline
                    points={path}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeDasharray={state === 'warm' ? '6 4' : undefined}
                  />
                )}
                {group.map(({ row, tokens, score }) => {
                  const label = `${armLabel(row)} · ${state ?? 'State unknown'} · ${fmt(tokens)} tokens · ${fmt(score)} ${unit}`;
                  return (
                    <circle
                      key={row.id}
                      cx={x(tokens)}
                      cy={y(score)}
                      r="5"
                      stroke="currentColor"
                      fill={state === 'warm' ? 'var(--color-surface-card)' : 'currentColor'}
                      className={excluded(row) ? 'engine-excluded' : undefined}
                      tabIndex={0}
                      role="button"
                      aria-label={label}
                      onClick={() => inspect(row)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault();
                          inspect(row);
                        }
                      }}
                      data-testid="factory-runs-engine-plot-source"
                      data-variant={row.id}
                    >
                      <title>{label}</title>
                    </circle>
                  );
                })}
              </g>
            );
          })}
        </svg>
      </div>
      <ul className="engine-legend">
        {groups.map((group) => {
          const { row } = group[0];
          return (
            <li key={row.id} className="engine-series" data-arm={row.arm}>
              <span aria-hidden="true">{row.request?.state === 'warm' ? '○' : '●'}</span> {armLabel(row)} ·{' '}
              {row.request?.state ?? 'State unknown'}
            </li>
          );
        })}
      </ul>
    </>
  );
}

export function DecodeBars({ rows, inspect }: { rows: EngineRow[]; inspect: Inspect }) {
  const points = rows.flatMap((row) => {
    const value = row.metrics?.decode_tps;
    return numeric(value) ? [{ row, value }] : [];
  });
  if (!points.length) return <Empty />;
  const arms = [...groupBy(points, ({ row }) => armKey(row)).values()]
    .map((group) => {
      const accepted = group.filter(({ row }) => !excluded(row));
      const warm = accepted.filter(({ row }) => row.request?.state === 'warm');
      const used = warm.length ? warm : accepted.length ? accepted : group;
      const values = used.map(({ value }) => value);
      const middle = median(values);
      const closest = used.reduce((best, item) =>
        Math.abs(item.value - middle) < Math.abs(best.value - middle) ? item : best,
      );
      return {
        row: closest.row,
        related: used.map(({ row }) => row),
        value: middle,
        low: Math.min(...values),
        high: Math.max(...values),
        n: used.length,
        warm: warm.length > 0,
      };
    })
    .sort((a, b) => armOrder(a.row, b.row));
  const max = Math.max(1, ...arms.map(({ high }) => high));
  return (
    <ul className="engine-bars">
      {arms.map(({ row, related, value, low, high, n, warm }) => (
        <li key={row.id}>
          <span>
            <strong>{armLabel(row)}</strong>
            <small>{`${warm ? 'warm' : 'cold'} request${n === 1 ? '' : 's'} · range ${fmt(low, 2)}–${fmt(high, 2)}`}</small>
          </span>
          <span className="engine-track" aria-hidden="true">
            <i style={{ width: `${(100 * value) / max}%` }} />
          </span>
          <RowValue row={row} related={related} inspect={inspect}>{`${fmt(value, 2)} tok/s`}</RowValue>
        </li>
      ))}
    </ul>
  );
}

export function SpeedBars({ ratios, inspect }: { ratios: Ratio[]; inspect: Inspect }) {
  if (!ratios.length) return <Empty>No matched request evidence.</Empty>;
  const merged = [
    ...groupBy(ratios, ({ candidate }) =>
      JSON.stringify([armKey(candidate), candidate.request?.prompt_tokens]),
    ).values(),
  ]
    .map((group) => {
      const warm = group.filter(({ candidate }) => candidate.request?.state === 'warm');
      const used = warm.length ? warm : group;
      const middle = median(used.map(({ value }) => value));
      const closest = used.reduce((best, item) =>
        Math.abs(item.value - middle) < Math.abs(best.value - middle) ? item : best,
      );
      return {
        ...closest,
        value: middle,
        sources: used.flatMap(({ candidate, baselines }) => [candidate, ...baselines]),
        warm: warm.length > 0,
      };
    })
    .sort(
      (a, b) =>
        armOrder(a.candidate, b.candidate) ||
        (a.candidate.request?.prompt_tokens ?? 0) - (b.candidate.request?.prompt_tokens ?? 0),
    );
  const max = Math.max(1.1, ...merged.map(({ value }) => value));
  return (
    <ul className="engine-bars">
      {merged.map(({ candidate, value, sources, warm }) => (
        <li key={candidate.id}>
          <span>
            <strong>{armLabel(candidate)}</strong>
            <small>{`${fmt(candidate.request?.prompt_tokens ?? 0)} tokens · ${warm ? 'warm' : 'cold'}`}</small>
          </span>
          <span
            className="engine-track"
            aria-hidden="true"
            style={{ '--engine-reference': `${100 / max}%` } as React.CSSProperties}
          >
            <i style={{ width: `${(100 * value) / max}%` }} />
          </span>
          <RowValue row={candidate} related={sources} inspect={inspect}>{`${fmt(value)}x`}</RowValue>
        </li>
      ))}
    </ul>
  );
}

export function MemoryBars({ rows, inspect }: { rows: EngineRow[]; inspect: Inspect }) {
  const observations = [
    ...groupBy(
      rows.filter((row) =>
        Boolean(
          row.memory &&
          (numeric(row.memory.budget) ||
            numeric(row.memory.peak_rss) ||
            devices.some(([key]) => numeric(row.memory?.device?.[key]))),
        ),
      ),
      (row) =>
        JSON.stringify([
          armKey(row),
          row.memory?.device,
          row.memory?.budget,
          row.memory?.peak_rss,
          row.quiet?.eligible,
          row.error,
        ]),
    ).values(),
  ].map(([row]) => row);
  if (!observations.length) return <Empty />;
  const getBuffers = (row: EngineRow) =>
    devices.flatMap(([key, name]) => {
      const value = row.memory?.device?.[key];
      return numeric(value) ? [{ key, name, value }] : [];
    });
  const max = Math.max(
    1,
    ...observations.map((row) =>
      Math.max(
        row.memory?.budget ?? 0,
        row.memory?.peak_rss ?? 0,
        getBuffers(row).reduce((sum, { value }) => sum + value, 0),
      ),
    ),
  );
  const width = (value: number) => `${(100 * value) / max}%`;
  return (
    <ul className="engine-memory">
      {observations.map((row) => {
        const buffers = getBuffers(row);
        const budget = row.memory?.budget;
        const rss = row.memory?.peak_rss;
        return (
          <li key={row.id} className={excluded(row) ? 'engine-excluded' : undefined}>
            <strong>{armLabel(row)}</strong>
            <div
              className="engine-track engine-stack"
              style={numeric(budget) ? ({ '--engine-reference': width(budget) } as React.CSSProperties) : undefined}
              aria-hidden="true"
            >
              {buffers.map(({ key, value }) => (
                <i key={key} data-buffer={key} style={{ width: width(value) }} />
              ))}
            </div>
            <div className="engine-memory-values">
              {buffers.map(({ key, name, value }) => (
                <span key={key} data-buffer={key}>
                  <RowValue row={row} inspect={inspect}>{`${name} ${fmt(value)} MiB`}</RowValue>
                </span>
              ))}
              {numeric(budget) && <RowValue row={row} inspect={inspect}>{`Budget ${fmt(budget)} MiB`}</RowValue>}
            </div>
            {numeric(rss) && (
              <>
                <div className="engine-track engine-rss" aria-hidden="true">
                  <i style={{ width: width(rss) }} />
                </div>
                <RowValue row={row} inspect={inspect}>{`Peak host RSS ${fmt(rss)} MiB`}</RowValue>
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}

const points = (v: number) => `${v > 0 ? '+' : ''}${fmt(v * 100, 2)} pp`;

export function AccuracyPlot({ rows, inspect }: { rows: EngineRow[]; inspect: Inspect }) {
  if (!rows.length) return <Empty>No paired accuracy measurements available.</Empty>;
  const limit = Math.max(
    0.05,
    ...rows.flatMap((row) =>
      [row.delta, row.interval?.lo, row.interval?.hi].flatMap((value) => (numeric(value) ? [Math.abs(value)] : [])),
    ),
  );
  const x = (value: number) => 50 + (value / limit) * 50;
  return (
    <ul className="engine-accuracy">
      {rows.map((row) => {
        const low = row.interval?.lo;
        const high = row.interval?.hi;
        const delta = row.delta;
        return (
          <li key={row.id} className={excluded(row) ? 'engine-excluded' : undefined}>
            <strong>{row.pack?.name ?? row.pack?.format ?? 'Pack unrecorded'}</strong>
            <span>{row.test ?? 'Paired accuracy'}</span>
            <div
              className="engine-track engine-interval"
              style={{ '--engine-reference': '50%' } as React.CSSProperties}
              aria-hidden="true"
            >
              {numeric(low) && numeric(high) && <i style={{ left: `${x(low)}%`, width: `${x(high) - x(low)}%` }} />}
              {numeric(delta) && <b style={{ left: `${x(delta)}%` }} />}
            </div>
            <div className="engine-memory-values">
              {numeric(delta) && <RowValue row={row} inspect={inspect}>{`Δ ${points(delta)}`}</RowValue>}
              {numeric(low) && numeric(high) && (
                <RowValue row={row} inspect={inspect}>{`Interval ${points(low)} to ${points(high)}`}</RowValue>
              )}
              {numeric(row.n) && <RowValue row={row} inspect={inspect}>{`n = ${fmt(row.n)}`}</RowValue>}
              {numeric(row.acc) && (
                <RowValue row={row} inspect={inspect}>{`Accuracy ${fmt(row.acc * 100, 2)}%`}</RowValue>
              )}
              {numeric(row.reference_acc) && (
                <RowValue row={row} inspect={inspect}>{`NVFP4 ${fmt(row.reference_acc * 100, 2)}%`}</RowValue>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
