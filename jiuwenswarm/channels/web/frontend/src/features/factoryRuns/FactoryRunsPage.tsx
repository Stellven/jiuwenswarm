import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Moon, Plus, RefreshCw, Sun } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  factoryApi,
  type EvidenceFile,
  type FileContent,
  type JsonRecord,
  type RunDetail,
  type RunList,
  type SessionSnapshot,
  type StoryEvent,
} from './api';
import { Measurements, MeasurementSummary } from './Measurements';
import { RunOverview } from './RunOverview';
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
  const [appearance, setAppearance] = useState<'light' | 'dark'>(() =>
    window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
  );
  const refresh = useCallback(async () => {
    setCatalogLoading(true);
    try {
      const result = await factoryApi.list();
      const runs = [...result.runs].sort((a, b) => b.updated - a.updated);
      setListing({ ...result, runs });
      setSelected((old) => old || runs[0]?.id || '');
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
    setError('');
    setPlaying(false);
    factoryApi
      .detail(selected)
      .then((result) => {
        if (active) {
          setDetail(result);
          observedStory.current = storyVersion(result.events);
          setEvents(result.events);
          setPosition(result.events.length);
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
  const isLiveHome = detail?.run.id === selected && detail.run.kind === 'live';
  useEffect(() => {
    if (!isLiveHome) return;
    let stopped = false;
    let timer: number;
    const tick = async () => {
      try {
        const update = await factoryApi.session(selected);
        if (!stopped) {
          setSession(update);
          setSessionStale(false);
        }
      } catch {
        if (!stopped) setSessionStale(true);
      }
      if (!stopped) timer = window.setTimeout(tick, 3000);
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
            setPosition(current.events.length);
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
    setSelected(id);
    setLive(false);
    setPanel('overview');
    setFocusedDecisionId(undefined);
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
  const changeAppearance = () => setAppearance((mode) => (mode === 'dark' ? 'light' : 'dark'));
  let measurementSummary: ReactNode;
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
        <button
          type="button"
          className="factory-story-appearance-button"
          onClick={changeAppearance}
          data-testid="factory-runs-appearance"
        >
          <Moon className="factory-story-moon" aria-hidden size={15} />
          <Sun className="factory-story-sun" aria-hidden size={15} />
          {t(appearance === 'dark' ? 'factoryRuns.story.lightMode' : 'factoryRuns.story.darkMode')}
        </button>
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
            {isLiveHome && (live || panel === 'overview' || panel === 'terminal') && (
              <LiveSession session={session} stale={sessionStale} />
            )}
            <section className="factory-replay" data-testid="factory-runs-replay">
              <div className="factory-replay-controls">
                <button
                  data-testid="factory-runs-play"
                  disabled={live || events.length === 0}
                  onClick={() => {
                    if (position === events.length) setPosition(0);
                    setPlaying(!playing);
                  }}
                >
                  {t(playing ? 'factoryRuns.pause' : 'factoryRuns.play')}
                </button>
                <input
                  type="range"
                  data-testid="factory-runs-scrubber"
                  aria-label={t('factoryRuns.replay')}
                  min={0}
                  max={events.length}
                  value={position}
                  disabled={live}
                  onChange={(event) => {
                    setPlaying(false);
                    setPosition(Number(event.target.value));
                  }}
                />
                <output data-testid="factory-runs-position">
                  {position} / {events.length}
                </output>
              </div>
              <p data-testid="factory-runs-current-event">
                {cursor ? `${cursor.kind} · ${cursor.summary}` : t('factoryRuns.start')}
                {cursor && <CapsuleChips value={capsuleEvent(cursor)} />}
              </p>
            </section>
            <nav className="factory-tabs" data-testid="factory-runs-tabs" aria-label={t('factoryRuns.panels')}>
              {panels.map((value) => (
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
              {panel === 'overview' && (
                <RunOverview
                  detail={detail}
                  events={visibleEvents}
                  onOpen={selectPanel}
                  measurements={measurementSummary}
                  eventCapsules={(event) => <CapsuleChips value={capsuleEvent(event)} />}
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
                  replay={{ events, position }}
                  initialMode="graph"
                />
              )}
              {panel === 'contract' && !selectedFile && (
                <DataViewer
                  key={selected}
                  name={t('factoryRuns.contract')}
                  value={detail.contract}
                  initialMode="readable"
                />
              )}
              {panel === 'capsules' && (
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
              {panel === 'measurements' && <Measurements />}
              {!['overview','graph','report','iterations','measurements'].includes(panel) && (
                <EvidenceFileBrowser
                  key={`${selected}:${panel}`}
                  files={matchingFiles}
                  runFiles={detail.files}
                  selectedFile={selectedFile && expectedSha && selectedFile.sha256 !== expectedSha ? { ...selectedFile, expected_sha256: expectedSha, integrity: 'mismatch' } : selectedFile}
                  content={file && expectedSha && file.sha256 !== expectedSha ? { ...file, expected_sha256: expectedSha, integrity: 'mismatch' } : file}
                  error={fileError}
                  onSelect={(path) => { setExpectedSha(''); setFilePath(path); }}
                />
              )}
            </section>
          </>
        )}
      </section>
    </div>
  );
}
