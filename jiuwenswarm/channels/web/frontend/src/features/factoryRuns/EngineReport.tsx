import { useEffect, useRef, useState } from 'react';
import { getApiBase } from '../../utils/env';
import { request } from './api';
import { AccuracyPlot, DecodeBars, LengthPlot, MemoryBars, Panel, RowValue, SpeedBars } from './EngineReportCharts';
import type { Inspect } from './EngineReportCharts';
import {
  accuracyRun,
  armOrder,
  armLabel,
  deliveryHeadline,
  devices,
  evidenceLabel,
  excluded,
  fmt,
  groupBy,
  isReportArm,
  median,
  numeric,
  quietStatus,
  ratios,
  rerun,
  sourceRef,
} from './engineBenchModel';
import type { Benchmark, EngineRow, Metric, QuietVerdict, Ratio } from './engineBenchModel';
import './story.css';
import './engineReport.css';

const runs: Record<string, string> = {
  'r8-lab': 'Nov 26 · R8 delivery lab',
  'nov25-lab-abcde': 'Nov 25 · E0 NVFP4 baseline',
  'nov25-mmlu-q2': 'Nov 25 · Paired MMLU',
};

const metrics: [Metric, string, string][] = [
  ['ttft_ms', 'TTFT', 'ms'],
  ['prefill_tps', 'Prefill', 'tok/s'],
  ['decode_tps', 'Decode', 'tok/s'],
  ['total_ms', 'Total', 'ms'],
  ['load_s', 'Load time', 's'],
  ['server_prefill_ms', 'Server prefill time', 'ms'],
];

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

function Verdict({ label, verdict }: { label: string; verdict: QuietVerdict }) {
  return (
    <div data-testid="factory-runs-engine-quiet-verdict" data-variant={label}>
      <dt>{label}</dt>
      <dd>
        {verdict.status}
        {verdict.reasons.length ? ` · ${verdict.reasons.join('; ')}` : ''}
      </dd>
    </div>
  );
}

function SourceDialog({ rows, close }: { rows: EngineRow[]; close: () => void }) {
  const [row, setRow] = useState(rows[0]);
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
      {rows.length > 1 && (
        <div className="engine-toggle engine-source-choices" role="group" aria-label="Measurement rows">
          {rows.map((source) => (
            <button
              key={source.id}
              type="button"
              aria-pressed={source.id === row.id}
              data-testid="factory-runs-engine-source-row"
              data-variant={source.id}
              onClick={() => setRow(source)}
            >
              {source.arm} · {source.request?.state} ·{' '}
              {source.request?.repeat == null ? source.id.split('/').at(-1) : `repeat ${source.request.repeat}`}
            </button>
          ))}
        </div>
      )}
      {row.launch_verdict || row.corrected_verdict ? (
        <dl className="engine-facts">
          {row.launch_verdict && <Verdict label="Launch quiet rule" verdict={row.launch_verdict} />}
          {row.corrected_verdict && <Verdict label="Final quiet rule" verdict={row.corrected_verdict} />}
        </dl>
      ) : (
        <p>{row.quiet?.reason ?? quietStatus(row)}</p>
      )}
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
      {row.source_excerpt && (
        <details data-testid="factory-runs-engine-primary-record">
          <summary>Primary record excerpt</summary>
          <pre>{JSON.stringify(row.source_excerpt, null, 2)}</pre>
        </details>
      )}
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

function ReportTable({ rows, speed, inspect }: { rows: EngineRow[]; speed: Ratio[]; inspect: Inspect }) {
  return (
    <Panel id="comparison" title="A / B / P comparison">
      <div className="engine-table-wrap">
        <table data-testid="factory-runs-engine-comparison-table">
          <thead>
            <tr>
              <th scope="col">Arm</th>
              <th scope="col">Rendered tokens</th>
              <th scope="col">Request</th>
              <th scope="col">TTFT (s)</th>
              <th scope="col">Prefill (tok/s)</th>
              <th scope="col">Decode (tok/s)</th>
              <th scope="col">Total (s)</th>
              <th scope="col">TTFT speedup</th>
              <th scope="col">Settings and resources</th>
            </tr>
          </thead>
          {[...groupBy(rows, (row) => row.arm ?? '').values()].map((arm) => {
            const load = arm.find((row) => row.kind === 'load') ?? arm[0];
            const requests = arm.filter((row) => row.kind === 'performance');
            const groups = [
              ...groupBy(requests, (row) =>
                JSON.stringify([row.request?.name, row.request?.prompt_tokens, row.request?.state]),
              ).values(),
            ].sort(
              (a, b) =>
                (a[0].request?.prompt_tokens ?? 0) - (b[0].request?.prompt_tokens ?? 0) ||
                Number(b[0].request?.state === 'warm') - Number(a[0].request?.state === 'warm'),
            );
            const facts: Datum[] = [
              [
                'Batch / microbatch',
                numeric(load.settings?.b) && numeric(load.settings?.ub)
                  ? `${load.settings.b} / ${load.settings.ub}`
                  : null,
              ],
              ['Expert cache', value(load.settings?.moe_cache_mib, 'MiB')],
              ['Peak host RSS', value(load.memory?.peak_rss, 'MiB')],
              ['Available memory floor', value(load.memory?.min_available, 'MiB')],
              ['Fit margin', value(load.memory?.fit_margin, 'MiB')],
              ['Load time', metricValue(load, 'load_s', 's')],
              ...packFacts(load).filter(([name]) => name !== 'Pack'),
            ];
            const rowsToShow = groups.length ? groups : [[]];
            return (
              <tbody key={load.id}>
                {rowsToShow.map((group, index) => {
                  const row = group[0];
                  const accepted = group.filter((source) => !excluded(source));
                  const matched = speed.filter(({ candidate }) => accepted.includes(candidate));
                  const prompt = row?.request?.prompt_tokens;
                  return (
                    <tr
                      key={row?.id ?? load.id}
                      data-testid="factory-runs-engine-measurement-row"
                      data-variant={row?.id ?? load.id}
                    >
                      {index === 0 && (
                        <th scope="rowgroup" rowSpan={rowsToShow.length}>
                          <RowValue row={load} inspect={inspect}>
                            {armLabel(load)}
                          </RowValue>
                        </th>
                      )}
                      <td>
                        {row && numeric(prompt) ? (
                          <RowValue row={row} related={group} inspect={inspect}>
                            {fmt(prompt, 0)}
                          </RowValue>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>{row?.request?.state ?? '—'}</td>
                      {metrics.slice(0, 4).map(([metric]) => {
                        const samples = accepted.flatMap((source) => {
                          const measurement = source.metrics?.[metric];
                          return numeric(measurement) ? [{ source, measurement }] : [];
                        });
                        const middle = median(samples.map(({ measurement }) => measurement));
                        const scale = metric === 'ttft_ms' || metric === 'total_ms' ? 1000 : 1;
                        return (
                          <td key={metric} className={!accepted.length && group.length ? 'engine-excluded' : undefined}>
                            {samples.length ? (
                              <RowValue row={samples[0].source} related={group} inspect={inspect}>
                                {fmt(middle / scale, 2)}
                              </RowValue>
                            ) : row && !accepted.length ? (
                              <RowValue row={row} related={group} inspect={inspect} ariaLabel={`Open ${metric} source`}>
                                —
                              </RowValue>
                            ) : (
                              '—'
                            )}
                          </td>
                        );
                      })}
                      <td>
                        {matched.length ? (
                          <RowValue
                            row={matched[0].candidate}
                            related={matched.flatMap(({ candidate, baselines }) => [candidate, ...baselines])}
                            inspect={inspect}
                          >
                            {`${fmt(median(matched.map(({ value }) => value)))}x`}
                          </RowValue>
                        ) : (
                          '—'
                        )}
                      </td>
                      {index === 0 && (
                        <td rowSpan={rowsToShow.length}>
                          <Facts facts={facts.filter(([, datum]) => datum != null)} row={load} inspect={inspect} />
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            );
          })}
        </table>
      </div>
    </Panel>
  );
}

export function EngineReport() {
  const [dataset, setDataset] = useState<Benchmark>();
  const [error, setError] = useState('');
  const [selection, setSelection] = useState<EngineRow[]>();
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
  const arms = observations.filter(isReportArm).sort(armOrder);
  const starts = arms.filter((row) => row.kind === 'load');
  const requests = arms.filter((row) => row.kind === 'performance');
  const speed = ratios(requests);
  const timed = requests.filter((row) => row.run === rerun && row.corrected_verdict);
  const excludedCount = timed.filter((row) => row.corrected_verdict?.status === 'excluded').length;
  const headline = deliveryHeadline(dataset?.delivery);
  const accuracy = observations
    .filter((row) => row.kind === 'accuracy' && row.run === accuracyRun && row.arm === 'B')
    .sort((a, b) => (b.n ?? 0) - (a.n ?? 0))
    .slice(0, 1);
  const inspect: Inspect = (row, related = []) => {
    setSelection([...new Map([row, ...related].map((source) => [source.id, source])).values()]);
  };
  const api = `${getApiBase()}/api/factory/engine-bench`;
  const status = error
    ? `Unable to load R8 measurements. ${error}`
    : !dataset
      ? 'Loading R8 measurements…'
      : !arms.length
        ? 'R8 measurements are unavailable.'
        : '';

  return (
    <main className="factory-runs-page engine-report" data-testid="factory-runs-engine-report">
      <div className="engine-report-content">
        <header className="engine-report-header">
          <div>
            <h1>R8 Engine Report</h1>
            <p>Muse Spark Open on DGX Spark</p>
          </div>
        </header>
        {headline && (
          <p className="engine-delivery-headline" data-testid="factory-runs-engine-delivery-headline">
            {headline}
          </p>
        )}
        {status && (
          <p role="status" className="engine-status" data-testid="factory-runs-engine-status">
            {status}
          </p>
        )}
        {arms.length > 0 && (
          <>
            <ReportTable rows={arms} speed={speed} inspect={inspect} />
            <div className="engine-report-grid">
              <Panel id="ttft" title="Time to first token">
                <LengthPlot rows={requests} metric="ttft_ms" unit="s" scale={1000} inspect={inspect} />
              </Panel>
              <Panel id="decode" title="Decode and total request time">
                <LengthPlot rows={requests} metric="total_ms" unit="s" scale={1000} inspect={inspect} />
                <h3>Decode · tokens per second</h3>
                <DecodeBars rows={requests} inspect={inspect} />
              </Panel>
              <Panel id="speed" title="TTFT speedup versus A">
                <SpeedBars ratios={speed} inspect={inspect} />
              </Panel>
              <Panel id="memory" title="Device and host memory">
                <MemoryBars rows={starts.length ? starts : arms} inspect={inspect} />
              </Panel>
              {accuracy.length > 0 && (
                <Panel id="accuracy" title="Q2_K paired accuracy versus NVFP4">
                  <AccuracyPlot rows={accuracy} inspect={inspect} />
                </Panel>
              )}
            </div>
            <footer className="engine-method" data-testid="factory-runs-engine-method">
              <h2>How this was measured</h2>
              <p>
                A is the Nov 25 baseline, E0 on NVFP4 from the Q2_K-era lab. B and P use the same R8 image, with one capped load per arm and the same
                prompts and device budget as A. TTFT speedups match prompt and cache state. Total times cover 128
                generated tokens for A and 32 for B and P. The paired MMLU result is for Q2_K. The new pack is the next
                accuracy benchmark.
              </p>
              <p>
                Admission required an idle server, one-minute load below 1 and a clear machine gate. Timing excluded
                builds, tests, helpers and foreign processes above 50% of one core. The launch rule exempted the server
                tree. The final rule also exempts the lab runner tree and ignores CPU windows shorter than 0.5 s.{' '}
                {dataset?.delivery?.decision?.kind === 'report_inconclusive' && (
                  <span data-testid="factory-runs-engine-terminal-decision">
                    The terminal decision was <code>report_inconclusive</code>. The quiet rule excluded {excludedCount}{' '}
                    of {timed.length} timing cells.
                  </span>
                )}{' '}
                <a href={`${api}/readme`} data-testid="factory-runs-engine-readme">
                  Final evidence index
                </a>
                {' · '}
                <a href={`${api}/method-history`} data-testid="factory-runs-engine-method-history">
                  Strict-rule history
                </a>
              </p>
            </footer>
          </>
        )}
      </div>
      {selection && <SourceDialog rows={selection} close={() => setSelection(undefined)} />}
    </main>
  );
}
