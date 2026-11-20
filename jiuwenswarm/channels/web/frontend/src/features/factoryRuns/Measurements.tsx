import { Fragment, useEffect, useId, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getApiBase } from '../../utils/env';
import { request, type RunDetail } from './api';
import { narrativeSummaries } from './iterationModel';
import { measurementCopy } from './measurementCopy';
import {
  aggregateMeasurements,
  chartScale,
  focusedP4Reports,
  promptKey,
  promptOptions,
  type MeasurementArm,
  type FocusedP4,
  type MeasurementLedger,
  type MeasurementMetric,
  type MeasurementPhase,
  type MeasurementRow,
  type MeasurementSource,
  type MetricValue,
} from './measurementModel';
import './measurements.css';

const metrics: MeasurementMetric[] = ['ttft_s', 'inverse_a', 'gap', 'decode_tps', 'peak_memory_bytes'];
const phases: MeasurementPhase[] = ['reconnaissance', 'final'];
const arms = {
  A: 'stock',
  'A+': 'cache',
  C1: 'recorder',
  C2: 'placement',
  C3: 'expertCache',
  C4: 'predictor',
  C5: 'layout',
  D: 'combined',
  S: 'strata',
} as const;
type Labels = ReturnType<typeof measurementCopy>;
type SourceSelection = { title: string; sources: MeasurementSource[] };
type OpenReport = (runId: string, reportId: string, sha256: string) => void;

function useLedger() {
  const [ledger, setLedger] = useState<MeasurementLedger>();
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    request<MeasurementLedger>('/measurements', { signal: controller.signal })
      .then(setLedger)
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      });
    return () => controller.abort();
  }, []);
  return { ledger, error };
}

function useVerifiedP4(detail: RunDetail, benchmarkRunId?: string) {
  const [benchmarks, setBenchmarks] = useState<RunDetail>();
  useEffect(() => {
    if (!benchmarkRunId || benchmarkRunId === detail.run.id) return;
    const controller = new AbortController();
    request<RunDetail>(`/runs/${encodeURIComponent(benchmarkRunId)}`, { signal: controller.signal })
      .then(setBenchmarks)
      .catch(() => {});
    return () => controller.abort();
  }, [benchmarkRunId, detail.run.id]);
  return useMemo(() => {
    const sources = benchmarks && benchmarks.run.id === benchmarkRunId && benchmarkRunId !== detail.run.id
      ? [detail, benchmarks] : [detail];
    const reports = new Map<string, { focus: FocusedP4; runId: string; summary?: string }>();
    for (const source of sources) {
      const observations = source.records.observations || [];
      const { verifiedReportSummaries } = narrativeSummaries(observations);
      for (const focus of focusedP4Reports(observations, source.files)) {
        const summary = verifiedReportSummaries.get(`${focus.report.artifact_id}:${focus.report.sha256}`) || focus.summary;
        reports.set(focus.key, { focus, runId: source.run.id, summary });
      }
    }
    return [...reports.values()];
  }, [benchmarks, benchmarkRunId, detail]);
}

function VerifiedP4Card({ focus, runId, summary, onOpenReport, language, copy }: {
  focus: FocusedP4;
  runId: string;
  summary?: string;
  onOpenReport: OpenReport;
  language: string;
  copy: Labels;
}) {
  const format = new Intl.NumberFormat(language, { maximumFractionDigits: 3 });
  const number = (value: number) => format.format(value);
  const delta = (effect: FocusedP4['rows'][number]['ttftSaved']) => (
    <>
      <strong>{number(effect.estimate)}</strong>
      <small>{copy.conditionalCI} [{effect.ci.map(number).join(', ')}]</small>
      <small>{copy.range} [{effect.range.map(number).join(', ')}]</small>
    </>
  );
  const titleId = useId();
  const profiles = [
    { arm: 'A+', identity: focus.controlProfile },
    { arm: focus.subject, identity: focus.candidateProfile },
  ];
  const candidateVersion = focus.candidateProfile.sourceCommit || focus.candidateProfile.binarySha256;
  return (
    <section className="factory-measurement-focus factory-measurement-summary" aria-labelledby={titleId}
      data-testid="factory-runs-focused-p4" data-variant={focus.manifest.sha256}>
      <header>
        <div>
          <h3 id={titleId}>{copy.focusedP4} · {focus.subject} / A+</h3>
          <p>
            {number(focus.budgetMib / 1024)} {copy.gib} · {copy.matchedPairs} ·{' '}
            <code title={candidateVersion}>{candidateVersion.slice(0, 12)}</code>
          </p>
        </div>
        <button type="button" onClick={() => onOpenReport(runId, focus.report.artifact_id, focus.report.sha256)}>
          {copy.openVerifiedReport}
        </button>
      </header>
      {summary && <p data-testid="factory-runs-focused-p4-summary">{summary}</p>}
      <div className="factory-measurement-table-container">
        <table className="factory-measurement-table">
          <thead>
            <tr>
              <th scope="col">{copy.prompt}</th>
              <th scope="col">{copy.ttft_s} (A+ / {focus.subject})</th>
              <th scope="col">{copy.pairedTtft}</th>
              <th scope="col">{copy.decode_tps} (A+ / {focus.subject})</th>
              <th scope="col">{copy.pairedDecode}</th>
            </tr>
          </thead>
          <tbody>
            {focus.rows.map((row) => (
              <tr key={row.tokens}>
                <th scope="row">{number(row.tokens)}</th>
                <td>{number(row.control.ttft)} / {number(row.candidate.ttft)} {copy.seconds}</td>
                <td>{delta(row.ttftSaved)}</td>
                <td>{number(row.control.decode)} / {number(row.candidate.decode)} {copy.tokenRate}</td>
                <td>{delta(row.decodeGained)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>{copy.p4IntervalScope}</p>
      <details>
        <summary>{copy.launchIdentity}</summary>
        <dl>
          <dt>{copy.manifest}</dt><dd><code>{focus.manifest.sha256}</code></dd>
          <dt>{copy.nativeAnalysis}</dt><dd><code>{focus.analysis.sha256}</code></dd>
          <dt>{copy.nativeVerification}</dt><dd><code>{focus.verification.sha256}</code></dd>
          <dt>{copy.allocatedBank}</dt><dd>{number(focus.allocatedMib)} MiB</dd>
          {profiles.map(({ arm, identity }) => (
            <Fragment key={arm}>
              <dt>{arm} · {copy.profileIdentity}</dt>
              <dd><code>{identity.profileSha256}</code></dd>
              <dt>{arm} · {copy.binaryIdentity}</dt>
              <dd><code>{identity.binarySha256}</code></dd>
              {identity.sourceCommit && <><dt>{arm} · {copy.sourceCommit}</dt><dd><code>{identity.sourceCommit}</code></dd></>}
            </Fragment>
          ))}
        </dl>
      </details>
    </section>
  );
}

function formatValue(value: number, metric: MeasurementMetric, language: string, copy: Labels) {
  const formatted = new Intl.NumberFormat(language, {
    maximumFractionDigits: metric === 'ttft_s' ? 3 : 2,
    style: metric === 'gap' ? 'percent' : 'decimal',
  }).format(metric === 'peak_memory_bytes' ? value / 2 ** 30 : value);
  const unit = {
    ttft_s: copy.seconds,
    decode_tps: copy.tokenRate,
    peak_memory_bytes: copy.gib,
    inverse_a: '×',
    gap: '',
  }[metric];
  return unit ? `${formatted} ${unit}` : formatted;
}

function EvidenceDialog({
  selection,
  copy,
  onClose,
}: {
  selection: SourceSelection;
  copy: Labels;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => dialog.current?.showModal(), []);
  const sources = [...new Map(selection.sources.map((source) => [source.line, source])).values()].sort(
    (a, b) => a.line - b.line,
  );
  return (
    <dialog
      ref={dialog}
      className="factory-measurement-dialog"
      aria-labelledby={titleId}
      onClose={onClose}
      data-testid="factory-runs-measurement-evidence"
    >
      <header>
        <div>
          <p>{copy.evidence}</p>
          <h3 id={titleId}>{selection.title}</h3>
        </div>
        <form method="dialog">
          <button type="submit" data-testid="factory-runs-measurement-evidence-close">
            {copy.close}
          </button>
        </form>
      </header>
      <ul data-testid="factory-runs-measurement-evidence-list">
        {sources.map((source) => {
          const url = `${getApiBase()}/api/factory/measurements/evidence/${source.line}`;
          const status = source.integrity === 'unavailable' ? 'unavailable-source' : source.integrity;
          return (
            <li key={source.line} data-testid="factory-runs-measurement-evidence-item" data-variant={source.line}>
              <div>
                <a
                  href={`${url}?kind=ledger`}
                  target="_blank"
                  rel="noreferrer"
                  data-testid="factory-runs-measurement-ledger-link"
                >
                  {copy.ledger} · {copy.line} {source.line}
                </a>
                {source.path && (
                  <a
                    href={`${url}?kind=result`}
                    aria-label={`${copy.result} · ${source.path}`}
                    target="_blank"
                    rel="noreferrer"
                    data-testid="factory-runs-measurement-result-link"
                  >
                    {source.path}
                  </a>
                )}
              </div>
              <span
                className="factory-measurement-integrity"
                data-testid="factory-runs-measurement-integrity"
                data-variant={source.integrity}
                title={source.sha256}
              >
                {copy[status]}
              </span>
            </li>
          );
        })}
      </ul>
    </dialog>
  );
}

function ValueButton({
  value,
  metric,
  arm,
  language,
  copy,
  onSelect,
  details = false,
}: {
  value: MetricValue;
  metric: MeasurementMetric;
  arm: MeasurementArm;
  language: string;
  copy: Labels;
  onSelect: (selection: SourceSelection) => void;
  details?: boolean;
}) {
  const formatted = formatValue(value.value, metric, language, copy);
  const title = `${arm} · ${copy[metric]} · ${formatted}`;
  const { interval, intervalSource } = value;
  const sources = intervalSource ? [...value.sources, intervalSource] : value.sources;
  const labelRange = ([low, high]: [number, number]) =>
    `${formatValue(low, metric, language, copy)}–${formatValue(high, metric, language, copy)}`;
  return (
    <button
      type="button"
      className="factory-measurement-value"
      aria-label={`${title} · ${copy.evidence}`}
      data-testid="factory-runs-measurement-value"
      data-variant={metric}
      onClick={() => onSelect({ title, sources })}
    >
      <strong>{formatted}</strong>
      {details && (
        <>
          <small>
            n = {value.n}
            {value.controlCounts &&
              Object.entries(value.controlCounts).map(([control, count]) => (
                <span key={control}>
                  {' '}
                  · {control} n = {count}
                </span>
              ))}
          </small>
          <small>
            {interval
              ? `${new Intl.NumberFormat(language, { style: 'percent' }).format(interval.level)} CI · ${labelRange([
                  interval.low,
                  interval.high,
                ])}`
              : copy.unsignedIntervals}
          </small>
          {value.range && (
            <small title={copy.range}>
              {copy.range} · {labelRange(value.range)}
            </small>
          )}
        </>
      )}
    </button>
  );
}

function MetricChart({
  metric,
  rows,
  language,
  copy,
  onSelect,
}: {
  metric: MeasurementMetric;
  rows: MeasurementRow[];
  language: string;
  copy: Labels;
  onSelect: (selection: SourceSelection) => void;
}) {
  const scale = chartScale(rows, metric);
  return (
    <figure
      className="factory-measurement-chart"
      data-testid={metric === 'gap' ? 'factory-runs-gap-chart' : 'factory-runs-measurement-chart'}
      data-variant={metric}
    >
      <figcaption>
        <strong>{copy[metric]}</strong>
        <span>{metric === 'ttft_s' || metric === 'peak_memory_bytes' ? copy.lower : copy.higher}</span>
      </figcaption>
      <ul data-testid="factory-runs-measurement-chart-list">
        {rows.map((row) => {
          const value = row.metrics[metric];
          const end = value ? scale.position(value.value) : scale.zero;
          return (
            <li
              key={row.arm}
              data-testid="factory-runs-measurement-chart-item"
              data-variant={row.arm}
              data-arm={row.arm}
            >
              <span className="factory-measurement-chart-arm">{row.arm}</span>
              <div className="factory-measurement-track" aria-hidden="true">
                <span className="factory-measurement-zero" style={{ left: `${scale.zero}%` }} />
                {value && (
                  <span
                    className="factory-measurement-bar"
                    style={{
                      left: `${Math.min(end, scale.zero)}%`,
                      width: `${Math.abs(end - scale.zero)}%`,
                    }}
                  />
                )}
                {value?.interval && (
                  <span
                    className="factory-measurement-whisker"
                    style={{
                      left: `${scale.position(value.interval.low)}%`,
                      width: `${scale.position(value.interval.high) - scale.position(value.interval.low)}%`,
                    }}
                  />
                )}
              </div>
              {value ? (
                <ValueButton {...{ value, metric, arm: row.arm, language, copy, onSelect }} />
              ) : (
                <span className="factory-measurement-unavailable">—</span>
              )}
            </li>
          );
        })}
      </ul>
    </figure>
  );
}

export function Measurements({ detail, benchmarkRunId, onOpenReport }: {
  detail: RunDetail;
  benchmarkRunId?: string;
  onOpenReport: OpenReport;
}) {
  const { i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? 'en';
  const copy = measurementCopy(language);
  const { ledger, error } = useLedger();
  const focused = useVerifiedP4(detail, benchmarkRunId);
  const [chosenPhase, setPhase] = useState<MeasurementPhase>();
  const [chosenPrompt, setPrompt] = useState('');
  const [comparison, setComparison] = useState<MeasurementMetric>('decode_tps');
  const [selection, setSelection] = useState<SourceSelection>();
  const phase =
    chosenPhase ?? (ledger?.samples.some((sample) => sample.phase === 'final') ? 'final' : 'reconnaissance');
  const prompts = useMemo(() => (ledger ? promptOptions(ledger, phase) : []), [ledger, phase]);
  const prompt = prompts.find((option) => promptKey(option) === chosenPrompt) ?? prompts[0];
  const rows = useMemo(
    () => (ledger && prompt ? aggregateMeasurements(ledger, phase, prompt) : []),
    [ledger, phase, prompt],
  );
  return (
    <section className="factory-measurement-panel" data-testid="factory-runs-measurements">
      {focused.map(({ focus, runId, summary }) => (
        <VerifiedP4Card key={focus.key} {...{ focus, runId, summary, onOpenReport, language, copy }} />
      ))}
      <header className="factory-measurement-heading">
        <div>
          <p>{copy.campaign}</p>
          <h2 data-testid="factory-runs-measurement-heading">{copy.title}</h2>
          <p>{focused.length ? copy.historicalContext : copy.subtitle}</p>
        </div>
        <section className="factory-measurement-controls">
          <div
            className="factory-measurement-phases"
            role="group"
            aria-label={copy.phase}
            data-testid="factory-runs-measurement-phase-group"
          >
            {phases.map((at) => (
              <button
                type="button"
                key={at}
                aria-pressed={at === phase}
                data-testid="factory-runs-measurement-phase"
                data-variant={at}
                onClick={() => setPhase(at)}
              >
                {copy[at]}
              </button>
            ))}
          </div>
          {prompts.length > 0 && (
            <label>
              {copy.prompt}
              <select
                value={promptKey(prompt)}
                onChange={(event) => setPrompt(event.target.value)}
                data-testid="factory-runs-measurement-prompt"
              >
                {prompts.map((option) => (
                  <option key={promptKey(option)} value={promptKey(option)}>
                    {option.tokens.toLocaleString(language)} {copy.tokens}
                    {prompts.filter((item) => item.tokens === option.tokens).length > 1 &&
                      ` · ${option.hash.slice(0, 8)}`}
                  </option>
                ))}
              </select>
            </label>
          )}
        </section>
      </header>
      {ledger && (
        <p
          className="factory-measurement-phase-note"
          data-variant={phase}
          data-testid="factory-runs-measurement-phase-note"
        >
          <span>{copy[phase]}</span>
          {phase === 'final' ? copy.finalDescription : copy.reconnaissanceDescription}
        </p>
      )}
      {!ledger && (
        <p role="status" data-testid="factory-runs-measurement-status">
          {error ? copy.error : copy.loading}
        </p>
      )}
      {!!ledger?.issues.length && (
        <button
          type="button"
          className="factory-measurement-warning"
          data-testid="factory-runs-measurement-issues"
          onClick={() => setSelection({ title: copy.issues, sources: ledger.issues })}
        >
          {copy.issues}
        </button>
      )}
      {ledger && !rows.length && (
        <div className="factory-measurement-empty" data-testid="factory-runs-measurements-empty">
          {phase === 'final' ? copy.finalEmpty : copy.reconnaissanceEmpty}
        </div>
      )}
      {rows.length > 0 && (
        <>
          <div className="factory-measurement-charts">
            <MetricChart metric="ttft_s" {...{ rows, language, copy, onSelect: setSelection }} />
            <div>
              <select
                className="factory-measurement-chart-select"
                aria-label={copy.comparison}
                value={comparison}
                data-testid="factory-runs-measurement-chart-select"
                onChange={(event) => setComparison(event.target.value as MeasurementMetric)}
              >
                {metrics
                  .filter((metric) => metric !== 'ttft_s')
                  .map((metric) => (
                    <option key={metric} value={metric}>
                      {copy[metric]}
                    </option>
                  ))}
              </select>
              <MetricChart metric={comparison} {...{ rows, language, copy, onSelect: setSelection }} />
            </div>
          </div>
          <div className="factory-measurement-table-container">
            <table className="factory-measurement-table" data-testid="factory-runs-measurement-table">
              <thead>
                <tr>
                  <th scope="col">{copy.arm}</th>
                  {metrics.map((metric) => (
                    <th key={metric} scope="col">
                      {copy[metric]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.arm} data-testid="factory-runs-measurement-row" data-variant={row.arm}>
                    <th scope="row">
                      <span>{row.arm}</span>
                      {copy[arms[row.arm]]}
                    </th>
                    {metrics.map((metric) => {
                      const value = row.metrics[metric];
                      return (
                        <td key={metric}>
                          {value ? (
                            <ValueButton
                              details
                              {...{ value, arm: row.arm, metric, language, copy, onSelect: setSelection }}
                            />
                          ) : (
                            <span className="factory-measurement-unavailable" aria-label={copy.unavailable}>
                              —
                            </span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <footer className="factory-measurement-method">
            <p data-testid="factory-runs-measurement-method">{copy.detail}</p>
            <p data-testid="factory-runs-gap-formula">{copy.formulas}</p>
          </footer>
        </>
      )}
      {selection && <EvidenceDialog {...{ selection, copy, onClose: () => setSelection(undefined) }} />}
    </section>
  );
}

export function MeasurementSummary({ onOpenMeasurements }: { onOpenMeasurements?: () => void }) {
  const { i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? 'en';
  const copy = measurementCopy(language);
  const { ledger, error } = useLedger();
  const [selection, setSelection] = useState<SourceSelection>();
  const phase = ledger?.samples.some((sample) => sample.phase === 'final') ? 'final' : 'reconnaissance';
  const prompt = ledger ? promptOptions(ledger, phase)[0] : undefined;
  const rows = ledger && prompt ? aggregateMeasurements(ledger, phase, prompt) : [];
  const combined = rows.find((row) => row.arm === 'D')?.metrics.gap;
  const metric = combined ? 'gap' : 'ttft_s';
  const overviewArms: MeasurementArm[] = combined ? ['D'] : ['A', 'S'];
  const outcomes = rows.filter((row) => overviewArms.includes(row.arm) && row.metrics[metric]);
  return (
    <section className="factory-measurement-summary" data-testid="factory-runs-measurement-summary">
      <header>
        <div>
          <h3>{copy.summary}</h3>
          {prompt && (
            <p>
              {copy[phase]} · {prompt.tokens.toLocaleString(language)} {copy.tokens} · {copy[metric]}
            </p>
          )}
        </div>
        {onOpenMeasurements && (
          <button type="button" data-testid="factory-runs-measurement-open" onClick={onOpenMeasurements}>
            {copy.open}
          </button>
        )}
      </header>
      {!ledger && <p role="status">{error ? copy.error : copy.loading}</p>}
      {ledger && !prompt && <p>{copy.finalEmpty}</p>}
      {prompt && !outcomes.length && <p>{copy.noComparison}</p>}
      <div className="factory-measurement-summary-tiles">
        {outcomes.map((row) => {
          const value = row.metrics[metric];
          return value ? (
            <div key={row.arm} data-testid="factory-runs-measurement-summary-item" data-variant={row.arm}>
              <span>
                {row.arm} · {copy[arms[row.arm]]}
              </span>
              <ValueButton {...{ value, arm: row.arm, metric, language, copy, onSelect: setSelection }} />
            </div>
          ) : null;
        })}
      </div>
      {selection && <EvidenceDialog {...{ selection, copy, onClose: () => setSelection(undefined) }} />}
    </section>
  );
}
