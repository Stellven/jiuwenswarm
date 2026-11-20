import { useEffect, useId, useMemo } from 'react';
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  ClipboardList,
  FlaskConical,
  GitBranch,
  Hammer,
  NotebookText,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { EvidenceFile, JsonRecord, RunDetail, Run } from './api';
import { asRecord, buildIterations, text, type Iteration, type IterationArtifact } from './iterationModel';
import { FactoryStructuredReport } from './FactoryStructuredReport';
import './iterations.css';

type OpenSource = (file: EvidenceFile) => void;
type OpenChild = (id: string, panel: 'diffs' | 'report' | 'terminal', sourceId?: string, sha256?: string) => void;

function reveal(id: string) {
  const target = document.getElementById(id);
  if (target instanceof HTMLDetailsElement) target.open = true;
  target?.focus({ preventScroll: true });
  target?.scrollIntoView({ block: 'center' });
}

function SourceLink({ file, onOpen, label }: { file: EvidenceFile; onOpen: OpenSource; label?: string }) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      className="factory-iteration-source"
      onClick={() => onOpen(file)}
      data-testid="factory-runs-iteration-source"
      data-variant={file.path}
    >
      <span>{label || file.display_path || file.path}</span>
      <span className="factory-digest" data-integrity={file.integrity} title={file.sha256 || undefined}>
        {t(`factoryRuns.${file.integrity}`)}
        {file.sha256 ? ` · ${file.sha256.slice(0, 12)}` : ''}
      </span>
      <ArrowUpRight aria-hidden size={14} />
    </button>
  );
}

function RawRecord({ value }: { value: JsonRecord }) {
  const { t } = useTranslation();
  return (
    <details className="factory-iteration-raw" data-testid="factory-runs-iteration-record">
      <summary>{t('factoryRuns.iteration.record')}</summary>
      <pre className="factory-json">{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function RecordedDecision({
  decision,
  source,
  onOpen,
  operator,
}: {
  decision: JsonRecord;
  source?: EvidenceFile;
  onOpen: OpenSource;
  operator?: boolean;
}) {
  const { t } = useTranslation();
  const action = asRecord(decision.action);
  const reason = operator ? '' : text(decision.reason_for_change);
  return (
    <>
      {text(decision.hypothesis) && <p>{text(decision.hypothesis)}</p>}
      {reason && <p className="factory-iteration-reason">{reason}</p>}
      {(action.type || action.template_id) && (
        <dl className="factory-iteration-properties">
          {text(action.type) && (
            <>
              <dt>{t('factoryRuns.iteration.action')}</dt>
              <dd>{text(action.type)}</dd>
            </>
          )}
          {text(action.template_id) && (
            <>
              <dt>{t('factoryRuns.template')}</dt>
              <dd>{text(action.template_id)}</dd>
            </>
          )}
        </dl>
      )}
      {source && <SourceLink file={source} onOpen={onOpen} label={t('factoryRuns.iteration.decisionsFile')} />}
      <RawRecord value={decision} />
    </>
  );
}

export function Iterations({
  detail,
  runs,
  onOpenSource,
  onOpenChild,
  onOpenDecision,
  focusedDecisionId,
}: {
  detail: RunDetail;
  runs: Run[];
  onOpenSource: OpenSource;
  onOpenChild: OpenChild;
  onOpenDecision: (runId: string, decisionId: string) => void;
  focusedDecisionId?: string;
}) {
  const { t } = useTranslation();
  const prefix = useId();
  const iterations = useMemo(() => buildIterations(detail.records, detail.files), [detail.records, detail.files]);
  const source = (path: string) => detail.files.find((file) => file.path === path);
  const decisionSource = source('records/decisions.json');
  const observationSource = source('records/observations.json');
  const planTarget = (iteration: Iteration) => `${prefix}-plan-${encodeURIComponent(iteration.id)}`;
  const reportTarget = (iteration: Iteration) => `${prefix}-report-${encodeURIComponent(iteration.id)}`;
  const focusedIteration = focusedDecisionId
    ? iterations.find(
        (item) => item.plan?.decision_id === focusedDecisionId || item.recordedPlanId === focusedDecisionId,
      )
    : undefined;
  const focusedDecision =
    focusedDecisionId && detail.records.decisions?.find((item) => item.decision_id === focusedDecisionId);
  const focusedTarget = focusedIteration ? planTarget(focusedIteration) : `${prefix}-spotlight`;
  useEffect(() => {
    if (!focusedDecisionId) return;
    const timer = window.requestAnimationFrame(() => reveal(focusedTarget));
    return () => window.cancelAnimationFrame(timer);
  }, [focusedDecisionId, focusedTarget]);

  const feedback = iterations.flatMap((iteration) => {
    const edges = iteration.nextDecisions.map((edge) => ({
      iteration,
      ...edge,
      target: iterations.find((item) => item.activeRev === edge.decision.rev),
    }));
    const target = iterations.find((item) => item.id === iteration.linkedNextId);
    if (!edges.length && (target || iteration.explicitNextId)) {
      return [{ iteration, decision: target?.plan ?? {}, cited: [iteration.reportId].filter(Boolean), target }];
    }
    return edges;
  });
  const anchorButton = (label: string, target: string, testId: string) => (
    <button className="factory-story-text-button" type="button" onClick={() => reveal(target)} data-testid={testId}>
      {label} <ArrowUpRight aria-hidden size={14} />
    </button>
  );

  const artifactLinks = (iteration: Iteration, kinds: IterationArtifact['kind'][]) => {
    const local = iteration.linkedFiles.filter((entry) => kinds.includes(entry.kind));
    const remote = iteration.remoteReferences.filter((entry) => kinds.includes(entry.kind));
    const items = [
      ...local.map(({ file }) => <SourceLink key={file.path} file={file} onOpen={onOpenSource} />),
      ...remote.map((ref) => {
        const run = runs.find((item) => item.task_id === ref.taskId);
        return run ? (
          <button
            key={`${ref.taskId}:${ref.id}`}
            type="button"
            className="factory-iteration-source"
            data-testid="factory-runs-iteration-remote-artifact"
            data-variant={ref.id}
            onClick={() =>
              onOpenChild(
                run.id,
                ref.kind === 'report' || ref.kind === 'prior' ? 'report' : 'terminal',
                ref.id,
                ref.sha256,
              )
            }
          >
            {ref.id} <ArrowUpRight aria-hidden size={14} />
          </button>
        ) : (
          <p key={ref.id} className="factory-iteration-cites">
            {t('factoryRuns.iteration.unavailable', { id: ref.id })}
          </p>
        );
      }),
    ];
    return items.length > 2 ? (
      <>
        {items.slice(0, 2)}
        <details className="factory-iteration-raw">
          <summary>{t('factoryRuns.iteration.moreEvidence', { count: items.length - 2 })}</summary>
          {items.slice(2)}
        </details>
      </>
    ) : (
      items
    );
  };

  return (
    <section
      className="factory-iterations"
      aria-label={t('factoryRuns.iterations')}
      data-testid="factory-runs-iterations"
    >
      <header className="factory-iterations-header">
        <div>
          <h3>{t('factoryRuns.iterations')}</h3>
          <p>{t('factoryRuns.iteration.description')}</p>
        </div>
        <div className="factory-iteration-flow" aria-label={t('factoryRuns.iteration.description')}>
          <span>
            <Hammer aria-hidden size={14} />
            {t('factoryRuns.iteration.do')}
          </span>
          <ArrowRight aria-hidden size={14} />
          <span>
            <FlaskConical aria-hidden size={14} />
            {t('factoryRuns.iteration.lab')}
          </span>
          <ArrowRight aria-hidden size={14} />
          <span>
            <NotebookText aria-hidden size={14} />
            {t('factoryRuns.iteration.report')}
          </span>
        </div>
      </header>
      {focusedDecisionId && !focusedIteration && (
        <section
          className="factory-story-card"
          id={`${prefix}-spotlight`}
          tabIndex={-1}
          data-testid="factory-runs-iteration-linked-plan"
        >
          <h4>{t('factoryRuns.iteration.nextPlan')}</h4>
          {focusedDecision ? (
            <RecordedDecision decision={focusedDecision} source={decisionSource} onOpen={onOpenSource} />
          ) : (
            <p>{t('factoryRuns.iteration.unavailableDecision')}</p>
          )}
        </section>
      )}
      {!iterations.length ? (
        <div className="factory-story-card" data-testid="factory-runs-iterations-empty">
          <h4>{t('factoryRuns.iteration.emptyTitle')}</h4>
          <p>{t('factoryRuns.iteration.empty')}</p>
        </div>
      ) : (
        <>
          <section
            className="factory-story-card factory-iteration-learning"
            data-testid="factory-runs-iteration-learning"
          >
            <h4>
              <GitBranch aria-hidden size={17} />
              {t('factoryRuns.iteration.learning')}
            </h4>
            {feedback.map(({ iteration, decision, cited, target: next }) => {
              const targetRun = runs.find(
                (run) => run.task_id === iteration.explicitNextTask && run.id !== detail.run.id,
              );
              const citedReport = iteration.linkedFiles.find(
                ({ file, kind }) =>
                  kind === 'report' &&
                  file.artifact_ids?.some((id) =>
                    cited.some((ref) => ref === id || iteration.reportAliases.get(ref) === id),
                  ),
              );
              const label =
                typeof decision.rev === 'number'
                  ? t('factoryRuns.iteration.decision', { rev: decision.rev })
                  : iteration.explicitNextId || t('factoryRuns.iteration.nextPlan');
              return (
                <article
                  key={`${iteration.id}:${decision.rev ?? label}`}
                  className="factory-iteration-feedback"
                  data-testid="factory-runs-iteration-feedback"
                >
                  <div className="factory-iteration-feedback-labels">
                    {citedReport ? (
                      <button
                        type="button"
                        className="factory-story-text-button"
                        data-testid="factory-runs-iteration-feedback-report"
                        onClick={() => onOpenSource(citedReport.file)}
                      >
                        {t('factoryRuns.iteration.reportOf', { number: iteration.number })}{' '}
                        <ArrowUpRight aria-hidden size={14} />
                      </button>
                    ) : (
                      anchorButton(
                        t('factoryRuns.iteration.reportOf', { number: iteration.number }),
                        reportTarget(iteration),
                        'factory-runs-iteration-feedback-report',
                      )
                    )}
                    <ArrowRight aria-hidden size={16} />
                    {next ? (
                      anchorButton(label, planTarget(next), 'factory-runs-iteration-feedback-plan')
                    ) : targetRun && iteration.explicitNextId ? (
                      <button
                        type="button"
                        className="factory-story-text-button"
                        data-testid="factory-runs-iteration-remote-plan"
                        onClick={() => onOpenDecision(targetRun.id, iteration.explicitNextId)}
                      >
                        {label} <ArrowUpRight aria-hidden size={14} />
                      </button>
                    ) : (
                      <strong>{label}</strong>
                    )}
                  </div>
                  {(next?.rationale || (!iteration.operator && text(decision.reason_for_change))) && (
                    <p className="factory-iteration-reason">{next?.rationale || text(decision.reason_for_change)}</p>
                  )}
                  {iteration.template &&
                    text(asRecord(decision.action).template_id) &&
                    iteration.template !== asRecord(decision.action).template_id && (
                      <p>
                        {t('factoryRuns.iteration.templateChanged', {
                          from: iteration.template,
                          to: asRecord(decision.action).template_id,
                        })}
                      </p>
                    )}
                  {cited.length > 0 && (
                    <p className="factory-iteration-cites">
                      {t('factoryRuns.iteration.explicitCitations', { refs: cited.join(', ') })}
                    </p>
                  )}
                  {!next &&
                    !(targetRun && iteration.explicitNextId) &&
                    (Object.keys(decision).length ? (
                      <RecordedDecision
                        decision={decision}
                        source={decisionSource}
                        onOpen={onOpenSource}
                        operator={iteration.operator}
                      />
                    ) : (
                      <p>{t('factoryRuns.iteration.unavailableDecision')}</p>
                    ))}
                </article>
              );
            })}
            {iterations.flatMap((iteration) => iteration.successors.map((edge) => {
              const run = runs.find((item) => item.task_id === edge.task && item.kind === 'live')
                ?? runs.find((item) => item.task_id === edge.task);
              return (
                <article key={edge.id} className="factory-iteration-feedback" data-testid="factory-runs-successor">
                  <SourceLink file={edge.reportFile} onOpen={onOpenSource} />
                  <ArrowRight aria-hidden size={16} />
                  {run && <button className="factory-story-text-button" type="button"
                    onClick={() => onOpenDecision(run.id, edge.id)}>{edge.id} <ArrowUpRight aria-hidden size={14} /></button>}
                  <SourceLink file={edge.decisionFile} onOpen={onOpenSource} label={run ? undefined : edge.id} />
                  {edge.reason && <p className="factory-iteration-reason">{edge.reason}</p>}
                </article>
              );
            }))}
            {!feedback.length && iterations.every((item) => !item.successors.length) &&
              <p>{t('factoryRuns.iteration.noFollowup')}</p>}
          </section>
          <ol className="factory-iteration-list">
            {iterations.map((iteration, index) => {
              const child = runs.find((run) => run.task_id === iteration.childTask);
              const contract = text(iteration.contract.contract_id);
              const verdict = text(iteration.reportData.verdict) || text(iteration.reportData.status);
              const reportNotes = Array.isArray(iteration.reportData.limitations)
                ? iteration.reportData.limitations.filter((note): note is string => typeof note === 'string')
                : [];
              const priorReports = artifactLinks(iteration, ['prior']);
              const diffFiles = artifactLinks(iteration, ['diff']);
              const labFiles = artifactLinks(iteration, ['lab']);
              const analysisFiles = artifactLinks(iteration, ['report', 'analysis']);
              const state = iteration.iterationStatus || iteration.state;
              return (
                <li
                  key={iteration.id}
                  className="factory-iteration-item"
                  data-testid="factory-runs-iteration"
                  data-variant={iteration.id}
                >
                  <div className="factory-iteration-number" aria-hidden="true">
                    {iteration.number}
                  </div>
                  <article className="factory-story-card factory-iteration-card">
                    <header>
                      <div>
                        <h4>{t('factoryRuns.iteration.number', { number: iteration.number })}</h4>
                        <p>
                          {iteration.template || iteration.id}
                          {iteration.operator ? ` · ${t('factoryRuns.iteration.operator')}` : ''}
                        </p>
                      </div>
                      {state && (
                        <span className="factory-iteration-state">
                          {t(`factoryRuns.iteration.states.${state}`, { defaultValue: state })}
                        </span>
                      )}
                    </header>
                    <details
                      className="factory-iteration-plan"
                      id={planTarget(iteration)}
                      tabIndex={-1}
                      open={index === 0}
                      data-testid="factory-runs-iteration-plan"
                    >
                      <summary>
                        <ClipboardList aria-hidden size={16} />
                        {t('factoryRuns.iteration.plan')}
                        {iteration.activeRev !== undefined && (
                          <span>{t('factoryRuns.iteration.decision', { rev: iteration.activeRev })}</span>
                        )}
                      </summary>
                      {iteration.plan ? (
                        <RecordedDecision
                          decision={iteration.plan}
                          source={decisionSource}
                          onOpen={onOpenSource}
                          operator={iteration.operator}
                        />
                      ) : (
                        <p>{iteration.rationale || t('factoryRuns.iteration.noPlan')}</p>
                      )}
                      {iteration.recordedPlanId && !iteration.plan && (
                        <p className="factory-iteration-cites">{iteration.recordedPlanId}</p>
                      )}
                      {iteration.inputs.length > 0 && (
                        <p className="factory-iteration-cites">
                          {t('factoryRuns.iteration.planInputs', { refs: iteration.inputs.join(', ') })}
                        </p>
                      )}
                      {(!Array.isArray(priorReports) || priorReports.length > 0) && (
                        <div className="factory-iteration-prior" data-testid="factory-runs-iteration-prior-reports">
                          <p className="factory-iteration-cites">{t('factoryRuns.iteration.priorReports')}</p>
                          {priorReports}
                        </div>
                      )}
                    </details>
                    <div className="factory-iteration-stages">
                      <section data-testid="factory-runs-iteration-do">
                        <h5>
                          <Hammer aria-hidden size={15} />
                          {t('factoryRuns.iteration.doTitle')}
                        </h5>
                        {iteration.capsuleIds.length > 0 && (
                          <ul className="factory-iteration-capsules">
                            {iteration.capsuleIds.map((id) => (
                              <li key={id}>{id}</li>
                            ))}
                          </ul>
                        )}
                        {!iteration.capsuleIds.length && <p>{t('factoryRuns.iteration.noCapsules')}</p>}
                        {iteration.component && (
                          <p>{t('factoryRuns.iteration.component', { id: iteration.component })}</p>
                        )}
                        {iteration.sourceCommit && (
                          <p>{t('factoryRuns.iteration.sourceCommit', { commit: iteration.sourceCommit })}</p>
                        )}
                        {diffFiles}
                        {Array.isArray(diffFiles) && !diffFiles.length && <p>{t('factoryRuns.iteration.noDiff')}</p>}
                        {child && (
                          <button
                            type="button"
                            className="factory-story-text-button"
                            data-testid="factory-runs-iteration-child-diffs"
                            onClick={() => onOpenChild(child.id, 'diffs')}
                          >
                            {t('factoryRuns.iteration.childDiffs')} <ArrowUpRight aria-hidden size={14} />
                          </button>
                        )}
                      </section>
                      <section data-testid="factory-runs-iteration-lab">
                        <h5>
                          <FlaskConical aria-hidden size={15} />
                          {t('factoryRuns.iteration.labTitle')}
                        </h5>
                        {contract && <p>{t('factoryRuns.iteration.contract', { id: contract })}</p>}
                        {verdict && (
                          <p className="factory-iteration-verdict">
                            {t('factoryRuns.iteration.labVerdict', {
                              verdict: t(`factoryRuns.iteration.states.${verdict}`, { defaultValue: verdict }),
                            })}
                          </p>
                        )}
                        {!verdict && (
                          <p>
                            {iteration.labState
                              ? t(`factoryRuns.iteration.states.${iteration.labState}`, {
                                  defaultValue: iteration.labState,
                                })
                              : t('factoryRuns.iteration.noLab')}
                          </p>
                        )}
                        {labFiles}
                        {child && iteration.attemptId && (
                          <button
                            type="button"
                            className="factory-story-text-button"
                            data-testid="factory-runs-iteration-child-lab"
                            onClick={() => onOpenChild(child.id, 'terminal', `${iteration.attemptId}:campaign.json`)}
                          >
                            {t('factoryRuns.iteration.childLab')} <ArrowUpRight aria-hidden size={14} />
                          </button>
                        )}
                        {verdict &&
                          anchorButton(
                            t('factoryRuns.iteration.labEvidence'),
                            reportTarget(iteration),
                            'factory-runs-iteration-lab-record',
                          )}
                      </section>
                      <section id={reportTarget(iteration)} tabIndex={-1} data-testid="factory-runs-iteration-report">
                        <h5>
                          <NotebookText aria-hidden size={15} />
                          {t('factoryRuns.iteration.reportTitle')}
                        </h5>
                        {iteration.analysisCapsules.length > 0 && (
                          <ul className="factory-iteration-capsules">
                            {iteration.analysisCapsules.map((id) => (
                              <li key={id}>{id}</li>
                            ))}
                          </ul>
                        )}
                        {iteration.resultId && <code>{iteration.resultId}</code>}
                        {iteration.resultId && observationSource && (
                          <SourceLink
                            file={observationSource}
                            onOpen={onOpenSource}
                            label={t('factoryRuns.iteration.observationsFile')}
                          />
                        )}
                        {Object.keys(iteration.reportData).length > 0 && (
                          <details className="factory-iteration-raw" data-testid="factory-runs-iteration-analysis-data">
                            <summary>{t('factoryRuns.iteration.analysisData')}</summary>
                            <FactoryStructuredReport content={JSON.stringify(iteration.reportData, null, 2)} />
                          </details>
                        )}
                        {reportNotes.length > 0 && (
                          <details className="factory-iteration-raw">
                            <summary>{t('factoryRuns.iteration.limitations')}</summary>
                            <ul>
                              {reportNotes.map((note) => (
                                <li key={note}>{note}</li>
                              ))}
                            </ul>
                          </details>
                        )}
                        {analysisFiles}
                        {iteration.analysisObservations.map((item) => (
                          <details
                            className="factory-iteration-raw"
                            key={text(item.obs_id)}
                            data-testid="factory-runs-iteration-analysis-observation"
                          >
                            <summary>{text(item.kind)}</summary>
                            <FactoryStructuredReport content={JSON.stringify(item.values ?? item, null, 2)} />
                          </details>
                        ))}
                        {!iteration.resultId &&
                          Array.isArray(analysisFiles) &&
                          !analysisFiles.length &&
                          !iteration.analysisObservations.length && <p>{t('factoryRuns.iteration.noReport')}</p>}
                        {child && (
                          <button
                            type="button"
                            className="factory-story-text-button"
                            data-testid="factory-runs-iteration-child-report"
                            onClick={() => onOpenChild(child.id, 'report')}
                          >
                            {t('factoryRuns.iteration.childReport')} <ArrowUpRight aria-hidden size={14} />
                          </button>
                        )}
                        {text(iteration.followup.objective) && (
                          <p className="factory-iteration-proposal">
                            <strong>{t('factoryRuns.iteration.proposed')}</strong> {text(iteration.followup.objective)}
                          </p>
                        )}
                        {!iteration.successors.length && !iteration.nextDecisions.length && !iteration.linkedNextId && !iteration.explicitNextId && (
                          <p className="factory-iteration-cites">{t('factoryRuns.iteration.noFollowup')}</p>
                        )}
                      </section>
                    </div>
                  </article>
                  {index < iterations.length - 1 && (
                    <ArrowDown className="factory-iteration-next" aria-hidden size={17} />
                  )}
                </li>
              );
            })}
          </ol>
        </>
      )}
    </section>
  );
}
