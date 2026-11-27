import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Plus, RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  factoryApi,
  request,
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
import { deliveryHeadline, type Benchmark, type Delivery } from './engineBenchModel';
import { FinalHeadlines, useFinalHeadlines } from './FinalHeadlines';
import { RunOverview } from './RunOverview';
import { LabResults } from './LabResults';
import { isContractV2 } from './labModel';
import { nodeActions, operatorEnabled, pauseStatement, type Controls, type NodeOperator, type PlanNode } from './views/checkModel';
import { CapsuleOverviewStrip, NodeEvidence, ReplayLabel } from './views/NodeEvidence';
import { RunState } from './views/RunState';
import { artifactReplayOrigins, checkArtifactLabels, evidenceText, labelCheckArtifact, nodeReplayOrigins, revisionEvent, runOperations } from './views/nodeEvidenceModel';
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
import { contractDemoRuns } from './views/runListModel';
import { ReplayContractPanel, ReplayEventsPanel, ReplayNodeContractsPanel } from './FactoryReplayEvidence';
import { TerminalViewer } from './views/TerminalViewer';
import { useViewerLabels } from './views/viewerLabels';
import { curatedStepFor, keyFilesFor, keyFlags as curatedKeyFlags, presentEvent } from './views/storyModel.ts';
import { CapsuleChips, CapsuleLinksContext } from './cc/CapsuleChips';
import { demoContractCapsuleIds } from './cc/inferenceCapsuleCopy';
import { capsuleApi, type CapsuleCard } from './cc/capsuleApi';
import { useCapsuleCopy } from './cc/copy';
import { capsuleHref, runFilesHref, runHref, type FactoryEntry } from './cc/navigation';
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
const contractReplayTabs = [
  ['report', 'Lab report'],
  ['overview', 'Story'],
  ['graph', 'Task graph'],
  ['contract', 'Contract'],
  ['node-contracts', 'Node contracts'],
  ['events', 'Events'],
  ['artifacts', 'Files and diffs'],
] as const;
type Panel = (typeof panels)[number] | (typeof contractReplayTabs)[number][0];
// A curated replay tells one story: the stepper, its graph, its files and the report.
const curatedPanels: readonly Panel[] = ['overview', 'graph', 'artifacts', 'report'];
// A task-graph run (node contracts, scheduler, capsule checks) has no ontology or iteration records.
const graphRunPanels: readonly Panel[] = panels.filter((value) => !['iterations', 'ontology', 'tests'].includes(value));
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
type FactoryRunsProps = { entry?: Extract<FactoryEntry, { view: 'factoryRuns' }>; engineViewer?: boolean };

export function FactoryRunsPage({ entry, engineViewer = false }: FactoryRunsProps) {
  const capsuleCatalog = useCapsuleResource('catalog', catalogRequest);
  return (
    <CapsuleLinksContext.Provider value={capsuleCatalog.data?.capsules ?? emptyCapsules}>
      <FactoryReplay key={JSON.stringify(entry)} entry={entry} engineViewer={engineViewer} />
    </CapsuleLinksContext.Provider>
  );
}

function FactoryReplay({ entry, engineViewer }: FactoryRunsProps) {
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
  const [panel, setPanel] = useState<Panel>(entry?.file ? 'artifacts' : entry?.panel ?? (entry?.node ? 'capsules' : 'overview'));
  const [events, setEvents] = useState<StoryEvent[]>([]);
  const [position, setPosition] = useState(0);
  const [live, setLive] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const finalHeadlines = useFinalHeadlines(!engineViewer, refreshVersion);
  const observedStory = useRef('');
  const [file, setFile] = useState<FileContent | null>(null);
  const [filePath, setFilePath] = useState(entry?.file || '');
  const [fileError, setFileError] = useState('');
  const [diffsOnly, setDiffsOnly] = useState(false);
  const [childSource, setChildSource] = useState<{ id: string; sha256?: string }>();
  const [expectedSha, setExpectedSha] = useState('');
  const [focusedDecisionId, setFocusedDecisionId] = useState<string>();
  const main = useRef<HTMLElement>(null);
  const [launchOpen, setLaunchOpen] = useState(false);
  const [session, setSession] = useState<SessionSnapshot | null>(null);
  const [sessionStale, setSessionStale] = useState(false);
  const [selectedNode, setSelectedNode] = useState(entry?.node);
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
      setSelected((old) => old || contractDemoRuns(runs)[0]?.id || (engineViewer ? firstDemo?.id : undefined) || runs.find((run) => run.featured)?.id || firstDemo?.id || runs[0]?.id || '');
    } catch (err) {
      setError(String(err));
    } finally {
      setCatalogLoading(false);
    }
  }, [engineViewer]);
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
  const presentation = detail?.curated?.presentation_header;
  const contractCapsuleIds = useMemo(() => {
    const contractId = detail?.contract.contract_id;
    if (!presentation || typeof contractId !== 'string') return undefined;
    const selected = demoContractCapsuleIds.get(contractId);
    if (!selected) return undefined;
    const recorded = new Set(Object.values(detail?.cc_overview ?? {}).flat().map(({ id }) => id));
    return selected.filter((id) => recorded.has(id));
  }, [detail, presentation]);
  const r8Demo = !presentation && engineViewer && detail?.run.task_id === 'muse-2bit-demo-r8';
  const [delivery, setDelivery] = useState<Delivery>();
  useEffect(() => {
    if (!r8Demo) return;
    const controller = new AbortController();
    request<Benchmark>('/engine-bench', { signal: controller.signal })
      .then((result) => {
        if (!controller.signal.aborted) setDelivery(result.delivery);
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [r8Demo]);
  const demoHeadline = r8Demo ? deliveryHeadline(delivery) : '';
  const terminalDecision = r8Demo && delivery?.decision?.kind === 'report_inconclusive' ? delivery.decision : undefined;
  const isTerminalDemo = r8Demo && (status?.outcome === 'report_inconclusive' || terminalDecision);
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
    if (engineViewer || !detail || !kind || position !== events.length || !operatorEnabled(kind, controls)) return undefined;
    return {
      actions: (node: PlanNode) => nodeActions(kind, controls, node),
      run: async (nodeId, op, reason) => {
        await factoryApi.operator(selected, nodeId, op, reason);
        await reloadDetail();
      },
    };
  }, [engineViewer, detail, selected, position, events.length, controls, reloadDetail]);
  const planNodes = useMemo(
    () => (Array.isArray(detail?.graph?.nodes) ? (detail.graph.nodes as PlanNode[]) : []),
    [detail],
  );
  const fallbackStatus = detail && !detail.curated ? pauseStatement(planNodes, controls)?.text : undefined;
  const availableOperations = !engineViewer && runKind && position === events.length ? runOperations(runKind, controls) : [];
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
  const checkNames = useMemo(() => checkArtifactLabels(detail?.records.observations ?? []), [detail]);
  const matchingFiles = useMemo(() => {
    const files = (detail?.files ?? []).map((item) => labelCheckArtifact(item, checkNames));
    return files.filter((item) => {
      const kind = evidenceKind(item.path, item.display_path);
      if (panel === 'artifacts') return !presentation || !diffsOnly || kind === 'diff';
      if ((panel === 'diffs' && kind === 'diff') || (panel === 'terminal' && kind === 'log')) return true;
      return [item.path, item.display_path || ''].some((name) => patterns[panel]?.test(name));
    });
  }, [detail, panel, checkNames, presentation, diffsOnly]);
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
  const replayByNode = useMemo(() => nodeReplayOrigins(events, position), [events, position]);
  const replayByArtifact = useMemo(() => artifactReplayOrigins(detail?.records.observations ?? []), [detail]);
  const cursor = visibleEvents[visibleEvents.length - 1];
  const curatedStep = curatedStepFor(detail?.curated, cursor);
  const focusedNode = selectedNode ?? (curatedStep?.original_kind === 'revise' ? undefined : curatedStep?.node_id);
  useEffect(() => {
    if (selectedNode) nodeEvidenceSection.current?.scrollIntoView({ block: 'start' });
  }, [selectedNode]);
  const nodeLabels = useMemo(() => new Map(planNodes.flatMap((node) => {
    const id = evidenceText(node.node_id);
    const title = (id ? detail?.curated?.node_presentation?.[id]?.title : undefined) ?? evidenceText(node.title) ?? id;
    return id && title ? [[id, title] as const] : [];
  })), [planNodes, detail?.curated?.node_presentation]);
  const stepKeyFiles = useMemo(() => keyFilesFor(curatedStep, detail?.files ?? []), [curatedStep, detail]);
  const keyFlagMap = useMemo(() => curatedKeyFlags(detail?.curated), [detail]);
  const shownCursor = cursor ? presentEvent(cursor) : undefined;
  const records = detail?.records || {};
  const graph = useMemo(
    () => (detail ? detectGraph(detail.graph, {
      contract: detail.contract, tasks: detail.records.tasks, nodePresentation: detail.curated?.node_presentation,
    }) : null),
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
    setDiffsOnly(false);
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
    setDiffsOnly(false);
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
  const correctionCursor = cursor && (detail?.curated || position < events.length)
    ? { created: cursor.created, id: (curatedStep?.correction ?? cursor.correction)?.id }
    : undefined;
  const nodeEvidence = detail && focusedNode ? (
    <div ref={nodeEvidenceSection} className="factory-node-evidence-slot">
      <NodeEvidence
        key={`${selected}:${focusedNode}`}
        runId={selected}
        nodeId={focusedNode}
        node={planNodes.find((node) => node.node_id === focusedNode)}
        checks={detail.node_checks?.[focusedNode]}
        presentation={detail.curated?.node_presentation?.[focusedNode]}
        files={detail.files}
        revision={detail}
        correctionCursor={correctionCursor}
        r8VerifierHelp={detail.contract.contract_id === 'muse-2bit-demo-r8'}
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
  const nativeTabs = detail?.curated && (!engineViewer || !detail.curated.native)
    ? curatedPanels : engineViewer || detail?.cc_overview ? graphRunPanels : panels;
  const tabItems = presentation ? contractReplayTabs : nativeTabs.map((value) => [
    value, value === 'artifacts' ? label('artifacts') : t(`factoryRuns.${value}`),
  ] as const);
  const navigation = detail && (
    <nav className="factory-tabs" data-testid="factory-runs-tabs" aria-label={t('factoryRuns.panels')}>
      {tabItems.map(([value, title]) => (
        <button
          key={value}
          data-testid="factory-runs-panel-tab"
          data-variant={value}
          aria-pressed={panel === value}
          onClick={() => selectPanel(value)}
        >
          {title}
        </button>
      ))}
    </nav>
  );
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
        {(!engineViewer || listing.runs.some((run) => run.contract_demo)) && <button
          className="factory-story-launch-button"
          type="button"
          data-testid="factory-runs-launch-button"
          disabled={engineViewer || catalogLoading || (!listing.launch_enabled && !listing.launch_templates.length)}
          onClick={() => setLaunchOpen(true)}
        >
          <Plus aria-hidden size={17} /> {t('factoryRuns.launch')}
        </button>}
        {!engineViewer && !catalogLoading && !listing.launch_enabled && !listing.launch_templates.length && (
          <p className="factory-muted" data-testid="factory-runs-launch-disabled">
            {t('factoryRuns.launchDisabled')}
          </p>
        )}
        <div aria-busy={catalogLoading}>
          {listing.runs.length > 0 || !catalogLoading ? (
            <FactoryRunList runs={listing.runs} selected={selected} onSelect={selectRun} engineViewer={engineViewer} />
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
                {presentation && (
                  <p className="factory-detail-subtitle" data-testid="factory-runs-run-objective">{presentation.objective}</p>
                )}
                {!presentation && typeof detail.contract.title === 'string' && detail.cc_overview && (
                  <p className="factory-detail-subtitle" data-testid="factory-runs-run-subtitle">{detail.contract.title}</p>
                )}
                {presentation ? <CapsuleChips
                  capsuleIds={contractCapsuleIds}
                  value={records.tasks?.map(({ component_cc, capability_cc }) => [component_cc, capability_cc])}
                /> : <CapsuleChips
                  value={detail.cc_overview
                    ? [...new Set(Object.values(detail.cc_overview).flat().map((cc) => cc.id))]
                    : [detail.stack, records.tasks?.map(({ component_cc, capability_cc }) => [component_cc, capability_cc])]}
                />}
              </div>
              {isLiveHome && !isTerminalDemo && (
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
            {presentation ? (
              <section className="factory-run-state factory-contract-result" data-testid="factory-runs-state" data-variant="finished">
                <div>
                  <strong data-testid="factory-runs-state-label">{presentation.outcome}</strong>
                  {presentation.image_id && (
                    <span className="factory-contract-image" data-testid="factory-runs-engine-image">
                      Engine image <code>{presentation.image_id}</code>
                    </span>
                  )}
                </div>
                <button type="button" data-testid="factory-runs-attached-report" onClick={() => selectPanel('report')}>
                  Open lab report
                </button>
              </section>
            ) : demoHeadline || isTerminalDemo ? (
              <section className="factory-run-state" data-testid="factory-runs-state" data-variant="finished">
                <strong data-testid="factory-runs-state-label">{demoHeadline || 'Finished'}</strong>
              </section>
            ) : (
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
            )}
            {!presentation && detail.contract.contract_id === 'muse-2bit-demo-r8' && (
              <p className="factory-correction-explanation" data-testid="factory-runs-correction-explanation">
                Agent help with the verifier role included monitoring and specific-fix notes. Advisory findings remain in the evidence.
              </p>
            )}
            {isLiveHome && !isTerminalDemo && (live || panel === 'overview' || panel === 'terminal') && (
              <LiveSession session={session} stale={sessionStale} engineViewer={engineViewer} />
            )}
            {presentation && navigation}
            {(presentation ? ['overview', 'graph'].includes(panel) : !isTerminalDemo || (detail.curated && !detail.curated.native)) && <section className="factory-replay" data-testid="factory-runs-replay">
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
            </section>}
            {!presentation && navigation}
            <section className="factory-evidence" data-testid="factory-runs-evidence">
              {!presentation && (!detail.curated || detail.curated.native) && ['contract', 'capsules'].includes(panel) && (
                <CapsuleOverviewStrip
                  nodes={detail.cc_overview}
                  labels={nodeLabels}
                  replayByNode={replayByNode}
                  corrections={detail.correction_overview}
                  selected={focusedNode}
                  onSelect={(id) => setSelectedNode((old) => old === id ? undefined : id)}
                />
              )}
              {!presentation && ['contract', 'capsules'].includes(panel) && nodeEvidence}
              {presentation && panel === 'contract' && (
                <ReplayContractPanel detail={detail} onOpenFile={(item) => selectPanel('artifacts', item.path)} />
              )}
              {presentation && panel === 'node-contracts' && (
                <ReplayNodeContractsPanel
                  detail={detail}
                  selectedNode={selectedNode}
                  onSelectNode={setSelectedNode}
                  onOpenFile={openEvidenceFile}
                />
              )}
              {presentation && panel === 'events' && <ReplayEventsPanel detail={detail} />}
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
              {panel === 'overview' && (!detail.curated || detail.curated.native) && (
                <CapsuleOverviewStrip
                  nodes={detail.cc_overview}
                  labels={nodeLabels}
                  replayByNode={replayByNode}
                  corrections={detail.correction_overview}
                  selected={focusedNode}
                  onSelect={(id) => setSelectedNode((old) => old === id ? undefined : id)}
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
                  onOpenFile={(path) => selectPanel('artifacts', path)}
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
                    replayByNode,
                    onOpenNode: detail.cc_overview ? (id) => setSelectedNode(id) : undefined,
                  }}
                  initialMode="graph"
                />
              )}
              {panel === 'graph' && nodeEvidence}
              {!presentation && panel === 'contract' && !selectedFile && !focusedNode && (
                <DataViewer
                  key={selected}
                  name={t('factoryRuns.contract')}
                  value={detail.contract}
                  initialMode="readable"
                />
              )}
              {panel === 'capsules' && !focusedNode && !detail.cc_overview && (
                <DataViewer key={selected} name={t('factoryRuns.capsules')} value={detail.stack} />
              )}
              {!presentation && ['capsules', 'contract'].includes(panel) && !focusedNode && detail.cc_overview && (
                <p className="factory-pick-node" data-testid="factory-runs-pick-node">
                  {panel === 'capsules'
                    ? 'Pick a node above to see each capsule it used: what the capsule gave the worker, the diff, pack, plan or image it produced, and its checks.'
                    : 'Pick a node above to compare its preliminary and final node contract, the planner briefing and the scheduler rationale.'}
                </p>
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
                  events={engineViewer ? detail.engine_log ?? [] : visibleEvents}
                  activeCursor={engineViewer ? undefined : cursor?.cursor}
                  onSeek={
                    live || engineViewer
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
              {panel === 'artifacts' && (detail.run.original_run_id || detail.run.demo_replay_id) && (
                <div className="factory-original-files" data-testid="factory-runs-source-files">
                  {detail.run.original_run_id ? (
                    <a href={runFilesHref(detail.run.original_run_id)} data-testid="factory-runs-open-original-files">
                      Browse all original run files →
                    </a>
                  ) : detail.run.demo_replay_id && (
                    <a href={runFilesHref(detail.run.demo_replay_id)} data-testid="factory-runs-back-demo-files">
                      ← Return to demo files
                    </a>
                  )}
                </div>
              )}
              {presentation && panel === 'artifacts' && (
                <div className="factory-tabs" data-testid="factory-runs-file-filters" aria-label="File types">
                  <button type="button" aria-pressed={!diffsOnly} onClick={() => setDiffsOnly(false)}>All files</button>
                  <button type="button" aria-pressed={diffsOnly} onClick={() => setDiffsOnly(true)}>Diffs</button>
                </div>
              )}
              {!(presentation && panel === 'contract') &&
                !['overview', 'graph', 'report', 'iterations', 'measurements', 'node-contracts', 'events'].includes(panel) && !(engineViewer && panel === 'terminal') && (
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
                  replayByArtifact={replayByArtifact}
                />
              )}
            </section>
          </>
        )}
      </section>
    </div>
  );
}
