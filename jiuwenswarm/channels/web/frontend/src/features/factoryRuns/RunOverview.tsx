import type { ReactNode } from 'react';
import { ArrowUpRight, CheckCircle2, CircleDot, FileText, GitBranch, Layers3 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { EvidenceFile, JsonRecord, RunDetail, StoryEvent } from './api';
import { atlasTitle } from './cc/atlasNames.ts';
import { collapseEvents, presentEvent } from './views/storyModel.ts';
import './story.css';

const capsuleFolders = {
  'observability.build_runtime_event_recorder': 'observability_event_recorder',
  'placement.build_weight_placement_planner': 'weight_placement_planner',
  'engine.build_expert_weight_cache': 'expert_weight_cache',
  'routing.build_expert_demand_predictor': 'expert_demand_predictor',
  'engine.build_batch_layout_mapper': 'batch_layout_mapper',
} as const;
type CapsuleId = keyof typeof capsuleFolders;
type OverviewPanel = 'contract' | 'capsules' | 'graph' | 'measurements' | 'report' | 'terminal';

function evidenceName(file: EvidenceFile) {
  return [file.path, ...(file.display_path?.split(' · ') || [])];
}

function connectedFile(files: EvidenceFile[], part: string) {
  return files.find((file) => evidenceName(file).some((name) => name === part || name.endsWith('/' + part)));
}

function object(value: unknown): JsonRecord {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as JsonRecord) : {};
}

function text(value: unknown) {
  return typeof value === 'string' ? value : '';
}

export function RunOverview({
  detail,
  events,
  eventCapsules,
  onOpen,
  measurements,
  headline,
  onOpenFile,
  onSeek,
  currentStep,
}: {
  detail: RunDetail;
  events: StoryEvent[];
  eventCapsules?: (event: StoryEvent) => ReactNode;
  onOpen: (panel: OverviewPanel, path?: string) => void;
  measurements?: ReactNode;
  headline?: ReactNode;
  onOpenFile?: (path: string) => void;
  onSeek?: (cursor: number) => void;
  currentStep?: number;
}) {
  const { t, i18n } = useTranslation();
  const task = detail.records.tasks?.[0] || {};
  const contractId = text(task.contract_id) || text(detail.contract.contract_id);
  const star = contractId === 'star-deepseek-v1';
  const objective = text(task.objective) || detail.run.objective;
  const scope = text(detail.contract.scope);
  const pinnedId = text(detail.contract.contract_id);
  const source =
    (star ? connectedFile(detail.files, 'star-deepseek-v1.md') : undefined) ||
    (pinnedId ? connectedFile(detail.files, `${pinnedId}.json`) : undefined);
  const ontology = object(detail.contract.ontology);
  const declared = (Array.isArray(ontology.capsule_slices) ? ontology.capsule_slices : [])
    .map((slice) => text(object(slice).capsule))
    .filter(Boolean);
  const recordStack = Array.isArray(detail.stack) ? detail.stack.map(object) : [];
  const candidates = [
    ...new Set(
      [...declared, text(task.component_cc), ...recordStack.slice(1).map((row) => text(row.name))].filter(Boolean),
    ),
  ];
  const nodes = Array.isArray(detail.graph.nodes) ? detail.graph.nodes.map(object) : [];
  const relevant = nodes.filter((node) => !['superseded', 'cancelled'].includes(text(node.state)));
  const complete = relevant.filter((node) => node.state === 'done');
  const failed = relevant.filter((node) => node.state === 'failed');
  const active = relevant.find((node) => node.state === 'running') || relevant.find((node) => node.state === 'ready');
  const integrityIssues = detail.files.filter((file) => ['mismatch', 'missing'].includes(file.integrity)).length;
  const referenceManifest = detail.run.kind === 'bundle' && detail.files.some((file) => file.path === 'MANIFEST.json' && file.integrity === 'untracked');
  const verified = detail.files.filter((file) => file.integrity === 'verified').length;
  const dateFormat = new Intl.DateTimeFormat(i18n.resolvedLanguage, { timeStyle: 'medium' });
  const curated = detail.curated;
  const fileByPath = new Map(detail.files.map((file) => [file.path, file]));
  const groups = collapseEvents(events);

  if (curated) {
    const focus = curated.steps.find((step) => step.step === currentStep) ?? curated.steps[0];
    const lead = focus?.key_files[0];
    return (
      <div className="factory-story" data-testid="factory-runs-overview">
        <header className="factory-story-hero" data-testid="factory-runs-overview-brief">
          <span className="factory-story-kicker">{curated.title}</span>
          <p className="factory-curated-label" data-testid="factory-runs-curated-summary">{curated.summary}</p>
        </header>
        {focus && (
          <section
            className="factory-story-card factory-curated-focus"
            data-testid="factory-runs-curated-focus"
            data-variant={String(focus.step)}
          >
            <p className="factory-curated-count">
              Step {focus.step} of {curated.steps.length}
              <small className="factory-original-kind" title="Original record kind">
                {focus.original_kind} · {focus.created_utc?.slice(0, 19).replace('T', ' ')} UTC
              </small>
            </p>
            <h3 title="Presentation title" data-testid="factory-runs-curated-focus-title">
              {focus.presentation_title}
            </h3>
            {focus.say && (
              <p className="factory-curated-say" data-testid="factory-runs-curated-focus-say">
                {focus.say}
              </p>
            )}
            {lead && (
              <button
                type="button"
                className="factory-curated-lead"
                data-testid="factory-runs-curated-focus-key-file"
                data-variant={lead.path}
                disabled={!fileByPath.get(lead.path)}
                onClick={() => onOpenFile?.(lead.path)}
              >
                ★ {lead.label}
                {lead.why && <small>{lead.why}</small>}
              </button>
            )}
            {(focus.quotes?.length ?? 0) > 0 && (
              <ul className="factory-curated-quotes" data-testid="factory-runs-curated-quotes">
                {focus.quotes?.map((quote) => (
                  <li key={`${quote.path}:${quote.line}`}>
                    <q>{quote.text}</q>
                    <small>
                      {quote.path.replace(/^evidence\//, '')} · line {quote.line} (verbatim)
                    </small>
                  </li>
                ))}
              </ul>
            )}
            <details className="factory-curated-more">
              <summary>Recorded summary and other key files</summary>
              <p className="factory-muted">{focus.original_summary}</p>
              <ul className="factory-curated-key-files">
                {focus.key_files.slice(1).map((key) => (
                  <li key={key.path}>
                    <button
                      type="button"
                      data-testid="factory-runs-curated-key-file"
                      data-variant={key.path}
                      disabled={!fileByPath.get(key.path)}
                      title={key.why}
                      onClick={() => onOpenFile?.(key.path)}
                    >
                      ★ {key.label}
                    </button>
                  </li>
                ))}
              </ul>
            </details>
          </section>
        )}
        <section className="factory-story-card factory-curated" data-testid="factory-runs-curated-steps">
          <ol className="factory-curated-steps">
            {curated.steps.map((step) => (
              <li
                key={step.step}
                data-testid="factory-runs-curated-step"
                data-variant={String(step.step)}
                aria-current={step.step === focus?.step ? 'step' : undefined}
              >
                <button
                  type="button"
                  className="factory-curated-step-title"
                  data-testid="factory-runs-curated-step-seek"
                  onClick={() => step.event_cursor && onSeek?.(step.event_cursor)}
                >
                  <span className="factory-curated-step-number">{step.step}</span>
                  <span>
                    <strong title="Presentation title">{step.presentation_title}</strong>
                    <small className="factory-original-kind" title="Original record kind">
                      {step.original_kind}
                    </small>
                  </span>
                </button>
                {step.key_files[0] && (
                  <button
                    type="button"
                    className="factory-curated-step-key"
                    data-testid="factory-runs-curated-step-key-file"
                    data-variant={step.key_files[0].path}
                    onClick={() => onOpenFile?.(step.key_files[0].path)}
                  >
                    ★ {step.key_files[0].label}
                  </button>
                )}
              </li>
            ))}
          </ol>
        </section>
      </div>
    );
  }

  return (
    <div className="factory-story" data-testid="factory-runs-overview">
      <header className="factory-story-hero" data-testid="factory-runs-overview-brief">
        <span className="factory-story-kicker">
          {star ? t('factoryRuns.story.engineComparison') : t('factoryRuns.story.runOverview')}
        </span>
        <h3 data-testid="factory-runs-overview-title">
          {star ? t('factoryRuns.story.starTitle') : t('factoryRuns.story.runQuestion')}
        </h3>
        {star && <p className="factory-story-question">{t('factoryRuns.story.starQuestion')}</p>}
        {!star && <p className="factory-story-question">{scope || objective || t('factoryRuns.story.noObjective')}</p>}
        {star && objective && (
          <p className="factory-story-context" data-testid="factory-runs-overview-run-objective">
            {objective}
          </p>
        )}
        {contractId && (
          <button
            type="button"
            className="factory-story-text-button"
            onClick={() => onOpen('contract', source?.path)}
            data-testid="factory-runs-overview-contract"
          >
            <FileText aria-hidden size={15} />
            {t('factoryRuns.story.readContract')} <ArrowUpRight aria-hidden size={15} />
          </button>
        )}
      </header>
      {headline}
      <div className="factory-story-overview-grid">
        <section className="factory-story-card" data-testid="factory-runs-overview-progress">
          <div className="factory-story-card-title">
            <GitBranch aria-hidden size={16} />
            <h4>{t('factoryRuns.story.planProgress')}</h4>
          </div>
          {relevant.length ? (
            <>
              <p className="factory-story-card-value">
                {t('factoryRuns.story.nodesComplete', { complete: complete.length, total: relevant.length })}
              </p>
              <progress
                max={relevant.length}
                value={complete.length}
                aria-label={t('factoryRuns.story.planProgress')}
              />
              {active && <p className="factory-muted">{text(active.title) || text(active.node_id)}</p>}
              {failed.length > 0 && (
                <p className="factory-muted">{t('factoryRuns.story.failedNodes', { count: failed.length })}</p>
              )}
            </>
          ) : (
            <p className="factory-story-quiet">{t('factoryRuns.story.noPlan')}</p>
          )}
          <button
            type="button"
            className="factory-story-text-button"
            onClick={() => onOpen('graph')}
            data-testid="factory-runs-overview-graph"
          >
            {t('factoryRuns.story.openGraph')} <ArrowUpRight aria-hidden size={14} />
          </button>
        </section>
        <section className="factory-story-card" data-testid="factory-runs-overview-integrity">
          <div className="factory-story-card-title">
            {integrityIssues ? <CircleDot aria-hidden size={16} /> : <CheckCircle2 aria-hidden size={16} />}
            <h4>{t('factoryRuns.story.evidenceIntegrity')}</h4>
          </div>
          <p className="factory-story-card-value">
            {t('factoryRuns.story.filesChecked', { verified, total: detail.files.length - Number(referenceManifest) })}
          </p>
          {referenceManifest && <p>{t('factoryRuns.story.manifestNote')}</p>}
          {integrityIssues > 0 && (
            <p className="factory-story-digest-warning" role="alert">
              {t('factoryRuns.story.integrityIssues', { count: integrityIssues })}
            </p>
          )}
          <button
            type="button"
            className="factory-story-text-button"
            onClick={() => onOpen('report')}
            data-testid="factory-runs-overview-report"
          >
            {t('factoryRuns.story.openReport')} <ArrowUpRight aria-hidden size={14} />
          </button>
        </section>
      </div>
      {measurements}
      {candidates.length > 0 && (
        <section className="factory-story-card factory-story-capsules" data-testid="factory-runs-overview-capsules">
          <div className="factory-story-section-heading">
            <div className="factory-story-card-title">
              <Layers3 aria-hidden size={17} />
              <h4>{t('factoryRuns.story.capsulesInScope')}</h4>
            </div>
            <button
              type="button"
              className="factory-story-text-button"
              onClick={() => onOpen('capsules')}
              data-testid="factory-runs-overview-capsule-evidence"
            >
              {t('factoryRuns.story.openCapsules')} <ArrowUpRight aria-hidden size={14} />
            </button>
          </div>
          <ul>
            {candidates.map((id) => {
              const folder = Object.prototype.hasOwnProperty.call(capsuleFolders, id)
                ? capsuleFolders[id as CapsuleId]
                : undefined;
              const manifest = folder ? connectedFile(detail.files, `${folder}/cc.yaml`) : undefined;
              const name = folder ? t(`factoryRuns.story.capsuleNames.${folder}`) : atlasTitle(id) ?? id;
              const state = text(recordStack.find((row) => row.name === id)?.state);
              return (
                <li key={id} data-testid="factory-runs-overview-capsule" data-variant={id}>
                  <button
                    type="button"
                    onClick={() => onOpen('capsules', manifest?.path)}
                    data-testid="factory-runs-overview-capsule-open"
                  >
                    <strong>{name}</strong>
                    <ArrowUpRight aria-hidden size={14} />
                    {state && <small>{t(`factoryRuns.story.stackState.${state}`, { defaultValue: state })}</small>}
                    {manifest && (
                      <small
                        className="factory-digest"
                        data-integrity={manifest.integrity}
                        title={manifest.sha256 || undefined}
                      >
                        {t(`factoryRuns.${manifest.integrity}`)}
                        {manifest.sha256 ? ` · ${manifest.sha256.slice(0, 12)}` : ''}
                      </small>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      )}
      {events.length > 0 && (
        <details className="factory-story-card factory-story-activity" data-testid="factory-runs-overview-activity">
          <summary>{t('factoryRuns.story.timeline', { count: events.length })}</summary>
          <ol className="factory-timeline" data-testid="factory-runs-timeline">
            {groups.map(({ event, count }, index) => {
              const shown = presentEvent(event);
              return (
                <li key={`${event.id}-${index}`} data-testid="factory-runs-event" data-variant={event.id}>
                  <time dateTime={new Date(event.created * 1000).toISOString()}>
                    {dateFormat.format(event.created * 1000)}
                  </time>
                  <strong data-testid="factory-runs-event-title">
                    {shown.title}
                    {count > 1 && <span className="factory-event-count" data-testid="factory-runs-event-count"> ×{count}</span>}
                    <small className="factory-original-kind" data-testid="factory-runs-event-kind">{shown.kind}</small>
                  </strong>
                  <span>{event.summary} {eventCapsules?.(event)}</span>
                </li>
              );
            })}
          </ol>
        </details>
      )}
    </div>
  );
}
