import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { request } from './api';
import {
  AccuracyPlot,
  DecodeBars,
  Empty,
  LengthPlot,
  MemoryBars,
  Panel,
  RowValue,
  SpeedBars,
} from './EngineReportCharts';
import type { Inspect } from './EngineReportCharts';
import {
  armKey,
  armLabel,
  devices,
  evidenceLabel,
  fmt,
  groupBy,
  numeric,
  quietStatus,
  ratios,
  sourceRef,
} from './engineBenchModel';
import type { Benchmark, EngineRow, Metric } from './engineBenchModel';
import './story.css';
import './engineReport.css';

const runs: Record<string, string> = {
  'r8-lab': 'Nov 26 · R8 delivery lab',
  'nov25-lab-abcde': 'Nov 25 · A–E lab',
  'r8-prefill-calibration': 'Nov 26 · R8 prefill calibration',
  'r8-smoke': 'Nov 26 · R8 smoke',
  'nov25-mmlu-q2': 'Nov 25 · Paired MMLU',
  'nov25-agent-sweep': 'Nov 25 · Agent-length sweep',
  'nov25-size-probe': 'Nov 25 · Context-size probe',
  'nov25-probe-d': 'Nov 25 · D probe',
  'nov25-probe-ub2048': 'Nov 25 · Microbatch probe',
  'nov24-lab-abc': 'Nov 24 · A–C lab',
  'nov24-smoke': 'Nov 24 · Smoke',
};

const metrics: [Metric, string, string][] = [
  ['ttft_ms', 'TTFT', 'ms'],
  ['decode_tps', 'Decode', 'tok/s'],
  ['prefill_tps', 'Prefill', 'tok/s'],
  ['total_ms', 'Total', 'ms'],
  ['load_s', 'Load time', 's'],
  ['server_prefill_ms', 'Server prefill time', 'ms'],
];

const ablations = [
  ['A', 'B', 'Quantization on default settings'],
  ['A', 'A+P', 'Prefill plan on NVFP4'],
  ['B', 'P', 'Prefill plan on mixed 2-bit'],
  ['A', 'P', 'Quantization and prefill plan'],
] as const;

function value(value: unknown, unit = '', digits = 2) {
  if (numeric(value)) return `${fmt(value, digits)}${unit ? ` ${unit}` : ''}`;
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'string' && value.trim()) return value;
  return null;
}

type Datum = [string, string | null];
const settingFacts = (row: EngineRow): Datum[] => [
  ['Batch', value(row.settings?.b)],
  ['Microbatch', value(row.settings?.ub)],
  ['MoE cache setting', value(row.settings?.moe_cache_mib, 'MiB')],
  ['Context', value(row.settings?.ctx, 'tokens')],
  ['Parallel slots', value(row.settings?.np)],
  ['CPU MoE', value(row.settings?.cpu_moe)],
  ['Placement setting', value(row.settings?.fitt, 'MiB')],
];
const memoryFacts = (row: EngineRow): Datum[] => [
  ['Peak host RSS', value(row.memory?.peak_rss, 'MiB')],
  ['Peak cgroup memory', value(row.memory?.peak_cgroup_mib, 'MiB')],
  ['Available memory floor', value(row.memory?.min_available, 'MiB')],
  ['Device budget', value(row.memory?.budget, 'MiB')],
  ['Device fit margin', value(row.memory?.fit_margin, 'MiB')],
  ...devices.map(([key, label]): Datum => [`Device ${label.toLowerCase()}`, value(row.memory?.device?.[key], 'MiB')]),
];
const packFacts = (row: EngineRow): Datum[] => [
  ['Pack', value(row.pack?.name)],
  ['Format', value(row.pack?.format)],
  ['Bits per weight', value(row.pack?.bits_per_weight)],
  ['Disk size', numeric(row.pack?.bytes) ? value(row.pack.bytes / 1024 ** 3, 'GiB') : null],
  [
    'Census',
    row.pack?.census && typeof row.pack.census === 'object'
      ? Object.entries(row.pack.census)
          .map(([type, count]) => `${type} ${count}`)
          .join(' · ')
      : row.pack?.census_digest
        ? 'Digest recorded'
        : null,
  ],
];
const metricValue = (row: EngineRow, metric: Metric, unit: string) => value(row.metrics?.[metric], unit);
const unavailable = <span className="engine-unmeasured">Unmeasured</span>;

function Facts({ facts, row, inspect }: { facts: Datum[]; row?: EngineRow; inspect?: Inspect }) {
  return (
    <dl className="engine-facts">
      {facts.map(([label, datum]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>
            {datum == null ? (
              unavailable
            ) : row && inspect ? (
              <RowValue row={row} inspect={inspect}>
                {datum}
              </RowValue>
            ) : (
              datum
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function SourceDialog({ row, close }: { row: EngineRow; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  const sources = new Map([row.source, ...(row.sources ?? [])].map((source) => [sourceRef(source), source]));
  return (
    <dialog
      ref={dialog}
      className="engine-dialog"
      onClose={close}
      aria-labelledby="engine-source-title"
      data-testid="factory-runs-engine-source-dialog"
    >
      <header>
        <div>
          <h2 id="engine-source-title">Measurement source</h2>
          <p>
            {armLabel(row)} · {runs[row.run ?? ''] ?? row.run} · {evidenceLabel(row)}
          </p>
        </div>
        <button type="button" data-testid="factory-runs-engine-close-source" onClick={() => dialog.current?.close()}>
          Close
        </button>
      </header>
      <p className={row.quiet?.eligible === false ? 'engine-excluded' : undefined}>{quietStatus(row)}</p>
      {row.quiet?.eligible !== false && row.quiet?.reason && <p>{row.quiet.reason}</p>}
      {row.error && <p>{row.error}</p>}
      <ul className="engine-sources" data-testid="factory-runs-engine-source-references">
        {[...sources].map(([location, source]) => (
          <li key={location}>
            <code>{location}</code>
            {source.sha256 && (
              <small>
                SHA-256 <code>{source.sha256}</code>
              </small>
            )}
          </li>
        ))}
      </ul>
      <h3>Request and measurement</h3>
      <Facts
        facts={[
          ['Rendered prompt length', value(row.request?.prompt_tokens, 'tokens')],
          ['Request label', value(row.request?.name)],
          ['Request state', value(row.request?.state)],
          ['Repeat', value(row.request?.repeat)],
          ['Requested generation', value(row.request?.n_predict, 'tokens')],
          ['Generated', value(row.request?.generated_tokens, 'tokens')],
          ['Cached', value(row.request?.cached_tokens, 'tokens')],
          ['Prefill chunk sizes', row.request?.prefill_chunks?.join(' + ') ?? null],
          ['Host load (1 min)', value(row.quiet?.load1)],
          ...metrics.map(([metric, label, unit]): Datum => [label, metricValue(row, metric, unit)]),
        ]}
      />
      {row.quiet?.processes != null && (
        <details>
          <summary>Quiet-gate processes</summary>
          <pre>{JSON.stringify(row.quiet.processes, null, 2)}</pre>
        </details>
      )}
      <h3>Engine and resources</h3>
      <Facts
        facts={[
          ['Engine', value(row.engine?.name)],
          ['Engine commit', value(row.engine?.commit)],
          ['Engine binary', value(row.engine?.binary)],
          ['Binary SHA-256', value(row.engine?.sha256)],
          ['Engine image', value(row.engine?.image)],
          ['Attempt ID', value(row.attempt_id)],
          ...settingFacts(row),
          ...memoryFacts(row),
          ...packFacts(row),
          ['Census SHA-256', value(row.pack?.census_digest)],
          ['Exact disk size', value(row.pack?.bytes, 'bytes')],
        ]}
      />
      {row.kind === 'accuracy' && (
        <>
          <h3>Paired accuracy</h3>
          <Facts
            facts={[
              ['Test', value(row.test)],
              ['Sample size', value(row.n)],
              ['Candidate accuracy', numeric(row.acc) ? `${fmt(row.acc * 100, 2)}%` : null],
              ['NVFP4 accuracy', numeric(row.reference_acc) ? `${fmt(row.reference_acc * 100, 2)}%` : null],
              ['Accuracy delta', numeric(row.delta) ? value(row.delta * 100, 'pp') : null],
              [
                'Interval',
                numeric(row.interval?.lo) && numeric(row.interval?.hi)
                  ? `${fmt(row.interval.lo * 100, 2)} to ${fmt(row.interval.hi * 100, 2)} pp`
                  : null,
              ],
              ['Margin', numeric(row.margin) ? value(row.margin * 100, 'pp') : null],
              ['Verdict', value(row.verdict)],
            ]}
          />
        </>
      )}
    </dialog>
  );
}

function RequestRows({ rows, inspect }: { rows: EngineRow[]; inspect: Inspect }) {
  if (!rows.length) return <Empty />;
  return (
    <div className="engine-table-wrap">
      <table>
        <thead>
          <tr>
            <th>Rendered prompt</th>
            <th>Request</th>
            {metrics.slice(0, 4).map(([metric, label, unit]) => (
              <th key={metric}>
                {label} ({unit})
              </th>
            ))}
            <th>Evidence and quiet gate</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              className={row.quiet?.eligible === false || row.error ? 'engine-excluded' : undefined}
              data-testid="factory-runs-engine-measurement-row"
              data-variant={row.id}
            >
              <td>
                {numeric(row.request?.prompt_tokens) ? (
                  <RowValue row={row} inspect={inspect}>
                    {fmt(row.request.prompt_tokens)}
                  </RowValue>
                ) : (
                  unavailable
                )}
              </td>
              <td>
                {[
                  row.request?.name,
                  row.request?.state,
                  row.request?.repeat == null ? undefined : `repeat ${row.request.repeat}`,
                ]
                  .filter(Boolean)
                  .join(' · ') || 'Unrecorded'}
              </td>
              {metrics.slice(0, 4).map(([metric]) => (
                <td key={metric}>
                  {numeric(row.metrics?.[metric]) ? (
                    <RowValue row={row} inspect={inspect}>
                      {fmt(row.metrics[metric], 2)}
                    </RowValue>
                  ) : (
                    unavailable
                  )}
                </td>
              ))}
              <td>
                <RowValue row={row} inspect={inspect}>{`${evidenceLabel(row)} · ${quietStatus(row)}`}</RowValue>
                {row.error && <small>{row.error}</small>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ArmDetails({ rows, accuracy, inspect }: { rows: EngineRow[]; accuracy: EngineRow[]; inspect: Inspect }) {
  return (
    <Panel id="arms" title="Arm details">
      {!rows.length && <Empty />}
      {[...groupBy(rows, armKey).values()].map((group) => {
        const arm =
          group.find((row) => row.kind === 'load' && row.quiet?.eligible !== false && !row.error) ??
          group.find((row) => row.quiet?.eligible !== false && !row.error) ??
          group[0];
        const packAccuracy = accuracy.find((row) => row.pack?.name && row.pack.name === arm.pack?.name);
        return (
          <article key={arm.id} className="engine-arm" data-testid="factory-runs-engine-arm" data-variant={arm.id}>
            <h3>{armLabel(arm)}</h3>
            <p>
              {runs[arm.run ?? ''] ?? arm.run} · {arm.engine?.commit ?? 'Engine revision unrecorded'}
            </p>
            <Facts
              row={arm}
              inspect={inspect}
              facts={[
                ...packFacts(arm),
                ...settingFacts(arm),
                ['Load time', metricValue(arm, 'load_s', 's')],
                ...memoryFacts(arm).slice(0, 5),
              ]}
            />
            <div className="engine-arm-accuracy">
              Paired accuracy{' '}
              {packAccuracy && numeric(packAccuracy.acc) ? (
                <RowValue
                  row={packAccuracy}
                  inspect={inspect}
                >{`${evidenceLabel(packAccuracy)} · ${fmt(packAccuracy.acc * 100, 2)}%`}</RowValue>
              ) : (
                unavailable
              )}
            </div>
            <RequestRows rows={group.filter((row) => row.kind === 'performance')} inspect={inspect} />
            {group
              .filter((row) => row.kind === 'load')
              .map((row) => (
                <p key={row.id} className={row.quiet?.eligible === false || row.error ? 'engine-excluded' : undefined}>
                  <RowValue
                    row={row}
                    inspect={inspect}
                  >{`Startup · ${evidenceLabel(row)} · ${quietStatus(row)}`}</RowValue>
                  {row.error && ` · ${row.error}`}
                </p>
              ))}
          </article>
        );
      })}
    </Panel>
  );
}

function Ablation({
  campaign,
  scope,
  baselineRows,
  inspect,
}: {
  campaign: EngineRow[];
  scope: string;
  baselineRows: EngineRow[];
  inspect: Inspect;
}) {
  return (
    <div className="engine-table-wrap">
      <table>
        <caption>R8 ablation by total request time</caption>
        <thead>
          <tr>
            <th>Arms</th>
            <th>Capsule contribution</th>
            <th>Matched evidence</th>
          </tr>
        </thead>
        <tbody>
          {ablations.map(([from, to, title]) => {
            const comparisons =
              scope === 'r8-lab' || scope === 'all'
                ? ratios([...campaign.filter((row) => row.run === 'r8-lab'), ...baselineRows], from, to).filter(
                    ({ candidate }) => candidate.run === 'r8-lab',
                  )
                : [];
            return (
              <tr key={`${from}-${to}`}>
                <td>
                  {from} → {to}
                </td>
                <td>{title}</td>
                <td>
                  {comparisons.length
                    ? comparisons.map(({ candidate, base, value, label }) => (
                        <div key={candidate.id} className="engine-comparison">
                          {candidate.request?.prompt_tokens} tokens · {candidate.request?.state}{' '}
                          <RowValue
                            row={candidate}
                            inspect={inspect}
                          >{`${fmt(value, 2)}× ${label.toLowerCase()}`}</RowValue>{' '}
                          <RowValue row={base} inspect={inspect}>{`Arm ${base.arm} source`}</RowValue>
                        </div>
                      ))
                    : unavailable}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function EngineReport() {
  const [dataset, setDataset] = useState<Benchmark>();
  const [error, setError] = useState('');
  const [scope, setScope] = useState('');
  const [selected, setSelected] = useState<EngineRow>();
  useEffect(() => {
    const controller = new AbortController();
    request<Benchmark>('/engine-bench', { signal: controller.signal })
      .then(setDataset)
      .catch((failure: unknown) => {
        if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : 'Benchmark unavailable');
      });
    return () => controller.abort();
  }, []);
  const observations = dataset?.rows ?? [];
  const campaign = observations.filter((row) => row.kind !== 'accuracy');
  const collections = new Set(campaign.map((row) => row.run ?? 'Unknown run'));
  const visibleScope =
    scope || ['r8-lab', 'nov25-lab-abcde', ...collections].find((key) => collections.has(key)) || 'all';
  const visible = campaign.filter((row) => visibleScope === 'all' || row.run === visibleScope);
  const requests = visible.filter((row) => row.kind === 'performance');
  const baselineRows = campaign.filter(
    (row) => row.kind === 'performance' && row.run === 'nov25-lab-abcde' && row.arm === 'A',
  );
  const speed = ratios([...new Map([...requests, ...baselineRows].map((row) => [row.id, row])).values()]).filter(
    ({ candidate }) => requests.includes(candidate),
  );
  const accuracy = [
    ...groupBy(
      observations.filter((row) => row.kind === 'accuracy'),
      (row) => JSON.stringify([row.run, row.pack?.name, row.test, row.quiet?.eligible]),
    ).values(),
  ].map((rows) => rows.reduce((latest, row) => ((row.n ?? 0) > (latest.n ?? 0) ? row : latest)));
  const accuracyPacks = new Set(accuracy.map((row) => row.pack?.name));
  const unmeasuredPacks = [...new Set(campaign.map((row) => row.pack?.name))].filter(
    (pack) => pack && !accuracyPacks.has(pack),
  );
  const excluded = observations.filter((row) => row.quiet?.eligible === false);
  const inspect: Inspect = setSelected;
  let status: ReactNode;
  if (error) status = `Unable to load benchmark evidence. ${error}`;
  else if (!dataset) status = 'Loading benchmark evidence…';
  else if (!observations.length) status = 'No benchmark evidence is available.';
  else
    status = (
      <>
        <strong>{fmt(observations.length)}</strong> source rows · <strong>{fmt(excluded.length)}</strong> excluded by
        the quiet gate
      </>
    );

  return (
    <main className="factory-runs-page engine-report" data-testid="factory-runs-engine-report">
      <div className="engine-report-content">
        <header className="engine-report-header">
          <div>
            <h1>Engine Report</h1>
            <p>Muse Spark Open on DGX Spark</p>
          </div>
          {collections.size > 0 && (
            <label>
              Run
              <select
                value={visibleScope}
                onChange={(event) => setScope(event.target.value)}
                data-testid="factory-runs-engine-run"
              >
                {[...collections].map((run) => (
                  <option value={run} key={run}>
                    {runs[run] ?? run}
                  </option>
                ))}
                <option value="all">All evidence</option>
              </select>
            </label>
          )}
        </header>
        <p role="status" className="engine-status" data-testid="factory-runs-engine-status">
          {status}
        </p>
        {dataset && (<>
        <div className="engine-report-grid">
          <Panel id="ttft" title="Time to first token">
            <p>Seconds from sending the request to the first streamed token, by rendered prompt length</p>
            <LengthPlot rows={requests} metric="ttft_ms" unit="s" scale={1000} inspect={inspect} />
          </Panel>
          <Panel id="decode" title="Decode and total request time">
            <p>Total request time in seconds (prompt plus 32 generated tokens)</p>
            <LengthPlot rows={requests} metric="total_ms" unit="s" scale={1000} inspect={inspect} />
            <h3>Decode · tokens per second</h3>
            <DecodeBars rows={requests} inspect={inspect} />
          </Panel>
          <Panel id="speed" title="Speed-up versus arm A">
            <p>
              Total-time ratios use matching rendered lengths, generation limits and request states. Historical or
              incompletely matched environments are indicative.
            </p>
            <SpeedBars ratios={speed} inspect={inspect} />
            <Ablation campaign={requests} baselineRows={baselineRows} scope={visibleScope} inspect={inspect} />
          </Panel>
          <Panel id="memory" title="Device and host memory">
            <p>
              The stacked bars show reported device buffers. The vertical marker shows the device budget. Host RSS has
              its own bar.
            </p>
            <MemoryBars rows={visible} inspect={inspect} />
          </Panel>
          <Panel id="accuracy" title="Paired accuracy versus NVFP4">
            <p>
              Difference in percentage points at the latest reported sample size. The center line marks zero difference.
            </p>
            <AccuracyPlot rows={accuracy} inspect={inspect} />
            {unmeasuredPacks.length > 0 && (
              <p className="engine-unmeasured">{unmeasuredPacks.join(', ')} · Paired accuracy unmeasured</p>
            )}
          </Panel>
          <Panel id="excluded" title="Quiet-gate exclusions">
            {excluded.length ? (
              <ul className="engine-exclusions">
                {excluded.map((row) => (
                  <li key={row.id} className="engine-excluded">
                    <RowValue
                      row={row}
                      inspect={inspect}
                    >{`${armLabel(row)} · ${row.id} · ${quietStatus(row)}`}</RowValue>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>{observations.length ? 'No rows are marked excluded.' : 'No quiet-gate records available.'}</Empty>
            )}
          </Panel>
        </div>
        <ArmDetails rows={visible} accuracy={accuracy} inspect={inspect} />
        </>)}
      </div>
      {selected && <SourceDialog row={selected} close={() => setSelected(undefined)} />}
    </main>
  );
}
