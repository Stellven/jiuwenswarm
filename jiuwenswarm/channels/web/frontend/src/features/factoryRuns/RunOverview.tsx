import type { ReactNode } from 'react';
import { ArrowUpRight, CheckCircle2, CircleDot, FileText, GitBranch, Layers3 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { EvidenceFile, JsonRecord, RunDetail, StoryEvent } from './api';
import { atlasTitle } from './cc/atlasNames.ts';
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
}: {
  detail: RunDetail;
  events: StoryEvent[];
  eventCapsules?: (event: StoryEvent) => ReactNode;
  onOpen: (panel: OverviewPanel, path?: string) => void;
  measurements?: ReactNode;
  headline?: ReactNode;
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
            {events.map((event, index) => (
              <li key={`${event.id}-${index}`} data-testid="factory-runs-event" data-variant={event.id}>
                <time dateTime={new Date(event.created * 1000).toISOString()}>
                  {dateFormat.format(event.created * 1000)}
                </time>
                <strong>{event.kind}</strong>
                <span>{event.summary} {eventCapsules?.(event)}</span>
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}
