import { createTwoFilesPatch } from 'diff';
import { EngineRequestMethod } from './EngineReportCharts';
import { DiffViewer } from './views/DiffViewer';
import { mmluSummary, numeric, requestIndexFromSpeedSource, requestStateLabel } from './engineBenchModel';
import type { ReactNode } from 'react';
import { ArrowUpRight, CheckCircle2, CircleDot, FileText, GitBranch, Layers3, PackageCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { EvidenceFile, JsonRecord, RunDetail, StoryEvent } from './api';
import { atlasTitle } from './cc/atlasNames.ts';
import { collapseEvents, presentEvent, replayCheckStage, replayEvidenceText, type CuratedMeasurement } from './views/storyModel.ts';
import { ReplayLabel } from './views/NodeEvidence';
import { CorrectionRecord, CorrectionSequence } from './views/CorrectionSequence';
import { correctionStatusAt } from './views/correctionModel';
import { outputCheckCounts } from './views/checkModel';
import { revisionEvent } from './views/nodeEvidenceModel';
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

function ReplayMeasurements({
  measurement,
  onOpenFile,
}: {
  measurement: CuratedMeasurement;
  onOpenFile?: (path: string) => void;
}) {
  const { baseline, rows, accuracy } = measurement;
  const { reference_pct, candidate_pct } = accuracy;
  const hasMmlu = numeric(reference_pct) && numeric(candidate_pct);
  const measuredRows = rows.filter((row) => row.status !== 'excluded');
  const generatedTokens = measuredRows[0]?.generated_tokens;
  const sameGeneration = numeric(generatedTokens) && measuredRows.every((row) => row.generated_tokens === generatedTokens);
  return (
    <section className="factory-curated-measurements" data-testid="factory-runs-curated-measurements">
      {hasMmlu ? (
        <p data-testid="factory-runs-curated-measurement-arms">
          A · NVFP4 baseline. AQB · mixed 2-bit + prefill plan.
          {sameGeneration && ` Both arms generated ${generatedTokens} tokens per request.`}
        </p>
      ) : (
        <p data-testid="factory-runs-curated-measurement-arms">{baseline}.</p>
      )}
      <div className="factory-curated-table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Arm</th>
              <th scope="col">Prompt</th>
              <th scope="col">State</th>
              <th scope="col">TTFT (s)</th>
              <th scope="col">Decode (tok/s)</th>
              <th scope="col">Total (s)</th>
              <th scope="col">Source row</th>
            </tr>
          </thead>
          <tbody>
            {measuredRows.map((row) => (
              <tr key={row.path + row.pointer}>
                <th scope="row">{hasMmlu && row.arm === 'P' ? 'AQB' : row.arm}</th>
                <td>{row.request.slice(1)} ({row.prompt_tokens} rendered)</td>
                <td>
                  {requestStateLabel(row.state, requestIndexFromSpeedSource(row.sources?.[0]))}
                  {row.repeat != null ? ` · ${row.repeat + 1}` : ''}
                </td>
                <td>{(row.ttft_ms / 1000).toFixed(3)}</td>
                <td>{row.decode_tps.toFixed(3)}</td>
                <td>{(row.total_ms / 1000).toFixed(3)}</td>
                <td>
                  <button
                    type="button"
                    data-testid="factory-runs-curated-measurement-source"
                    data-variant={row.arm + row.pointer}
                    onClick={() => onOpenFile?.(row.path)}
                  >
                    {row.pointer}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>
        {hasMmlu ? mmluSummary(accuracy.n, reference_pct, candidate_pct) : `Paired MMLU · ${accuracy.n} questions`}{' '}
        <button type="button" data-testid="factory-runs-curated-accuracy-source" onClick={() => onOpenFile?.(accuracy.path)}>
          Source
        </button>
      </p>
    </section>
  );
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
  nodeEvidence,
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
  nodeEvidence?: ReactNode;
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
  const r8VerifierHelp = detail.contract.contract_id === 'muse-2bit-demo-r8';
  const fileByPath = new Map(detail.files.map((file) => [file.path, file]));
  const groups = collapseEvents(events);
  const verifiedCorrections = new Set(
    events.flatMap(({ correction }) => correction?.kind === 'passing_check' ? correction.finding_ids ?? [] : []),
  );

  if (curated) {
    const focus = curated.steps.find((step) => step.step === currentStep) ?? curated.steps[0];
    const prefillStep = r8VerifierHelp && focus?.node_id === 'size_prefill_batch' && Boolean(focus.capsule_diff);
    const engineMeasurement = (r8VerifierHelp && Boolean(focus?.measurement)) ||
      (detail.contract.contract_id === 'muse-2bit-demo-r9' && focus?.node_id === 'measure_engine');
    const lead = focus?.key_files[0];
    const correction = focus?.correction ?? events.find((event) => event.step === focus?.step)?.correction;
    const stepSummary = focus?.say || focus?.original_summary;
    return (
      <div className="factory-story" data-testid="factory-runs-overview">
        <header className="factory-story-hero" data-testid="factory-runs-overview-brief">
          <span className="factory-story-kicker">{curated.title}</span>
          <p className="factory-curated-label" data-testid="factory-runs-curated-summary">{curated.summary}</p>
          {curated.node_presentation && (
            <details data-testid="factory-runs-curated-check-roles">
              <summary>Who checks what</summary>
              <p>Factory stage runs on the factory machine using builds, digest checks and small fixtures. Runtime stage uses the full model on the target.</p>
              <p>The CC verifier checks that the capsule’s method, tool or build was used correctly. The scheduler writes the node contract and the node verifier checks whether the node met it.</p>
              <p>The factory delivers the image, test requirements and acceptance criteria. The lab agent runs the tests on the target and decides whether the engine passes. Lab acceptance can run without a CC.</p>
            </details>
          )}
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
                {focus.original_kind}
                {(focus.created_utc || focus.created) && (
                  <> · {new Date(focus.created_utc ?? (focus.created ?? 0) * 1000).toLocaleString(i18n.resolvedLanguage, { timeZone: 'America/New_York', dateStyle: 'medium', timeStyle: 'medium' })} ET</>
                )}
              </small>
            </p>
            <h3 title="Presentation title" data-testid="factory-runs-curated-focus-title">
              {focus.presentation_title}
            </h3>
            {curated.graph_mode === 'recorded' && (
              <button
                type="button"
                className="factory-curated-graph-link"
                data-testid="factory-runs-curated-open-graph"
                onClick={() => onOpen('graph')}
              >
                View highlighted graph nodes
              </button>
            )}
            <ReplayLabel value={focus.replayed_from} />
            {!!focus.stages?.length && (
              <p className="factory-story-kicker" data-testid="factory-runs-curated-check-stage">
                {focus.stages.map(replayCheckStage).join(' · ')}
              </p>
            )}
            {(!correction || curated.node_presentation) && stepSummary && (
              <p className="factory-curated-say" data-testid="factory-runs-curated-focus-say">
                {curated.node_presentation ? replayEvidenceText(stepSummary) : stepSummary}
              </p>
            )}
            {correction && (
              <CorrectionRecord
                event={correctionStatusAt(correction, verifiedCorrections)}
                compact
                r8VerifierHelp={r8VerifierHelp}
                files={detail.files}
                onOpenFile={onOpenFile}
              />
            )}
            {focus.capsule_diff && (
              <section aria-label="Capsule changes" data-testid="factory-runs-curated-capsule-diff">
                <h4 data-testid="factory-runs-curated-capsule-diff-caption">{focus.capsule_diff.caption}</h4>
                <DiffViewer content={createTwoFilesPatch('before', 'after',
                  JSON.stringify(focus.capsule_diff.before, null, 2) + '\n',
                  JSON.stringify(focus.capsule_diff.after, null, 2) + '\n')} />
                {prefillStep && <p>Lab load at context 8192: 62,464 MiB cache (same rule, more context).</p>}
              </section>
            )}
            {focus.measurement && <ReplayMeasurements measurement={focus.measurement} onOpenFile={onOpenFile} />}
            {engineMeasurement && (
              <details className="factory-curated-more" data-testid="factory-runs-curated-engine-method">
                <summary>Measurement method</summary>
                <EngineRequestMethod />
              </details>
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
            <details className="factory-curated-more" key={focus.step} open={(curated.graph_mode === 'recorded' && !prefillStep) || undefined}>
              <summary>Recorded summary and other key files</summary>
              {!correction && focus.original_summary && focus.original_summary !== stepSummary && (
                <p className="factory-muted">
                  {curated.node_presentation ? replayEvidenceText(focus.original_summary) : focus.original_summary}
                </p>
              )}
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
            {focus.correction_trail && (
              <details className="factory-curated-more">
                <summary>Correction sequence</summary>
                <CorrectionSequence corrections={focus.correction_trail} files={detail.files} onOpenFile={onOpenFile} />
              </details>
            )}
          </section>
        )}
        {nodeEvidence}
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
                    <ReplayLabel value={step.replayed_from} />
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
      {nodeEvidence}
      <header className="factory-story-hero" data-testid="factory-runs-overview-brief">
        <span className="factory-story-kicker">
          {star ? t('factoryRuns.story.engineComparison') : t('factoryRuns.story.runOverview')}
        </span>
        <h3 data-testid="factory-runs-overview-title">
          {star ? t('factoryRuns.story.starTitle') : t('factoryRuns.story.runQuestion')}
        </h3>
        {star && <p className="factory-story-question">{t('factoryRuns.story.starQuestion')}</p>}
        {!star && (
          <p className="factory-story-question" data-long={(scope || objective || '').length > 320 ? 'true' : undefined}>
            {scope || objective || t('factoryRuns.story.noObjective')}
          </p>
        )}
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
      <RunBuilds detail={detail} events={events} />
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
      {candidates.length > 0 && !detail.cc_overview && (
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
                    {revisionEvent(event) !== undefined && <> · Revision {revisionEvent(event)}</>}
                    {count > 1 && <span className="factory-event-count" data-testid="factory-runs-event-count"> ×{count}</span>}
                    <small className="factory-original-kind" data-testid="factory-runs-event-kind">{shown.kind}</small>
                  </strong>
                  {event.correction ? (
                    <CorrectionRecord
                      event={correctionStatusAt(event.correction, verifiedCorrections)}
                      compact
                      r8VerifierHelp={r8VerifierHelp}
                      files={detail.files}
                      onOpenFile={onOpenFile}
                    />
                  ) : (
                    <span>
                      {event.summary} {eventCapsules?.(event)} <ReplayLabel value={event.replayed_from} />
                      {revisionEvent(event) !== undefined && <small className="factory-muted"><code>{event.id}</code></small>}
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
        </details>
      )}
    </div>
  );
}

// The capsules this week's demo is about; every other bound capsule is listed with them.
const FEATURED: Record<string, string> = {
  'weights.build_weight_pack_compiler': 'Quantization CC Q',
  'engine.size_prefill_batch': 'Prefill CC B',
};

function RunBuilds({ detail, events }: { detail: RunDetail; events: StoryEvent[] }) {
  const overview = detail.cc_overview;
  if (!overview) return null;
  const capsules = new Map<string, { title: string; kind: string; nodes: string[]; passed: boolean }>();
  for (const [node, rows] of Object.entries(overview)) {
    for (const cc of rows) {
      const row = capsules.get(cc.id) ?? { title: text(cc.title) || atlasTitle(cc.id) || cc.id, kind: text(cc.kind), nodes: [], passed: false };
      row.nodes.push(node.replace(/_/g, ' '));
      row.passed = row.passed || cc.verdict === 'passed';
      capsules.set(cc.id, row);
    }
  }
  const counts = Object.values(detail.correction_overview ?? {}).reduce(
    (sum, c) => ({ findings: sum.findings + c.findings, notes: sum.notes + c.notes, repairs: sum.repairs + c.repairs }),
    { findings: 0, notes: 0, repairs: 0 },
  );
  const checks = Object.entries(detail.node_checks ?? {}).flatMap(([node, view]) => {
    const count = outputCheckCounts(view);
    return count.total ? [{ node, ...count }] : [];
  });
  const replays = [...new Map(events.filter((e) => e.replayed_from).map((e) => [JSON.stringify(e.replayed_from), e.replayed_from])).values()];
  const model = text(object(object(detail.contract.subject).model).name);
  const observations = Array.isArray(detail.records.observations) ? detail.records.observations.map(object) : [];
  const finals = observations.filter((o) => o.kind === 'node_contract_final').length;
  const refusals = observations.filter((o) => o.kind === 'node_contract_refusal').length;
  const ordered = [...capsules.entries()].sort(([a], [b]) => Number(!(a in FEATURED)) - Number(!(b in FEATURED)));
  return (
    <section className="factory-story-card factory-run-builds" data-testid="factory-runs-builds">
      <div className="factory-story-card-title">
        <PackageCheck aria-hidden size={17} />
        <h4>What this run builds</h4>
      </div>
      {model && <p className="factory-run-builds-model">{model}</p>}
      <div className="factory-run-builds-grid">
        <div>
          <span className="factory-run-builds-label">Capsules combined</span>
          <strong className="factory-run-builds-value">{capsules.size}</strong>
          <span className="factory-muted">across {Object.keys(overview).length} task graph nodes</span>
        </div>
        <div>
          <span className="factory-run-builds-label">Node contracts finalized</span>
          <strong className="factory-run-builds-value">{finals}</strong>
          <span className="factory-muted">
            by the scheduler agent{detail.scheduler_models?.length ? ` (${detail.scheduler_models.join(', ')})` : ''}
            {' · '}{refusals} refused by control code
          </span>
        </div>
        <div>
          <span className="factory-run-builds-label">Output checks passed / total</span>
          {checks.length ? (
            <ul className="factory-run-builds-checks" data-testid="factory-runs-builds-checks">
              {checks.map(({ node, passed, total }) => (
                <li key={node} data-testid="factory-runs-builds-check" data-variant={node}>
                  {node.replaceAll('_', ' ')} <strong>{passed}/{total}</strong>
                </li>
              ))}
            </ul>
          ) : <span className="factory-muted">No declared output checks</span>}
          <span className="factory-muted">
            {counts.findings} findings · {counts.notes} specific-fix notes · {counts.repairs} repairs
          </span>
        </div>
        <div>
          <span className="factory-run-builds-label">Production replayed</span>
          <strong className="factory-run-builds-value">{replays.length}</strong>
          <span className="factory-run-builds-replays">
            {replays.length ? replays.map((value, index) => <ReplayLabel key={index} value={value} />) : <span className="factory-muted">none yet</span>}
          </span>
        </div>
      </div>
      <ul className="factory-run-builds-ccs" data-testid="factory-runs-builds-capsules">
        {ordered.map(([id, row]) => (
          <li key={id} data-featured={id in FEATURED ? 'true' : undefined}>
            {id in FEATURED && <span className="factory-run-builds-feature">{FEATURED[id]}</span>}
            <strong>{row.title}</strong>
            {row.kind && <small className="factory-muted">{row.kind}</small>}
            <span className="factory-muted factory-run-builds-nodes">{row.nodes.join(' · ')}</span>
            <span className="factory-run-builds-verdict" data-passed={row.passed ? 'true' : 'false'}>
              {row.passed ? 'checked' : 'not checked yet'}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
