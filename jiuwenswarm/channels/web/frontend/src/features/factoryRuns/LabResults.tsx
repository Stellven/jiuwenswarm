import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { EvidenceFile, JsonRecord } from './api';
import { requestIndexFromSpeedSource, requestStateLabel } from './engineBenchModel';
import { formatChange, formatValue, labResults, type LabCell, type LabReport, type LabResults as Results, type RawRow } from './labModel';
import './measurements.css';
import './labResults.css';

type Selected = { title: string; rows: RawRow[] };

function labConditionLabel(condition: string, row: RawRow) {
  const state = row.state === 'cold' || row.state === 'warm' ? row.state : condition;
  const source = row.source as { path?: string; record?: string | number } | undefined;
  const index = typeof row.request_index === 'number' ? row.request_index : requestIndexFromSpeedSource(source);
  return requestStateLabel(state, index);
}

function Cell({ cell, onSelect, title, condition }: {
  cell?: LabCell;
  onSelect: (value: Selected) => void;
  title: string;
  condition?: string;
}) {
  if (!cell || !cell.rows.length) return <span className="factory-lab-missing">—</span>;
  return (
    <button
      type="button"
      className="factory-lab-cell"
      data-testid="factory-runs-lab-cell"
      data-verdict={cell.reference ? 'reference' : cell.verdict}
      title={cell.rows.length > 1 ? `Median of ${cell.rows.length} rows; open the raw rows` : 'Open the raw row'}
      onClick={() => onSelect({ title, rows: cell.rows })}
    >
      <b>{formatValue(cell.value, cell.unit)}</b>
      {condition && <small data-testid="factory-runs-lab-cell-condition">{condition}</small>}
      {cell.reference ? (
        <small>reference</small>
      ) : (
        cell.change !== undefined && (
          <small data-testid="factory-runs-lab-change">
            {formatChange(cell.change)}
            {cell.verdict === 'better' ? ' better' : cell.verdict === 'worse' ? ' worse' : cell.verdict === 'undetermined' ? ' (direction not declared)' : ''}
          </small>
        )
      )}
      {cell.rows.length > 1 && <small className="factory-lab-count">n={cell.rows.length}</small>}
    </button>
  );
}

function Report({ report, results, onOpenFile }: { report: LabReport; results: Results; onOpenFile: (path: string) => void }) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<Selected>();
  const reference = results.reference.arm;
  const arms = results.arms.filter((arm) => report.tables.some((table) => table.lines.some((line) => line.cells[arm.id])));
  const shownArms = arms.length ? arms : results.arms;
  const museReplay = results.contractId === 'muse-2bit-demo-r8' || results.contractId === 'muse-2bit-demo-r9';
  return (
    <>
      <section className="factory-lab-report-head" data-testid="factory-runs-lab-report" data-valid={String(report.valid)}>
        <p>
          <b>{report.requestId ?? report.obsId}</b> · {report.outcome ?? (report.valid ? 'reported' : 'rejected')}
          {report.lab && <> · lab {report.lab}</>}
          {report.reportFile && (
            <>
              {' '}
              ·{' '}
              <button type="button" className="factory-lab-link" onClick={() => onOpenFile(report.reportFile as string)}>
                raw report
              </button>
            </>
          )}
        </p>
        {report.summary && <p>{report.summary}</p>}
        {!report.valid && (
          <p className="factory-lab-problem" role="alert">
            The lab manager rejected this report: {report.problems.join('; ') || 'no reason recorded'}
          </p>
        )}
      </section>
      {report.tables.map(({ metric, lines }) => (
        <section key={metric.id} className="factory-lab-metric" data-testid="factory-runs-lab-metric" data-variant={metric.id}>
          <h3>
            {metric.id}
            {metric.unit && <small> · {metric.unit}</small>}
            <small>
              {' '}
              ·{' '}
              {metric.better
                ? `${metric.better} is better (contract)`
                : metric.declared
                  ? 'the contract declares no direction: changes are shown without better/worse'
                  : 'not a contract metric: changes are shown without better/worse'}
            </small>
            {metric.primary && <span className="factory-lab-primary">primary</span>}
          </h3>
          {metric.how && <p className="factory-lab-how">{metric.how}</p>}
          <div className="factory-measurement-table-container">
            <table className="factory-measurement-table factory-lab-table">
              <thead>
                <tr>
                  <th scope="col">Prompt</th>
                  <th scope="col">Condition</th>
                  {shownArms.map((arm) => (
                    <th scope="col" key={arm.id} title={arm.summary}>
                      {arm.id}
                      {arm.role && <small> · {arm.role}</small>}
                      {arm.id === reference && <small> · reference</small>}
                      {!arm.declared && <small> · not in contract</small>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {lines.map((line) => {
                  const cellLabels = Object.fromEntries(Object.entries(line.cells).map(([arm, cell]) => [
                    arm,
                    museReplay
                      ? [...new Set(cell.rows.map((row) => labConditionLabel(line.condition, row)))].join(' · ')
                      : line.condition,
                  ]));
                  const distinct = new Set(Object.values(cellLabels));
                  const differentByArm = distinct.size > 1;
                  const label = differentByArm ? 'By arm' : Object.values(cellLabels)[0];
                  return (
                    <tr key={`${line.request}:${line.condition}`}>
                      <th scope="row">{line.request || '—'}</th>
                      <th scope="row">{label || '—'}</th>
                      {shownArms.map((arm) => (
                        <td key={arm.id}>
                          <Cell
                            cell={line.cells[arm.id]}
                            title={`${metric.id} · ${line.request || 'all prompts'} · ${cellLabels[arm.id] || 'all'} · arm ${arm.id}`}
                            condition={differentByArm ? cellLabels[arm.id] : undefined}
                            onSelect={setSelected}
                          />
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ))}
      {!report.tables.length && report.valid && <p className="factory-muted">This report carries no measured results.</p>}
      {report.checks.length > 0 && (
        <section className="factory-lab-metric" data-testid="factory-runs-lab-checks">
          <h3>Contract checks</h3>
          <div className="factory-measurement-table-container">
            <table className="factory-measurement-table factory-lab-table">
              <thead>
                <tr>
                  <th scope="col">Check</th>
                  <th scope="col">Applies to</th>
                  <th scope="col">Verdict</th>
                  <th scope="col">Detail</th>
                </tr>
              </thead>
              <tbody>
                {report.checks.map((check) => (
                  <tr key={check.id} data-testid="factory-runs-lab-check" data-variant={check.id} data-verdict={check.verdict}>
                    <th scope="row" title={check.does}>
                      {check.id}
                      {!check.declared && <small> · not in contract</small>}
                    </th>
                    <td>{check.appliesTo.join(', ') || '—'}</td>
                    <td>
                      {check.rows.length ? (
                        <button
                          type="button"
                          className="factory-lab-cell"
                          data-verdict={check.verdict === 'pass' ? 'better' : check.verdict === 'fail' ? 'worse' : undefined}
                          onClick={() => setSelected({ title: `check ${check.id}`, rows: check.rows })}
                        >
                          <b>{check.verdict === 'not_run' ? t('factoryRuns.ccActivity.noLabVerdict') : check.verdict}</b>
                          {check.rows.length > 1 && (
                            <small>{check.rows.map((row) => `${row.arm ?? ''} ${row.verdict === 'not_run'
                              ? t('factoryRuns.ccActivity.noLabVerdict') : row.verdict ?? ''}`.trim()).join(' · ')}</small>
                          )}
                        </button>
                      ) : (
                        <span className="factory-lab-missing">no result</span>
                      )}
                    </td>
                    <td className="factory-lab-detail">
                      {check.rows.map((row) => (typeof row.detail === 'string' ? row.detail : '')).filter(Boolean).join(' · ') ||
                        check.does}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {report.notRun.length > 0 && (
        <section className="factory-lab-metric" data-testid="factory-runs-lab-not-run">
          <h3>{t('factoryRuns.ccActivity.labOmissions')}</h3>
          <ul>
            {report.notRun.map((row, index) => (
              <li key={`${row.test_id}:${index}`}>
                <code>{row.test_id}</code> {typeof row.reason === 'string' ? row.reason : ''}
              </li>
            ))}
          </ul>
        </section>
      )}
      {report.limitations && <p className="factory-lab-how">Limits stated by the lab: {report.limitations}</p>}
      {selected && (
        <section className="factory-lab-raw" data-testid="factory-runs-lab-raw">
          <header>
            <b>Raw report rows · {selected.title}</b>
            <span>
              {report.reportFile && (
                <button type="button" className="factory-lab-link" onClick={() => onOpenFile(report.reportFile as string)}>
                  open report file
                </button>
              )}{' '}
              <button type="button" className="factory-lab-link" onClick={() => setSelected(undefined)}>
                close
              </button>
            </span>
          </header>
          <pre>{JSON.stringify(selected.rows, null, 2)}</pre>
        </section>
      )}
    </>
  );
}

export function LabResults({
  contract,
  observations,
  files,
  onOpenFile,
}: {
  contract: JsonRecord;
  observations?: JsonRecord[];
  files: EvidenceFile[];
  onOpenFile: (path: string) => void;
}) {
  const results = useMemo(() => labResults(contract, observations, files), [contract, observations, files]);
  const [chosen, setChosen] = useState<string>();
  if (!results) return null;
  const valid = results.reports.filter((report) => report.valid);
  const report =
    results.reports.find((item) => item.obsId === chosen) ?? valid[valid.length - 1] ?? results.reports[results.reports.length - 1];
  return (
    <section className="factory-measurement-panel factory-lab-panel" data-testid="factory-runs-lab-results">
      <header className="factory-measurement-heading">
        <div>
          <p className="factory-story-kicker">Lab results · {results.contractId}</p>
          <h2>Arms against {results.reference.arm ?? 'no reference arm'}</h2>
          <p>
            Reference arm from the {results.reference.source}. Arms: {results.arms.map((arm) => arm.id).join(', ') || 'none declared'}.
            Every number opens the raw row of the lab report recorded by the lab manager.
          </p>
        </div>
        {results.reports.length > 1 && (
          <label className="factory-lab-select">
            Report
            <select
              value={report?.obsId}
              data-testid="factory-runs-lab-report-select"
              onChange={(event) => setChosen(event.target.value)}
            >
              {results.reports.map((item) => (
                <option key={item.obsId} value={item.obsId}>
                  {item.requestId ?? item.obsId} · {item.valid ? item.outcome : 'rejected'}
                </option>
              ))}
            </select>
          </label>
        )}
      </header>
      {report ? (
        <Report key={report.obsId} report={report} results={results} onOpenFile={onOpenFile} />
      ) : (
        <p className="factory-muted" data-testid="factory-runs-lab-empty">
          No lab report yet. The lab manager records one when a lab answers this run&apos;s lab request.
        </p>
      )}
    </section>
  );
}
