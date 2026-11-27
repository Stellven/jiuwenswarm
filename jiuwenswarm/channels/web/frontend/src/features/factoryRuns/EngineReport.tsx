import { useEffect, useRef, useState } from 'react';
import { getApiBase } from '../../utils/env';
import { request } from './api';
import { AccuracyPlot, DecodeBars, EngineRequestMethod, LengthPlot, MemoryBars, Panel, RowValue, SpeedBars } from './EngineReportCharts';
import type { Inspect } from './EngineReportCharts';
import {
  finalRun,
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
  requestStateLabel,
  sourceRef,
} from './engineBenchModel';
import type { Benchmark, EngineRow, Metric, QuietVerdict, Ratio } from './engineBenchModel';
import './story.css';
import './engineReport.css';

const runs: Record<string, string> = {
  'r9-aqbc': 'Run 2 same-server benchmark',
  'r8-final-bench': 'R8 engine benchmark',
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
  ['Disk size', numeric(row.pack?.bytes) ? value(row.pack.bytes / 1e9, 'GB', 1) : null],
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
              {source.arm} · {requestStateLabel(source.request?.state) ?? 'State unknown'} ·{' '}
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
          ['Request state', value(requestStateLabel(row.request?.state))],
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
              [row.arm === 'AQBC' ? 'AQBC · inherited from AQB' : 'AQB · Mixed 2-bit', numeric(row.acc) ? `${(row.acc * 100).toFixed(1)}%` : null],
              ['A · NVFP4', numeric(row.reference_acc) ? `${(row.reference_acc * 100).toFixed(1)}%` : null],
            ]}
          />
        </>
      )}
    </dialog>
  );
}

function ReportTable({ rows, speed, inspect }: { rows: EngineRow[]; speed: Ratio[]; inspect: Inspect }) {
  return (
    <Panel id="comparison" title="First-request comparison">
      <div className="engine-table-wrap">
        <table data-testid="factory-runs-engine-comparison-table">
          <thead>
            <tr>
              <th scope="col">Arm</th>
              <th scope="col">Rendered tokens</th>
              <th scope="col">Request</th>
              <th scope="col">TTFT (s)</th>
              <th scope="col">Decode (tok/s)</th>
              <th scope="col">Total (s)</th>
              <th scope="col">TTFT speedup</th>
              <th scope="col">Total speedup</th>
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
            ].filter((group) => group.some((row) => !excluded(row))).sort(
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
                      <td>{requestStateLabel(row?.request?.state) ?? '—'}</td>
                      {metrics.slice(0, 4).filter(([metric]) => metric !== 'prefill_tps').map(([metric]) => {
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
                      <td>
                        {numeric(matched[0]?.totalSpeedup) ? (
                          <RowValue
                            row={matched[0].candidate}
                            related={matched.flatMap(({ candidate, baselines }) => [candidate, ...baselines])}
                            inspect={inspect}
                          >
                            {`${fmt(matched[0].totalSpeedup)}x`}
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

function ControlTable({ rows, inspect }: { rows: EngineRow[]; inspect: Inspect }) {
  const standard = rows.filter((row) => row.run === 'r9-aqbc' &&
    (row.request?.state === 'warm' || row.request?.state === 'cold'));
  if (!standard.length) return null;
  return (
    <details className="engine-method">
      <summary>Run 2 first requests on the same server</summary>
      <table>
        <thead><tr><th>Document</th><th>Request</th><th>Arm</th><th>First token (s)</th><th>Decode (tok/s)</th><th>Total (s)</th></tr></thead>
        <tbody>{[...groupBy(standard, (row) => [row.request?.name, row.request?.state, row.arm].join('/'))]
          .sort(([left], [right]) => left.localeCompare(right, undefined, { numeric: true }))
          .map(([key, samples]) => {
            const first = samples[0];
            return <tr key={key}><th>{first.request?.name?.slice(1)}</th><td>{requestStateLabel(first.request?.state)}</td>
              <td>{first.arm === 'AQB' ? 'AQB control' : first.arm}</td>
              {(['ttft_ms', 'decode_tps', 'total_ms'] as const).map((metric) => {
                const values = samples.map((row) => row.metrics?.[metric]).filter(numeric);
                return <td key={metric}><RowValue row={first} related={samples} inspect={inspect}>
                  {fmt(median(values) / (metric === 'decode_tps' ? 1 : 1000), 2)}
                </RowValue></td>;
              })}</tr>;
          })}</tbody>
      </table>
    </details>
  );
}

function FollowupTable({ rows, inspect }: { rows: EngineRow[]; inspect: Inspect }) {
  const followups = rows.filter((row) => row.run === 'r9-aqbc' && row.request?.state === 'follow-up');
  if (!followups.length) return null;
  return (
    <Panel id="followup" title="Follow-up question">
      <p>Two questions share one document. AQBC reuses its processed prefix. The AQB control runs on the same server with prompt reuse off. A is the published Warm server reference.</p>
      <table>
        <thead><tr><th>Document</th><th>Arm</th><th>First token (s)</th><th>Decode (tok/s)</th><th>Total (s)</th></tr></thead>
        <tbody>
          {['p512', 'p2048'].flatMap((name) => ['A', 'AQB', 'AQBC'].map((arm) => {
            const recorded = (arm === 'A' ? rows : followups).filter((row) => row.arm === arm &&
              row.request?.name === name && (arm !== 'A' || (row.run === finalRun && row.request?.state === 'warm')));
            const samples = recorded.filter((row) => !excluded(row));
            if (!samples.length) return <tr key={name + arm}><th>{name.slice(1)}</th><td>{arm}</td>
              <td colSpan={3}>{recorded.length
                ? <RowValue row={recorded[0]} related={recorded} inspect={inspect}>Excluded by the quiet rule</RowValue>
                : 'No measurement recorded'}</td></tr>;
            return <tr key={name + arm}><th>{name.slice(1)}</th><td>{arm}</td>
              {(['ttft_ms', 'decode_tps', 'total_ms'] as const).map((key) => {
                const values = samples.map((row) => row.metrics?.[key]).filter(numeric);
                return <td key={key}>{values.length > 0 && <RowValue row={samples[0]} related={samples} inspect={inspect}>
                  {fmt(median(values) / (key === 'decode_tps' ? 1 : 1000), 2)}
                </RowValue>}</td>;
              })}
            </tr>;
          }))}
        </tbody>
      </table>
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
  const clockDifferences = requests.flatMap((row) => {
    const direct = row.source_excerpt?.client_ttft_ms;
    const derived = row.metrics?.ttft_ms;
    return row.arm === 'A' && !excluded(row) && numeric(direct) && numeric(derived) ? [Math.abs(direct - derived)] : [];
  });
  const headline = deliveryHeadline(dataset?.delivery);
  const accuracy = observations
    .filter((row) => row.kind === 'accuracy' && ((row.run === finalRun && row.arm === 'AQB') || (row.run === 'r9-aqbc' && row.arm === 'AQBC')))
    .sort((a, b) => (b.n ?? 0) - (a.n ?? 0));
  const inspect: Inspect = (row, related = []) => {
    setSelection([...new Map([row, ...related].map((source) => [source.id, source])).values()]);
  };
  const api = `${getApiBase()}/api/factory/engine-bench`;
  const status = error
    ? `Unable to load engine measurements. ${error}`
    : !dataset
      ? 'Loading engine measurements…'
      : !arms.length
        ? 'Engine measurements are unavailable.'
        : '';

  return (
    <main className="factory-runs-page engine-report" data-testid="factory-runs-engine-report">
      <div className="engine-report-content">
        <header className="engine-report-header">
          <div>
            <h1>{arms.some((row) => row.arm === 'AQBC') ? 'Engine Report' : 'R8 Engine Report'}</h1>
            <p>Muse Spark Open on DGX Spark</p>
          </div>
        </header>
        {headline && (
          <p className="engine-delivery-headline" data-testid="factory-runs-engine-delivery-headline">
            {arms.some((row) => row.arm === 'AQBC') && 'Run 1 · '}{headline}
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
            <FollowupTable rows={observations} inspect={inspect} />
            <ControlTable rows={observations} inspect={inspect} />
            <div className="engine-report-grid">
              <Panel id="ttft" title="Time to first token">
                <LengthPlot rows={requests} metric="ttft_ms" unit="s" scale={1000} inspect={inspect} />
              </Panel>
              <Panel id="decode" title="Decode by rendered prompt length">
                <DecodeBars rows={requests} inspect={inspect} />
                <h3>Total request time</h3>
                <LengthPlot rows={requests} metric="total_ms" unit="s" scale={1000} inspect={inspect} />
              </Panel>
              <Panel id="speed" title="TTFT speedup versus A">
                <SpeedBars ratios={speed} inspect={inspect} />
              </Panel>
              <Panel id="memory" title="Device and host memory">
                <MemoryBars rows={starts.length ? starts : arms} inspect={inspect} />
              </Panel>
              {accuracy.length > 0 && (
                <Panel id="accuracy" title="Accuracy">
                  <AccuracyPlot rows={accuracy} inspect={inspect} />
                </Panel>
              )}
            </div>
            <footer className="engine-method" data-testid="factory-runs-engine-method">
              <h2>How this was measured</h2>
              <p>
                A and AQB used the R8 image. {arms.some((row) => row.arm === 'AQBC') && 'AQBC used the Run 2 image with the same server binary and a prefix-store configuration. '}Each speed request generated 32 tokens. We estimated time to first token
                from the server’s first sampled token, aligned to the client clock
                {clockDifferences.length > 0 && ` (median difference from direct NVFP4 timing: ${fmt(median(clockDifferences))} ms)`}. Warm server results are medians. {arms.some((row) => row.arm === 'AQBC') && 'Run 2 was measured on a shared machine; background activity recorded, not filtered. Its first-request check uses Warm server pairs because the first AQBC request at 512 tokens also read the pack into memory.'} The NVFP4 accuracy reference used the same 250 questions on Nov 25 with engine build 9048bad8d.
              </p>
              <EngineRequestMethod />
              <p>
                <a href={`${api}/readme`} data-testid="factory-runs-engine-readme">
                  Final evidence index
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
