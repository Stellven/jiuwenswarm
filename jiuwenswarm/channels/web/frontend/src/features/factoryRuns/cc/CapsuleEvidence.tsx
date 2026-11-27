import { useMemo, useState } from 'react';
import type { CapsuleAnalysis, CapsuleDetail, CapsuleMeasurement } from './capsuleApi';
import { AnalysisData } from './AnalysisData';
import { Integrity, StructuredData } from './CapsuleMaterial';
import { isRecord, numericColumns, readableName, tableData } from './capsuleModel';
import { type CopyKey, useCapsuleCopy } from './copy';
import { runHref } from './navigation';

function number(value: number | null | undefined, unit = '', digits = 2): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${value.toFixed(digits)}${unit}`;
}

function MeasurementRows({ rows }: { rows: CapsuleMeasurement[] }) {
  const copy = useCapsuleCopy();
  return (
    <div className="cc-table-wrap" data-testid="factory-runs-capsule-results">
      <table className="cc-table cc-measurements">
        <thead>
          <tr>
            {(
              [
                'arm',
                'tokens',
                'count',
                'ttft',
                'stock',
                'speedup',
                'cache',
                'gap',
                'decode',
                'memory',
                'load',
                'run',
              ] as const
            ).map((key) => (
              <th key={key} scope="col">
                {copy(key)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={`${row.run_id}:${row.arm}:${row.observation_ids.join(',')}`}
              data-testid="factory-runs-capsule-result"
              data-variant={`${row.run_id}:${row.arm}:${row.prompt_tokens}:${row.observation_ids[0] || ''}`}
            >
              <th scope="row">
                {row.arm}
                {row.scope === 'combined' && <small>{copy('combined')}</small>}
              </th>
              <td>{row.prompt_tokens}</td>
              <td>{row.samples}</td>
              <td>{number(row.ttft_s, ' s')}</td>
              <td>
                {row.delta_vs_stock_s != null && row.delta_vs_stock_s > 0 ? '+' : ''}
                {number(row.delta_vs_stock_s, ' s')}
              </td>
              <td>{number(row.inverse_vs_stock, '×')}</td>
              <td>{number(row.inverse_vs_cache, '×')}</td>
              <td>{row.gap_closed == null ? '—' : number(row.gap_closed * 100, '%', 1)}</td>
              <td>{number(row.decode_tps)}</td>
              <td>{number(row.peak_memory_bytes == null ? null : row.peak_memory_bytes / 1024 ** 3)}</td>
              <td>{number(row.load_time_s, ' s')}</td>
              <td>
                <a href={runHref(row.run_id)} data-testid="factory-runs-capsule-result-replay">
                  {row.run_name}
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Receipt({
  capsule,
  onArtifact,
}: {
  capsule: CapsuleDetail;
  onArtifact: (run: string, path: string, title: string) => void;
}) {
  const copy = useCapsuleCopy();
  const receipt = capsule.evidence?.latest_verify_receipt;
  if (!receipt) return <p className="cc-muted">{copy(capsule.evidence ? 'noReceipt' : 'evidenceUnavailable')}</p>;
  const result = receipt.done === true ? 'receiptDone' : receipt.done === false ? 'receiptFailed' : 'receiptUnknown';
  return (
    <div className="cc-receipt" data-testid="factory-runs-capsule-receipt">
      <div className="cc-split-row">
        <strong data-result={result}>{copy(result)}</strong>
        <Integrity state={receipt.integrity} />
      </div>
      <dl className="cc-meta">
        {receipt.state && (
          <div>
            <dt>{copy('state')}</dt>
            <dd>{receipt.state}</dd>
          </div>
        )}
        {receipt.completeness && (
          <div>
            <dt>{copy('completeness')}</dt>
            <dd>{receipt.completeness}</dd>
          </div>
        )}
        <div>
          <dt>{copy('release')}</dt>
          <dd>
            <code>{receipt.release || '—'}</code>
          </dd>
        </div>
        {receipt.created > 0 && (
          <div>
            <dt>{copy('recorded')}</dt>
            <dd>
              <time dateTime={new Date(receipt.created * 1000).toISOString()}>
                {new Date(receipt.created * 1000).toLocaleString()}
              </time>
            </dd>
          </div>
        )}
      </dl>
      {(!receipt.release || receipt.release !== capsule.digest) && (
        <p className="cc-alert">{copy(receipt.release ? 'differentRelease' : 'receiptReleaseUnknown')}</p>
      )}
      {receipt.limitations && <p className="cc-muted">{receipt.limitations}</p>}
      {receipt.integrity === 'verified' && receipt.checks != null && <StructuredData value={receipt.checks} tree />}
      <div className="cc-actions">
        {receipt.path && (
          <button
            className="cc-control"
            type="button"
            onClick={() => onArtifact(receipt.run_id, receipt.path, receipt.artifact_id || receipt.path)}
            data-testid="factory-runs-capsule-receipt-preview"
          >
            {copy('available')}
          </button>
        )}
        <a href={runHref(receipt.run_id, receipt.path)} data-testid="factory-runs-capsule-receipt-replay">
          {copy('run')} · {receipt.run_name}
        </a>
      </div>
    </div>
  );
}

export function CapsuleEvidenceView({
  capsule,
  onArtifact,
}: {
  capsule: CapsuleDetail;
  onArtifact: (run: string, path: string, title: string) => void;
}) {
  const copy = useCapsuleCopy();
  const evidence = capsule.evidence;
  if (!evidence) return <p className="cc-muted">{copy('evidenceUnavailable')}</p>;
  return (
    <>
      {!!evidence.analyses?.length && (
        <section className="cc-section" data-testid="factory-runs-capsule-analyses">
          <h2>{copy('analysisOutput')}</h2>
          {evidence.analyses.map((analysis, index) => (
            <AnalysisOutput
              key={`${analysis.run_id}:${analysis.observation_id || analysis.call || index}`}
              analysis={analysis}
              onArtifact={onArtifact}
            />
          ))}
        </section>
      )}
      <section className="cc-section" data-testid="factory-runs-capsule-results-section">
        <h2>Runtime stage · {copy('results')}</h2>
        {evidence.measurements.length ? (
          <MeasurementRows rows={evidence.measurements} />
        ) : (
          <p className="cc-muted">{copy('noTrials')}</p>
        )}
      </section>
      <section className="cc-section" data-testid="factory-runs-capsule-artifacts-section">
        <h2>{copy('runArtifacts')}</h2>
        {!evidence.artifacts.length && <p className="cc-muted">{copy('noArtifacts')}</p>}
        <ul className="cc-artifact-list">
          {evidence.artifacts.map((artifact) => (
            <li
              key={`${artifact.run_id}:${artifact.artifact_id}`}
              data-testid="factory-runs-capsule-artifact"
              data-variant={artifact.artifact_id}
            >
              <div className="cc-artifact-name">
                <small>
                  {readableName(artifact.kind)} · {artifact.run_name}
                </small>
                <strong>{artifact.display_path || artifact.artifact_id}</strong>
              </div>
              <Integrity state={artifact.integrity} />
              <div className="cc-actions">
                {artifact.path && (
                  <button
                    className="cc-control"
                    type="button"
                    onClick={() =>
                      onArtifact(artifact.run_id, artifact.path, artifact.display_path || artifact.artifact_id)
                    }
                    data-testid="factory-runs-capsule-artifact-preview"
                  >
                    {copy('available')}
                  </button>
                )}
                <a href={runHref(artifact.run_id, artifact.path)} data-testid="factory-runs-capsule-artifact-replay">
                  {copy('run')} →
                </a>
              </div>
            </li>
          ))}
        </ul>
      </section>
      {evidence.runs.length > 0 && (
        <section className="cc-section" data-testid="factory-runs-capsule-related-runs">
          <h2>{copy('relatedRuns')}</h2>
          <div className="cc-actions">
            {evidence.runs.map((run) => (
              <a
                className="cc-control"
                key={run.id}
                href={runHref(run.id)}
                data-testid="factory-runs-capsule-related-run"
                data-variant={run.id}
              >
                {run.name} · {run.kind}
              </a>
            ))}
          </div>
        </section>
      )}
    </>
  );
}

function AnalysisOutput({
  analysis,
  onArtifact,
}: {
  analysis: CapsuleAnalysis;
  onArtifact: (run: string, path: string, title: string) => void;
}) {
  const copy = useCapsuleCopy();
  const [mode, setMode] = useState<'readable' | 'table' | 'chart' | 'raw'>('readable');
  const datasets = useMemo(() => tableData(analysis.values), [analysis.values]);
  const modes = [
    'readable' as const,
    ...(datasets.length ? (['table'] as const) : []),
    ...(datasets.some(({ rows }) => rows.length > 1 && numericColumns(rows).length) ? (['chart'] as const) : []),
    'raw' as const,
  ];
  return (
    <details
      className="cc-analysis-output"
      data-testid="factory-runs-capsule-analysis-output"
      data-variant={analysis.observation_id || analysis.call || analysis.kind}
    >
      <summary>
        <strong>
          {(isRecord(analysis.values) && typeof analysis.values.title === 'string' && analysis.values.title) ||
            readableName(analysis.kind)}
        </strong>
        <small>{analysis.run_name}</small>
        {analysis.integrity && <Integrity state={analysis.integrity} />}
      </summary>
      {analysis.limitations && <p className="cc-muted">{analysis.limitations}</p>}
      <div className="cc-file-modes">
        <div className="cc-switcher">
          {modes.map((option) => (
            <button
              type="button"
              key={option}
              aria-pressed={option === mode}
              onClick={() => setMode(option)}
              data-testid="factory-runs-capsule-analysis-mode"
              data-variant={option}
            >
              {copy(option)}
            </button>
          ))}
        </div>
        <div className="cc-actions">
          {analysis.path && (
            <button
              className="cc-control"
              type="button"
              onClick={() => onArtifact(analysis.run_id, analysis.path!, analysis.report_artifact_id || analysis.kind)}
              data-testid="factory-runs-capsule-analysis-preview"
            >
              {copy('available')}
            </button>
          )}
          <a
            href={runHref(analysis.run_id, analysis.path || undefined)}
            data-testid="factory-runs-capsule-analysis-replay"
          >
            {copy('run')} →
          </a>
        </div>
      </div>
      {mode === 'readable' && <StructuredData value={analysis.values} />}
      {mode === 'raw' && (
        <pre tabIndex={0}>
          <code>{JSON.stringify(analysis.values, null, 2)}</code>
        </pre>
      )}
      {(mode === 'table' || mode === 'chart') && <AnalysisData datasets={datasets} chart={mode === 'chart'} />}
    </details>
  );
}

function verdict(value: boolean | null | undefined, pass: CopyKey, fail: CopyKey): CopyKey {
  return value == null ? 'notRecorded' : value ? pass : fail;
}

export function BuilderRunEvidence({
  capsule,
  onArtifact,
}: {
  capsule: CapsuleDetail;
  onArtifact: (run: string, path: string, title: string) => void;
}) {
  const copy = useCapsuleCopy();
  const run = capsule.evidence?.latest_builder_run;
  const build = run?.build;
  const lab = run?.lab;
  const report = run?.report;
  const digest = build?.binary_sha256 || lab?.binary_sha256;
  const measurements =
    capsule.evidence?.measurements.filter(
      (row) => row.scope !== 'combined' && (digest ? row.binary_sha256 === digest : row.run_id === run?.run_id),
    ) || [];
  const hasLabNumbers = Object.keys(lab?.metrics || {}).length > 0 || measurements.length > 0;
  const origin = (item?: { version?: string | null; run_name?: string } | null) =>
    item?.version && item.version !== capsule.version ? (
      <small className="cc-release-origin" data-testid="factory-runs-capsule-evidence-origin" title={item.run_name}>
        {copy('fromRelease')} {item.version}
      </small>
    ) : null;
  const metricText = (key: string, value: number) => {
    const saved = /^paired_ttft_saved_s_(\d+)$/.exec(key);
    if (saved) return `${value > 0 ? '+' : ''}${number(value, ' s')} ${copy('pairedSaved')} · ${saved[1]} ${copy('tokens').toLowerCase()}`;
    const label = (
      {
        written: 'eventsWritten',
        lost: 'eventsLost',
        bytes_transferred: 'copiedBytes',
        peak_memory_bytes: 'peakMemory',
      } as Record<string, CopyKey | undefined>
    )[key];
    const formatted =
      key.endsWith('_bytes') || key === 'bytes_transferred'
        ? number(value / 1024 ** 3, ' GiB')
        : value.toLocaleString();
    return `${formatted} ${label ? copy(label) : readableName(key)}`;
  };

  return (
    <section className="cc-section cc-builder-run" data-testid="factory-runs-capsule-builder-evidence">
      <div className="cc-split-row">
        <h2>{copy('artifacts')}</h2>
        {run && (
          <div className="cc-actions">
            {report && (
              <button
                className="cc-control"
                type="button"
                onClick={() => onArtifact(run.run_id, report.path, report.artifact_id)}
                data-testid="factory-runs-capsule-iteration-report"
              >
                {copy('iterationReport')}
              </button>
            )}
            <a href={runHref(run.run_id, report?.path)} data-testid="factory-runs-capsule-builder-replay">
              {copy('run')} →
            </a>
          </div>
        )}
      </div>
      {!run && <p className="cc-muted">{copy(capsule.evidence ? 'builderPending' : 'evidenceUnavailable')}</p>}
      {run && (
        <dl className="cc-builder-grid">
          <div>
            <dt>Factory stage · {copy('buildDigest')}</dt>
            <dd data-testid="factory-runs-capsule-binary-digest">
              {digest ? <code title={digest}>{digest}</code> : <span className="cc-muted">{copy('notRecorded')}</span>}
              {build?.artifact && <Integrity state={build.artifact.integrity} />}
              {origin(build)}
            </dd>
          </div>
          <div>
            <dt>Runtime stage · {copy('parity')}</dt>
            <dd data-testid="factory-runs-capsule-parity" data-verdict={lab?.parity ?? undefined}>
              {copy(verdict(lab?.parity, 'parityMatch', 'parityMismatch'))}
              {lab?.parity != null && origin(lab)}
            </dd>
          </div>
          <div>
            <dt>Runtime stage · {copy('activation')}</dt>
            <dd data-testid="factory-runs-capsule-activation" data-verdict={lab?.activation ?? undefined}>
              {copy(verdict(lab?.activation, 'active', 'inactive'))}
              {lab?.activation != null && origin(lab)}
            </dd>
          </div>
          <div>
            <dt>Runtime stage · {copy('labNumbers')}</dt>
            <dd data-testid="factory-runs-capsule-latest-lab">
              {!hasLabNumbers && <span className="cc-muted">{copy('notRecorded')}</span>}
              {measurements.length > 0 && (
                <ul>
                  {measurements.slice(0, 2).map((row) => (
                    <li key={`${row.arm}:${row.observation_ids.join(',')}`}>
                      {row.prompt_tokens} · {copy('ttft')} {number(row.ttft_s, ' s')} · {number(row.decode_tps)}{' '}
                      {copy('decode')}
                    </li>
                  ))}
                </ul>
              )}
              {Object.keys(lab?.metrics || {}).length > 0 && (
                <ul>
                  {Object.entries(lab?.metrics || {})
                    .slice(0, 4)
                    .map(([key, value]) => (
                      <li key={key}>{metricText(key, value)}</li>
                    ))}
                </ul>
              )}
              {hasLabNumbers && origin(lab)}
            </dd>
          </div>
        </dl>
      )}
      {lab?.scope && <p className="cc-muted">{lab.scope}</p>}
      {lab?.binary_sha256 && build?.binary_sha256 && lab.binary_sha256 !== build.binary_sha256 && (
        <p className="cc-alert">
          {copy('labReleaseMismatch')} <code>{lab.binary_sha256}</code>
        </p>
      )}
    </section>
  );
}
