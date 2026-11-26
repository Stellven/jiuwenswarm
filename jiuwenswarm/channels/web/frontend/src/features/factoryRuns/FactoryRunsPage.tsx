import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Plus, RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  factoryApi,
  type EvidenceFile,
  type FileContent,
  type JsonRecord,
  type RunDetail,
  type RunList,
  type RunState as RunStateRecord,
  type RunOperation,
  type SessionSnapshot,
  type StoryEvent,
} from './api';
import { Measurements, MeasurementSummary } from './Measurements';
import { FinalHeadlines, useFinalHeadlines } from './FinalHeadlines';
import { RunOverview } from './RunOverview';
import { LabResults } from './LabResults';
import { isContractV2 } from './labModel';
import { nodeActions, operatorEnabled, pauseStatement, type Controls, type NodeOperator, type PlanNode } from './views/checkModel';
import { CapsuleOverviewStrip, NodeEvidence, ReplayLabel } from './views/NodeEvidence';
import { RunState } from './views/RunState';
import { evidenceText, revisionEvent, runOperations } from './views/nodeEvidenceModel';
import './labResults.css';
import { Iterations } from './Iterations';
import { FactoryReport } from './FactoryReport';
import { reportFiles } from './reportModel';
import { LiveSession } from './LiveSession';
import { LaunchSessionDialog } from './LaunchSessionDialog';
import { DataViewer } from './views/DataViewer';
import { evidenceKind } from './views/dataModel';
import { EvidenceFileBrowser } from './views/EvidenceFiles';
import { detectGraph } from './views/graphModel';
import { FactoryRunList } from './views/RunList';
import { TerminalViewer } from './views/TerminalViewer';
import { useViewerLabels } from './views/viewerLabels';
import { curatedStepFor, keyFilesFor, keyFlags as curatedKeyFlags, presentEvent } from './views/storyModel.ts';
import { CapsuleChips, CapsuleLinksContext } from './cc/CapsuleChips';
import { capsuleApi, type CapsuleCard } from './cc/capsuleApi';
import { useCapsuleCopy } from './cc/copy';
import { capsuleHref, runHref, type FactoryEntry } from './cc/navigation';
import { useCapsuleResource } from './cc/useCapsuleResource';
import './factoryRuns.css';

const catalogRequest = (_key: string, signal: AbortSignal) => capsuleApi.catalog(signal, false);
const emptyCapsules: CapsuleCard[] = [];

const panels = [
  'overview',
  'iterations',
  'contract',
  'ontology',
  'graph',
  'capsules',
  'artifacts',
  'diffs',
  'tests',
  'measurements',
  'terminal',
  'report',
] as const;
type Panel = (typeof panels)[number];
// A curated replay tells one story: the stepper, its graph, its files and the report.
const curatedPanels: readonly Panel[] = ['overview', 'graph', 'artifacts', 'report'];
const storyVersion = (events: StoryEvent[]) => {
  const last = events[events.length - 1];
  return `${events.length}:${last?.id ?? ''}:${last?.summary ?? ''}`;
};

const patterns: Partial<Record<Panel, RegExp>> = {
  contract: /contract|task.*\.json/i,
  ontology: /ontology|dictionary|alignment|example\.md|\.(mmd|mermaid)$/i,
  capsules: /cc\.yaml|capsule|verif|digest|sha256/i,
  diffs: /(?:diff|patch|scor)/i,
  tests: /test|scor|verif|parity/i,
  measurements: /bench|measur|result|ledger|metrics/i,
  terminal: /session|\.log$|stdout|stderr|terminal/i,
  report: /report|summary.*\.md/i,
};
export function FactoryRunsPage({ entry }: { entry?: Extract<FactoryEntry, { view: 'factoryRuns' }> }) {
  const capsuleCatalog = useCapsuleResource('catalog', catalogRequest);
  return (
    <CapsuleLinksContext.Provider value={capsuleCatalog.data?.capsules ?? emptyCapsules}>
      <FactoryReplay key={JSON.stringify(entry)} entry={entry} />
    </CapsuleLinksContext.Provider>
  );
}

function FactoryReplay({ entry }: { entry?: Extract<FactoryEntry, { view: 'factoryRuns' }> }) {
  const { t } = useTranslation();
  const copy = useCapsuleCopy();
  const { label } = useViewerLabels();
  const [listing, setListing] = useState<RunList>({ runs: [], launch_templates: [], launch_enabled: false });
  const [selected, setSelected] = useState(entry?.run || '');
  const selectedRef = useRef(selected);
  useEffect(() => {
    selectedRef.current = selected;
  }, [selected]);
  const [loadedDetail, setDetail] = useState<RunDetail | null>(null);
  const detail = loadedDetail?.run.id === selected ? loadedDetail : null;
  const [panel, setPanel] = useState<Panel>(entry?.file ? 'artifacts' : 'overview');
  const [events, setEvents] = useState<StoryEvent[]>([]);
  const [position, setPosition] = useState(0);
  const [live, setLive] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const finalHeadlines = useFinalHeadlines(true, refreshVersion);
  const observedStory = useRef('');
  const [file, setFile] = useState<FileContent | null>(null);
  const [filePath, setFilePath] = useState(entry?.file || '');
  const [fileError, setFileError] = useState('');
  const [childSource, setChildSource] = useState<{ id: string; sha256?: string }>();
  const [expectedSha, setExpectedSha] = useState('');
  const [focusedDecisionId, setFocusedDecisionId] = useState<string>();
  const main = useRef<HTMLElement>(null);
  const [launchOpen, setLaunchOpen] = useState(false);
  const [session, setSession] = useState<SessionSnapshot | null>(null);
  const [sessionStale, setSessionStale] = useState(false);
  const [selectedNode, setSelectedNode] = useState<string>();
  const nodeEvidenceSection = useRef<HTMLDivElement>(null);
  const [runStatus, setRunStatus] = useState<{ id: string; run_state?: RunStateRecord; controls?: Controls }>();
  // Demo build: light theme only. The scoped dark palette had unreadable
  // text on several surfaces, so the page no longer follows the OS setting.
  const appearance = 'light';
  const refresh = useCallback(async () => {
    setCatalogLoading(true);
    try {
      const result = await factoryApi.list();
      const runs = [...result.runs].sort((a, b) => b.updated - a.updated);
      setListing({ ...result, runs });
      const firstDemo = runs.filter((run) => run.demo).sort((a, b) => (a.demo_order ?? 0) - (b.demo_order ?? 0))[0];
      setSelected((old) => old || runs.find((run) => run.featured)?.id || firstDemo?.id || runs[0]?.id || '');
    } catch (err) {
      setError(String(err));
    } finally {
      setCatalogLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    setLoading(true);
    setDetail(null);
    setFile(null);
    setSession(null);
    setSessionStale(false);
    setRunStatus(undefined);
    setError('');
    setPlaying(false);
    factoryApi
      .detail(selected)
      .then((result) => {
        if (active) {
          setDetail(result);
          observedStory.current = storyVersion(result.events);
          setEvents(result.events);
          // A curated replay is a stepper: open on step 1, not on the end.
          setPosition(result.curated ? Math.min(1, result.events.length) : result.events.length);
          if (result.run.featured && result.controls?.running && !result.curated) setLive(true);
          if (result.session) setSession(result.session);
        }
      })
      .catch((err) => {
        if (active) setError(String(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selected, refreshVersion]);
  const isLiveHome = detail?.run.id === selected && detail.run.kind === 'live' && !detail.run.read_only && !detail.curated;
  const controls = detail && runStatus?.id === selected ? runStatus.controls : detail?.controls;
  const status = detail && runStatus?.id === selected ? runStatus.run_state : detail?.run_state;
  // Operator actions change the graph: reload the run in place, keeping the open panel and selection.
  const reloadDetail = useCallback(async () => {
    const current = await factoryApi.detail(selected);
    if (selectedRef.current !== selected) return;
    observedStory.current = storyVersion(current.events);
    setDetail(current);
    setRunStatus({ id: selected, run_state: current.run_state, controls: current.controls });
    setEvents(current.events);
    setPosition(current.events.length);
    if (current.session) setSession(current.session);
  }, [selected]);
  const runKind = detail ? { kind: detail.run.kind, curated: Boolean(detail.curated) } : undefined;
  const operator = useMemo<NodeOperator | undefined>(() => {
    const kind = detail ? { kind: detail.run.kind, curated: Boolean(detail.curated) } : undefined;
    if (!detail || !kind || position !== events.length || !operatorEnabled(kind, controls)) return undefined;
    return {
      actions: (node: PlanNode) => nodeActions(kind, controls, node),
      run: async (nodeId, op, reason) => {
        await factoryApi.operator(selected, nodeId, op, reason);
        await reloadDetail();
      },
    };
  }, [detail, selected, position, events.length, controls, reloadDetail]);
  const planNodes = useMemo(
    () => (Array.isArray(detail?.graph?.nodes) ? (detail.graph.nodes as PlanNode[]) : []),
    [detail],
  );
  const fallbackStatus = detail && !detail.curated ? pauseStatement(planNodes, controls)?.text : undefined;
  const availableOperations = runKind && position === events.length ? runOperations(runKind, controls) : [];
  const runOperation = async (action: RunOperation, reason: string) => {
    const result = await factoryApi.runOperation(selected, action, reason);
    if (action === 'resume' && selectedRef.current === selected) setLive(true);
    if (action !== 'revise-preview') {
      void reloadDetail().catch((err) => setError(String(err)));
    }
    return result;
  };
  useEffect(() => {
    if (!isLiveHome) return;
    let stopped = false;
    let timer: number;
    const tick = async () => {
      try {
        const [snapshot, state] = await Promise.allSettled([factoryApi.session(selected), factoryApi.state(selected)]);
        if (!stopped) {
          if (snapshot.status === 'fulfilled') setSession(snapshot.value);
          setSessionStale(snapshot.status === 'rejected');
          if (state.status === 'fulfilled') setRunStatus({ id: selected, ...state.value });
        }
      } finally {
        if (!stopped) timer = window.setTimeout(tick, 3000);
      }
    };
    void tick();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [selected, isLiveHome]);
  useEffect(() => {
    if (!isLiveHome || !live) return;
    let stopped = false;
    let timer: number;
    const tick = async () => {
      try {
        const result = await factoryApi.story(selected, 0);
        if (stopped) return;
        const version = storyVersion(result.events);
        setEvents(result.events);
        setPosition(result.total);
        if (version !== observedStory.current) {
          const current = await factoryApi.detail(selected);
          if (!stopped) {
            observedStory.current = storyVersion(current.events);
            setDetail(current);
            setEvents(current.events);
            if (current.curated) {
              setPosition(Math.min(1, current.events.length));
              setSelectedNode(undefined);
              setPanel((value) => curatedPanels.includes(value) ? value : 'overview');
              setLive(false);
            } else {
              setPosition(current.events.length);
            }
          }
        }
      } catch (err) {
        if (!stopped) setError(String(err));
      }
      if (!stopped) timer = window.setTimeout(tick, 3000);
    };
    void tick();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [selected, live, isLiveHome]);
  useEffect(() => {
    if (!playing) return;
    if (position >= events.length) {
      setPlaying(false);
      return;
    }
    const timer = window.setTimeout(() => setPosition((old) => old + 1), 700);
    return () => window.clearTimeout(timer);
  }, [playing, position, events.length]);
  const matchingFiles = useMemo(() => {
    const files = detail?.files ?? [];
    return files.filter((item) => {
      if (panel === 'artifacts') return true;
      const kind = evidenceKind(item.path, item.display_path);
      if ((panel === 'diffs' && kind === 'diff') || (panel === 'terminal' && kind === 'log')) return true;
      return [item.path, item.display_path || ''].some((name) => patterns[panel]?.test(name));
    });
  }, [detail, panel]);
  const defaultFile =
    matchingFiles.find((item) => {
      const name = item.display_path || item.path;
      if (item.integrity === 'missing') return false;
      if (panel === 'contract') {
        return [item.path, ...(item.display_path?.split(' · ') ?? [])].some(
          (path) =>
            /^contracts\/(?:[^/]+\.json|[a-f0-9]{64})$/i.test(path) ||
            (/(?:^|[/:])[^/]*contract[^/]*\.json$/i.test(path) && path !== 'contract-origins.json'),
        );
      }
      if (panel === 'ontology') return /\.(?:mmd|mermaid)$/i.test(name);
      if (panel === 'diffs') return evidenceKind(item.path, item.display_path) === 'diff';
      if (panel === 'report') return /(?:^|[/:-])report\.(md|json)$/i.test(name);
      return false;
    }) ??
    (['ontology', 'report', 'diffs'].includes(panel)
      ? matchingFiles.find((item) => item.integrity !== 'missing')
      : undefined);
  const selectedFile = filePath ? detail?.files.find((item) => item.path === filePath) : defaultFile;
  const previewPath = selectedFile?.integrity !== 'missing' ? selectedFile?.path : undefined;
  const previewDigest = selectedFile?.sha256;

  useEffect(() => {
    setFile(null);
    setFileError('');
    if (!selected || !previewPath || panel === 'report') return;
    let active = true;
    factoryApi
      .file(selected, previewPath)
      .then((result) => {
        if (active) setFile(result);
      })
      .catch((err) => {
        if (active) setFileError(String(err));
      });
    return () => {
      active = false;
    };
  }, [selected, previewPath, previewDigest, panel, refreshVersion]);
  useEffect(() => {
    if (!detail || detail.run.id !== selected || !childSource) return;
    const source = detail.files.find((item) => item.artifact_ids?.includes(childSource.id));
    if (source) {
      setFilePath(source.path);
      setExpectedSha(childSource.sha256 || '');
    } else {
      setError(t('factoryRuns.iteration.unavailable', { id: childSource.id }));
    }
    setChildSource(undefined);
  }, [childSource, detail, selected, t]);
  useEffect(() => {
    if (main.current) main.current.scrollTop = 0;
  }, [panel, selected]);
  const visibleEvents = events.slice(0, position);
  const cursor = visibleEvents[visibleEvents.length - 1];
  const curatedStep = curatedStepFor(detail?.curated, cursor);
  const focusedNode = selectedNode ?? (curatedStep?.original_kind === 'revise' ? undefined : curatedStep?.node_id);
  useEffect(() => {
    if (selectedNode) nodeEvidenceSection.current?.scrollIntoView({ block: 'start' });
  }, [selectedNode]);
  const nodeLabels = useMemo(() => new Map(planNodes.flatMap((node) => {
    const id = evidenceText(node.node_id);
    const title = evidenceText(node.title) ?? id;
    return id && title ? [[id, title] as const] : [];
  })), [planNodes]);
  const stepKeyFiles = useMemo(() => keyFilesFor(curatedStep, detail?.files ?? []), [curatedStep, detail]);
  const keyFlagMap = useMemo(() => curatedKeyFlags(detail?.curated), [detail]);
  const shownCursor = cursor ? presentEvent(cursor) : undefined;
  const records = detail?.records || {};
  const graph = useMemo(
    () => (detail ? detectGraph(detail.graph, { contract: detail.contract, tasks: detail.records.tasks }) : null),
    [detail],
  );
  const eventRefs = useMemo(() => {
    const result = new Map<string, JsonRecord>();
    const data = detail?.records;
    for (const type of ['decisions', 'observations', 'evaluations', 'attempts']) {
      for (const row of data?.[type] ?? []) {
        const id = row.decision_id ?? row.obs_id ?? row.eval_id ?? row.attempt_id;
        if (typeof id === 'string') result.set(id, row);
      }
    }
    return result;
  }, [detail]);
  const capsuleEvent = (event: StoryEvent) => [
    event,
    eventRefs.get(event.id) ?? eventRefs.get(event.id.split(':')[0]),
    ['build', 'integrate'].includes(event.kind) ? records.tasks?.[0]?.component_cc : null,
  ];
  const selectPanel = (value: Panel, path = '', digest = '') => {
    setPanel(value);
    setExpectedSha(digest);
    if (path !== filePath) {
      setFilePath(path);
      setFile(null);
    }
  };
  const selectRun = (id: string) => {
    if (id === selected) return;
    window.history.replaceState(window.history.state, '', runHref(id));
    selectedRef.current = id;
    setSelected(id);
    setLive(false);
    setPanel('overview');
    setFocusedDecisionId(undefined);
    setSelectedNode(undefined);
    setChildSource(undefined);
    setExpectedSha('');
    setFilePath('');
  };
  const openIterationChild = (id: string, panel: Panel, sourceId?: string, sha256?: string) => {
    selectRun(id);
    setPanel(panel);
    setChildSource(sourceId ? { id: sourceId, sha256 } : undefined);
  };
  const openIterationSource = (source: EvidenceFile) => {
    const report = reportFiles([source]).length > 0;
    selectPanel(report ? 'report' : 'terminal', source.path, source.expected_sha256 || '');
  };
  const onLaunched = (id: string) => {
    setLaunchOpen(false);
    selectRun(id);
    setLive(true);
    void refresh();
  };
  const openEvidenceFile = (path: string) =>
    selectPanel(/(?:^|\/)report[^/]*\.md$/i.test(path) ? 'report' : 'artifacts', path);
  const nodeEvidence = detail && focusedNode ? (
    <div ref={nodeEvidenceSection} className="factory-node-evidence-slot">
      <NodeEvidence
        key={`${selected}:${focusedNode}`}
        runId={selected}
        nodeId={focusedNode}
        node={planNodes.find((node) => node.node_id === focusedNode)}
        checks={detail.node_checks?.[focusedNode]}
        files={detail.files}
        revision={detail}
        onOpenFile={openEvidenceFile}
        onClose={selectedNode ? () => setSelectedNode(undefined) : undefined}
      />
    </div>
  ) : undefined;
  const seek = (next: number) => {
    setPlaying(false);
    setSelectedNode(undefined);
    setPosition(next);
  };
  const headline = finalHeadlines &&
    <FinalHeadlines publication={finalHeadlines} onOpen={openIterationChild} />;
  let measurementSummary: ReactNode;
  // The campaign measurement panel reads the DeepSeek OPS ledger; other contract/2 runs use their lab reports.
  const deepseekCampaign = [detail?.contract.contract_id, detail?.records.tasks?.[0]?.contract_id].some(
    (id) => typeof id === 'string' && id.startsWith('star-deepseek-'),
  );
  if (
    detail &&
    (detail.contract.contract_id === 'star-deepseek-v1' ||
      detail.records.tasks?.[0]?.contract_id === 'star-deepseek-v1')
  ) {
    measurementSummary = <MeasurementSummary onOpenMeasurements={() => selectPanel('measurements')} />;
  }
  return (
    <div className="factory-runs-page" data-testid="factory-runs-page" data-appearance={appearance}>
      <aside className="factory-rail" data-testid="factory-runs-rail">
        <div className="factory-heading">
          <h1 data-testid="factory-runs-title">{t('factoryRuns.title')}</h1>
          <button
            className="factory-story-icon-button"
            type="button"
            data-testid="factory-runs-refresh"
            title={t('factoryRuns.refresh')}
            aria-label={t('factoryRuns.refresh')}
            disabled={catalogLoading || loading}
            onClick={() => {
              void refresh();
              setRefreshVersion((value) => value + 1);
            }}
          >
            <RefreshCw aria-hidden size={16} />
          </button>
        </div>
        <button
          className="factory-story-launch-button"
          type="button"
          data-testid="factory-runs-launch-button"
          disabled={catalogLoading || (!listing.launch_enabled && !listing.launch_templates.length)}
          onClick={() => setLaunchOpen(true)}
        >
          <Plus aria-hidden size={17} /> {t('factoryRuns.launch')}
        </button>
        {!catalogLoading && !listing.launch_enabled && !listing.launch_templates.length && (
          <p className="factory-muted" data-testid="factory-runs-launch-disabled">
            {t('factoryRuns.launchDisabled')}
          </p>
        )}
        <div aria-busy={catalogLoading}>
          {listing.runs.length > 0 || !catalogLoading ? (
            <FactoryRunList runs={listing.runs} selected={selected} onSelect={selectRun} />
          ) : null}
          {!listing.runs.length && catalogLoading && (
            <p className="factory-muted">{t('factoryRuns.story.loadingCatalog')}</p>
          )}
        </div>
      </aside>
      {launchOpen && (
        <LaunchSessionDialog
          enabled={listing.launch_enabled}
          templates={listing.launch_templates}
          onClose={() => setLaunchOpen(false)}
          onLaunched={onLaunched}
        />
      )}
      <section ref={main} className="factory-main" data-testid="factory-runs-main">
        {error && (
          <div className="factory-error" role="alert" data-testid="factory-runs-error">
            {error}
          </div>
        )}
        {loading && <p data-testid="factory-runs-loading">{t('factoryRuns.loading')}</p>}
        {detail && (
          <>
            <header className="factory-detail-header">
              <div>
                <p className="factory-story-kicker">
                  {t(detail.run.kind === 'bundle' ? 'factoryRuns.story.bundle' : 'factoryRuns.story.factoryHome')}
                </p>
                <h2 data-testid="factory-runs-run-title">{detail.run.name}</h2>
                <CapsuleChips value={[detail.stack, records.tasks?.map(({ component_cc, capability_cc }) => [component_cc, capability_cc])]} />
              </div>
              {isLiveHome && (
                <label className="factory-live">
                  <input
                    type="checkbox"
                    data-testid="factory-runs-live"
                    checked={live}
                    onChange={(event) => {
                      setLive(event.target.checked);
                      setPlaying(false);
                    }}
                  />
                  {t('factoryRuns.live')}
                </label>
              )}
            </header>
            <RunState
              key={selected}
              status={status}
              fallback={fallbackStatus}
              live={Boolean(isLiveHome && controls?.running)}
              historical={Boolean(runKind && !operatorEnabled(runKind, controls))}
              actions={availableOperations}
              resumeMode={controls?.resume_mode}
              onRun={runOperation}
            />
            {isLiveHome && (live || panel === 'overview' || panel === 'terminal') && (
              <LiveSession session={session} stale={sessionStale} />
            )}
            <section className="factory-replay" data-testid="factory-runs-replay">
              <div className="factory-replay-controls">
                <button
                  data-testid="factory-runs-play"
                  disabled={live || events.length === 0}
                  onClick={() => {
                    if (position === events.length) setPosition(detail.curated ? 1 : 0);
                    setSelectedNode(undefined);
                    setPlaying(!playing);
                  }}
                >
                  {t(playing ? 'factoryRuns.pause' : 'factoryRuns.play')}
                </button>
                <input
                  type="range"
                  data-testid="factory-runs-scrubber"
                  aria-label={t('factoryRuns.replay')}
                  min={detail.curated ? 1 : 0}
                  max={events.length}
                  value={position}
                  disabled={live}
                  onChange={(event) => seek(Number(event.target.value))}
                />
                <button
                  type="button"
                  data-testid="factory-runs-step-prev"
                  disabled={live || position <= (detail.curated ? 1 : 0)}
                  onClick={() => seek(position - 1)}
                >
                  ← Prev
                </button>
                <button
                  type="button"
                  data-testid="factory-runs-step-next"
                  disabled={live || position >= events.length}
                  onClick={() => seek(position + 1)}
                >
                  Next →
                </button>
                <output data-testid="factory-runs-position">
                  {detail.curated ? `Step ${position} of ${events.length}` : `${position} / ${events.length}`}
                </output>
              </div>
              <p data-testid="factory-runs-current-event">
                {cursor && shownCursor ? (
                  <>
                    <strong className="factory-current-title" data-testid="factory-runs-current-title" title={shownCursor.curated ? 'Presentation title' : undefined}>
                      {curatedStep ? `Step ${curatedStep.step} · ` : ''}{shownCursor.title}
                    </strong>{' '}
                    <small className="factory-original-kind factory-inline-kind" data-testid="factory-runs-current-kind" title="Original record kind">
                      {cursor.kind}
                    </small>
                    {!curatedStep && <span className="factory-current-summary"> · {cursor.summary}</span>}
                  </>
                ) : (
                  t('factoryRuns.start')
                )}
                {cursor && <CapsuleChips value={capsuleEvent(cursor)} />}
                {cursor && revisionEvent(cursor) !== undefined && (
                  <span className="factory-node-evidence-kind">Graph revision {revisionEvent(cursor)}</span>
                )}
                <ReplayLabel value={curatedStep?.replayed_from ?? cursor?.replayed_from} />
              </p>
            </section>
            <nav className="factory-tabs" data-testid="factory-runs-tabs" aria-label={t('factoryRuns.panels')}>
              {(detail.curated ? curatedPanels : panels).map((value) => (
                <button
                  key={value}
                  data-testid="factory-runs-panel-tab"
                  data-variant={value}
                  aria-pressed={panel === value}
                  onClick={() => selectPanel(value)}
                >
                  {value === 'artifacts' ? label('artifacts') : t(`factoryRuns.${value}`)}
                </button>
              ))}
            </nav>
            <section className="factory-evidence" data-testid="factory-runs-evidence">
              {(!detail.curated || detail.curated.native) && ['overview', 'graph', 'contract', 'capsules'].includes(panel) && (
                <CapsuleOverviewStrip
                  nodes={detail.cc_overview}
                  labels={nodeLabels}
                  selected={focusedNode}
                  onSelect={(id) => setSelectedNode((old) => old === id ? undefined : id)}
                />
              )}
              {['contract', 'capsules'].includes(panel) && nodeEvidence}
              {panel === 'overview' && (
                <RunOverview
                  detail={detail}
                  events={visibleEvents}
                  onOpen={selectPanel}
                  measurements={measurementSummary}
                  headline={measurementSummary || finalHeadlines?.run_id === selected ? headline : undefined}
                  eventCapsules={(event) => <CapsuleChips value={capsuleEvent(event)} />}
                  currentStep={curatedStep?.step}
                  onSeek={seek}
                  onOpenFile={openEvidenceFile}
                  nodeEvidence={nodeEvidence}
                />
              )}
              {panel === 'iterations' && (
                <Iterations
                  detail={detail}
                  runs={listing.runs}
                  onOpenSource={openIterationSource}
                  onOpenChild={openIterationChild}
                  onOpenDecision={(runId, decisionId) => {
                    selectRun(runId);
                    setPanel('iterations');
                    setFocusedDecisionId(decisionId);
                  }}
                  focusedDecisionId={focusedDecisionId}
                />
              )}
              {panel === 'report' && (
                <FactoryReport
                  runId={detail.run.id}
                  files={detail.files}
                  initialPath={filePath}
                  expectedSha={expectedSha}
                />
              )}
              {panel === 'graph' && (
                <DataViewer
                  key={selected}
                  name={t('factoryRuns.graph')}
                  value={detail.graph}
                  graph={graph}
                  replay={{
                    events,
                    position,
                    files: detail.files,
                    curated: detail.curated,
                    onOpenFile: (path: string) => selectPanel('artifacts', path),
                    checks: detail.node_checks,
                    operator,
                    onOpenNode: detail.cc_overview ? (id) => setSelectedNode(id) : undefined,
                  }}
                  initialMode="graph"
                />
              )}
              {panel === 'graph' && nodeEvidence}
              {panel === 'contract' && !selectedFile && !focusedNode && (
                <DataViewer
                  key={selected}
                  name={t('factoryRuns.contract')}
                  value={detail.contract}
                  initialMode="readable"
                />
              )}
              {panel === 'capsules' && !focusedNode && (
                <DataViewer key={selected} name={t('factoryRuns.capsules')} value={detail.stack} />
              )}
              {panel === 'tests' && (
                <DataViewer
                  key={selected}
                  name={t('factoryRuns.tests')}
                  value={records.evaluations || []}
                  initialMode="table"
                />
              )}
              {panel === 'terminal' && (
                <TerminalViewer
                  key={selected}
                  events={visibleEvents}
                  activeCursor={cursor?.cursor}
                  onSeek={
                    live
                      ? undefined
                      : (next) => {
                          setPlaying(false);
                          setPosition(next);
                        }
                  }
                />
              )}
              {panel === 'capsules' && (
                <div className="cc-actions" data-testid="factory-runs-run-capsules">
                  <CapsuleChips value={[detail.stack, records.tasks?.map(({ component_cc, capability_cc }) => [component_cc, capability_cc])]} />
                  <a href={capsuleHref()} data-testid="factory-runs-capsule-browse">{copy('catalog')} →</a>
                </div>
              )}
              {panel === 'measurements' && isContractV2(detail.contract) && (
                <LabResults
                  contract={detail.contract}
                  observations={records.observations}
                  files={detail.files}
                  onOpenFile={(path) => selectPanel('artifacts', path)}
                />
              )}
              {panel === 'measurements' && (!isContractV2(detail.contract) || deepseekCampaign) && (
                <Measurements
                  detail={detail}
                  headline={headline}
                  benchmarkRunId={listing.runs.find((run) =>
                    run.kind === 'live' && run.task_id === 'spark-direct-benchmarks-20261120')?.id}
                  onOpenReport={(runId, reportId, sha256) => openIterationChild(runId, 'report', reportId, sha256)}
                />
              )}
              {!['overview','graph','report','iterations','measurements'].includes(panel) && (
                <EvidenceFileBrowser
                  key={`${selected}:${panel}`}
                  files={matchingFiles}
                  runFiles={detail.files}
                  selectedFile={selectedFile && expectedSha && selectedFile.sha256 !== expectedSha ? { ...selectedFile, expected_sha256: expectedSha, integrity: 'mismatch' } : selectedFile}
                  content={file && expectedSha && file.sha256 !== expectedSha ? { ...file, expected_sha256: expectedSha, integrity: 'mismatch' } : file}
                  error={fileError}
                  onSelect={(path) => { setExpectedSha(''); setFilePath(path); }}
                  keyFiles={stepKeyFiles}
                  keyFlags={keyFlagMap}
                />
              )}
            </section>
          </>
        )}
      </section>
    </div>
  );
}
