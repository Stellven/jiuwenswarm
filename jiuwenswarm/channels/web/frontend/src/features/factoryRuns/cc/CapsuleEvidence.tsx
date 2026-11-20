import { useMemo, useState } from 'react';
import type { CapsuleAnalysis, CapsuleDetail, CapsuleMeasurement } from './capsuleApi';
import { AnalysisData } from './AnalysisData';
import { Integrity, StructuredData } from './CapsuleMaterial';
import { isRecord, numericColumns, readableName, tableData } from './capsuleModel';
import { useCapsuleCopy } from './copy';
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
              key={`${row.run_id}:${row.arm}:${row.prompt_tokens}`}
              data-testid="factory-runs-capsule-result"
              data-variant={`${row.run_id}:${row.arm}:${row.prompt_tokens}`}
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
        <h2>{copy('results')}</h2>
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
