import { useState } from 'react';
import type { ReactNode } from 'react';
import {
  armKey, armLabel, armOrder, chartRequestGroups, devices, engineRequestGroup, engineRequestLabel, excluded,
  fmt, groupBy, median, mmluSummary, numeric, requestGroupLabels,
} from './engineBenchModel';
import type { ChartRequestGroup, EngineRow, Metric, Ratio } from './engineBenchModel';

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

export function EngineRequestMethod() {
  return (
    <div data-testid="factory-runs-engine-request-method">
      <p>Warm-server numbers. The first request after a server start is slower (W1: +36 s first token at 512 tokens); dropping file pages adds about 5%.</p>
      <p>{"Run 2's 2048-token warm decode varied between repeats in both arms (AQBC 2.2 and 4.4 tok/s, AQB control 2.1 and 4.3), so the table's 3.28 median isn't quoted as an absolute speed; the same-server comparison holds."}</p>
    </div>
  );
}

function RequestGroupControls({ groups, selected, select, label, testId }: {
  groups: readonly ChartRequestGroup[];
  selected?: ChartRequestGroup;
  select: (group: ChartRequestGroup) => void;
  label: string;
  testId: string;
}) {
  if (groups.length < 2) return null;
  return (
    <div className="engine-toggle" role="group" aria-label={label}>
      {groups.map((group) => (
        <button
          key={group}
          type="button"
          aria-pressed={selected === group}
          onClick={() => select(group)}
          data-testid={testId}
          data-variant={group}
        >
          {requestGroupLabels[group]}
        </button>
      ))}
    </div>
  );
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
  const [shownState, setShownState] = useState<ChartRequestGroup>('warm');
  const all = rows
    .filter((row) => !excluded(row))
    .flatMap((row) => {
      const tokens = row.request?.prompt_tokens;
      const value = row.metrics?.[metric];
      return numeric(tokens) && numeric(value) ? [{ row, tokens, score: value / scale, group: engineRequestGroup(row) }] : [];
    });
  if (!all.length) return <Empty />;
  const choices = chartRequestGroups.filter((group) => all.some((point) => point.group === group));
  const selected = choices.includes(shownState) ? shownState : choices[0];
  const points = selected ? all.filter(({ group }) => group === selected) : all;
  const lengths = [...new Set(points.map((point) => point.tokens))].sort((a, b) => a - b);
  const groups = [...groupBy(points, ({ row, group }) => JSON.stringify([armKey(row), group])).values()].sort(
    (a, b) => armOrder(a[0].row, b[0].row),
  );
  const x = (length: number) => 96 + (lengths.indexOf(length) * 524) / Math.max(1, lengths.length - 1);
  const max = Math.max(1, ...points.map((point) => point.score));
  const y = (value: number) => 195 - (value * 174) / max;
  const digits = max >= 100 ? 0 : 1;
  return (
    <>
      <RequestGroupControls groups={choices} selected={selected} select={setShownState}
        label="Request state" testId="factory-runs-engine-state" />
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
            const byLength = [...groupBy(group, ({ tokens }) => String(tokens)).values()].sort(
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
                  const label = `${armLabel(row)} · ${engineRequestLabel(row) ?? 'State unknown'} · ${fmt(tokens)} tokens · ${fmt(score)} ${unit}`;
                  return (
                    <circle
                      key={row.id}
                      cx={x(tokens)}
                      cy={y(score)}
                      r="5"
                      stroke="currentColor"
                      fill={state === 'warm' ? 'var(--color-surface-card)' : 'currentColor'}
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
              {engineRequestLabel(row) ?? 'State unknown'}
            </li>
          );
        })}
      </ul>
    </>
  );
}

export function DecodeBars({ rows, inspect }: { rows: EngineRow[]; inspect: Inspect }) {
  const [shownState, setShownState] = useState<ChartRequestGroup>('warm');
  const points = rows.flatMap((row) => {
    const length = row.request?.prompt_tokens;
    const speed = row.metrics?.decode_tps;
    return numeric(length) && numeric(speed) ? [{ row, length, speed, group: engineRequestGroup(row) }] : [];
  });
  const eligible = points.filter(({ row }) => !excluded(row));
  if (!eligible.length) return <Empty />;

  const choices = chartRequestGroups.filter((group) => eligible.some((point) => point.group === group));
  const selected = choices.includes(shownState) ? shownState : choices[0];
  const shown = selected ? eligible.filter(({ group }) => group === selected) : eligible;
  const lengths = [...new Set(shown.map(({ length }) => length))].sort((a, b) => b - a);
  const arms = [...groupBy(shown, ({ row }) => armKey(row)).entries()].sort((a, b) =>
    armOrder(a[1][0].row, b[1][0].row),
  );
  const max = Math.max(1, ...eligible.map(({ speed }) => speed));

  return (
    <>
      <RequestGroupControls groups={choices} selected={selected} select={setShownState}
        label="Decode request state" testId="factory-runs-engine-decode-state" />
      {lengths.map((length) => (
        <section
          key={length}
          className="engine-decode-length"
          data-testid="factory-runs-engine-decode-length"
          data-variant={length}
        >
          <h3>{fmt(length, 0)} rendered prompt tokens</h3>
          <ul className="engine-bars">
            {arms.map(([key, [arm]]) => {
              const samples = shown.filter((point) => point.length === length && armKey(point.row) === key);
              const values = samples.map(({ speed }) => speed);
              const value = samples.length ? median(values) : undefined;
              const sources = samples.map(({ row }) => row);
              return (
                <li key={key} data-testid="factory-runs-engine-decode-arm" data-variant={arm.row.arm}>
                  <span>
                    <strong>{armLabel(arm.row)}</strong>
                    {values.length > 1 && <small>Median of {values.length} requests</small>}
                  </span>
                  <span className="engine-track" aria-hidden="true">
                    {value !== undefined && <i style={{ width: `${(100 * value) / max}%` }} />}
                  </span>
                  {value !== undefined ? (
                    <RowValue row={sources[0]} related={sources} inspect={inspect}>{`${fmt(value, 2)} tok/s`}</RowValue>
                  ) : (
                    '—'
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </>
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
      {merged.map(({ candidate, value, sources }) => (
        <li key={candidate.id}>
          <span>
            <strong>{armLabel(candidate)}</strong>
            <small>{`${fmt(candidate.request?.prompt_tokens ?? 0)} tokens · ${engineRequestLabel(candidate) ?? 'State unknown'}`}</small>
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

export function AccuracyPlot({ rows, inspect }: { rows: EngineRow[]; inspect: Inspect }) {
  if (!rows.length) return <Empty>No paired accuracy measurements available.</Empty>;
  return (
    <ul className="engine-accuracy">
      {rows.map((row) => (
        <li key={row.id}>
          {row.arm === 'AQBC' && row.verdict && <RowValue row={row} inspect={inspect}>{row.verdict}</RowValue>}
          {row.arm !== 'AQBC' && numeric(row.n) && numeric(row.reference_acc) && numeric(row.acc) && (
            <RowValue row={row} inspect={inspect}>
              {mmluSummary(row.n, row.reference_acc * 100, row.acc * 100)}
            </RowValue>
          )}
          <span>{row.arm === 'AQBC' ? 'First 25 AQB load 8 questions, in the original order' : 'A · NVFP4 vs AQB · mixed 2-bit'}</span>
        </li>
      ))}
    </ul>
  );
}
