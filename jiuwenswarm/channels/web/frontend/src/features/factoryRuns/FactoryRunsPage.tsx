import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Archive, CircleDot, Moon, Plus, RefreshCw, Sun } from 'lucide-react';
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
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Measurements, MeasurementSummary } from './Measurements';
import { RunOverview } from './RunOverview';
import { Iterations } from './Iterations';
import { FactoryReport } from './FactoryReport';
import { FactoryStructuredReport } from './FactoryStructuredReport';
import { reportFiles } from './reportModel';
import { LiveSession } from './LiveSession';
import { LaunchSessionDialog } from './LaunchSessionDialog';
import './factoryRuns.css';

const panels = [
  'overview',
  'iterations',
  'contract',
  'ontology',
  'graph',
  'capsules',
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
  ontology: /ontology|dictionary|alignment|example\.md/i,
  capsules: /cc\.yaml|capsule|verif|digest|sha256/i,
  diffs: /\.diff$|\.patch$|scor/i,
  tests: /test|scor|verif|parity/i,
  measurements: /bench|measur|result|ledger|metrics/i,
  terminal: /session|\.log$|stdout|stderr|terminal/i,
};
function JsonView({ value }: { value: unknown }) {
  return (
    <pre className="factory-json" data-testid="factory-runs-json">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
function Digest({ file }: { file: EvidenceFile }) {
  const { t } = useTranslation();
  return (
    <span
      className="factory-digest"
      data-integrity={file.integrity}
      data-testid="factory-runs-digest"
      title={`${file.sha256}\n${file.expected_sha256 || ''}`}
    >
      {t(`factoryRuns.${file.integrity}`)} · {file.sha256?.slice(0, 12)}
    </span>
  );
}
function Graph({ value }: { value: JsonRecord }) {
  const nodes = Array.isArray(value.nodes) ? (value.nodes as JsonRecord[]) : [];
  return (
    <div className="factory-graph" data-testid="factory-runs-graph">
      {nodes.map((node, index) => (
        <article
          key={String(node.node_id || index)}
          data-testid="factory-runs-graph-node"
          data-variant={String(node.node_id || index)}
        >
          <strong>{String(node.title || node.label || node.node_id)}</strong>
          <small>{String(node.status || node.kind || '')}</small>
          <JsonView value={node} />
        </article>
      ))}
      {nodes.length === 0 && <JsonView value={value} />}
    </div>
  );
}

export function FactoryRunsPage() {
  const { t } = useTranslation();
  const [listing, setListing] = useState<RunList>({ runs: [], launch_templates: [], launch_enabled: false });
  const [selected, setSelected] = useState('');
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [panel, setPanel] = useState<Panel>('overview');
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
  const [filePath, setFilePath] = useState('');
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
  useEffect(() => {
    setFile(null);
    if (!selected || !filePath || panel === 'report') return;
    let active = true;
    factoryApi
      .file(selected, filePath)
      .then((result) => {
        if (active) setFile(result);
      })
      .catch((err) => {
        if (active) setError(String(err));
      });
    return () => {
      active = false;
    };
  }, [selected, filePath, panel, refreshVersion]);
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
  const matchingFiles = useMemo(
    () => detail?.files.filter((item) => patterns[panel]?.test(item.display_path || item.path)) || [],
    [detail, panel],
  );
  const visibleEvents = events.slice(0, position);
  const cursor = visibleEvents[visibleEvents.length - 1];
  const records = detail?.records || {};
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
    setSelected(id);
    setLive(false);
    setPanel('overview');
    setFocusedDecisionId(undefined);
    setChildSource(undefined);
    setExpectedSha('');
    setFilePath('');
    setFile(null);
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
        <div className="factory-run-list" data-testid="factory-runs-list" aria-busy={catalogLoading}>
          {listing.runs.map((run) => (
            <button
              key={run.id}
              className="factory-run"
              data-testid="factory-runs-run"
              data-variant={run.id}
              aria-pressed={run.id === selected}
              onClick={() => selectRun(run.id)}
            >
              <span>
                {run.kind === 'bundle' ? <Archive aria-hidden size={13} /> : <CircleDot aria-hidden size={13} />}
                {t(run.kind === 'bundle' ? 'factoryRuns.story.bundle' : 'factoryRuns.story.factoryHome')}
              </span>
              <strong>{run.name}</strong>
              <small>
                <time dateTime={new Date(run.updated * 1000).toISOString()}>
                  {new Date(run.updated * 1000).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}
                </time>
              </small>
            </button>
          ))}
          {!listing.runs.length && !catalogLoading && !error && (
            <p data-testid="factory-runs-empty">{t('factoryRuns.empty')}</p>
          )}
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
            {isLiveHome && <LiveSession session={session} stale={sessionStale} />}
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
                  {t(`factoryRuns.${value}`)}
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
              {panel === 'graph' && <Graph value={detail.graph} />}
              {panel === 'contract' && (
                <>
                  <h3 data-testid="factory-runs-contract-title">{t('factoryRuns.contract')}</h3>
                  <dl className="factory-contract-summary" data-testid="factory-runs-contract-summary">
                    {Object.entries(detail.contract)
                      .filter(([, value]) => ['string', 'number', 'boolean'].includes(typeof value))
                      .map(([key, value]) => (
                        <div key={key}>
                          <dt>{key.replaceAll('_', ' ')}</dt>
                          <dd>{String(value)}</dd>
                        </div>
                      ))}
                  </dl>
                  <JsonView value={detail.contract} />
                </>
              )}
              {panel === 'capsules' && <JsonView value={detail.stack} />}
              {panel === 'tests' && <JsonView value={records.evaluations || []} />}
              {panel === 'measurements' && <Measurements />}
              {panel !== 'overview' &&
                panel !== 'graph' &&
                panel !== 'report' &&
                panel !== 'iterations' &&
                panel !== 'measurements' && (
                  <div className="factory-file-grid">
                    <div className="factory-files" data-testid="factory-runs-files">
                      {matchingFiles.map((item) => (
                        <button
                          key={item.path}
                          data-testid="factory-runs-file"
                          data-variant={item.path}
                          aria-pressed={filePath === item.path}
                          onClick={() => {
                            setExpectedSha('');
                            setFilePath(item.path);
                          }}
                        >
                          <span>{item.display_path || item.path}</span>
                          <Digest file={item} />
                        </button>
                      ))}
                      {!matchingFiles.length && (
                        <p data-testid="factory-runs-no-evidence">{t('factoryRuns.noEvidence')}</p>
                      )}
                    </div>
                    <div className="factory-file-content" data-testid="factory-runs-file-content">
                      {file && (
                        <>
                          <h3>{file.display_path || file.path}</h3>
                          <Digest
                            file={
                              expectedSha && file.sha256 !== expectedSha
                                ? { ...file, integrity: 'mismatch', expected_sha256: expectedSha }
                                : file
                            }
                          />
                          {file.truncated && <p data-testid="factory-runs-truncated">{t('factoryRuns.truncated')}</p>}
                          {/\.md(?:$| ·)/i.test(file.display_path || file.path) && panel !== 'diffs' ? (
                            <div className="markdown-body" data-testid="factory-runs-markdown">
                              <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                skipHtml
                                components={{
                                  img: ({ alt }) => <span>{alt}</span>,
                                  a: ({ children }) => <span>{children}</span>,
                                }}
                              >
                                {file.content}
                              </ReactMarkdown>
                            </div>
                          ) : /\.json(?:$| ·)/i.test(file.display_path || file.path) ? (
                            <FactoryStructuredReport content={file.content} />
                          ) : (
                            <pre>{file.content}</pre>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                )}
            </section>
          </>
        )}
      </section>
    </div>
  );
}
