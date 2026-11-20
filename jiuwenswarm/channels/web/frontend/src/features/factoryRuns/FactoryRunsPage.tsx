import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { factoryApi, type FileContent, type RunDetail, type RunList, type StoryEvent } from './api';
import { Measurements } from './Measurements';
import { DataViewer } from './views/DataViewer';
import { evidenceKind } from './views/dataModel';
import { EvidenceFileBrowser } from './views/EvidenceFiles';
import { detectGraph } from './views/graphModel';
import { FactoryRunList } from './views/RunList';
import { TerminalViewer } from './views/TerminalViewer';
import { useViewerLabels } from './views/viewerLabels';
import './factoryRuns.css';

const panels = [
  'overview',
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
const patterns: Partial<Record<Panel, RegExp>> = {
  contract: /contract|task.*\.json/i,
  ontology: /ontology|dictionary|alignment|example\.md|\.(mmd|mermaid)$/i,
  capsules: /cc\.yaml|capsule|verif|digest|sha256/i,
  diffs: /(?:diff|patch|scor)/i,
  tests: /test|scor|verif|parity/i,
  measurements: /bench|measur|result|ledger|metrics/i,
  terminal: /terminal/i,
  report: /report|summary.*\.md/i,
};
export function FactoryRunsPage() {
  const { t } = useTranslation();
  const { label } = useViewerLabels();
  const [listing, setListing] = useState<RunList>({ runs: [], launch_templates: [], launch_enabled: false });
  const [selected, setSelected] = useState('');
  const [loadedDetail, setDetail] = useState<RunDetail | null>(null);
  const detail = loadedDetail?.run.id === selected ? loadedDetail : null;
  const [panel, setPanel] = useState<Panel>('overview');
  const [events, setEvents] = useState<StoryEvent[]>([]);
  const [position, setPosition] = useState(0);
  const [live, setLive] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [template, setTemplate] = useState('');
  const [file, setFile] = useState<FileContent | null>(null);
  const [filePath, setFilePath] = useState('');
  const [fileError, setFileError] = useState('');
  const [launching, setLaunching] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const result = await factoryApi.list();
      setListing(result);
      setSelected((old) => old || result.runs[0]?.id || '');
      setTemplate((old) => old || result.launch_templates[0]?.id || '');
    } catch (err) {
      setError(String(err));
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
    setFilePath('');
    setError('');
    setPlaying(false);
    factoryApi
      .detail(selected)
      .then((result) => {
        if (active) {
          setDetail(result);
          setEvents(result.events);
          setPosition(result.events.length);
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
  }, [selected]);
  useEffect(() => {
    if (!live || !selected || !detail) return;
    let active = true;
    const tick = async () => {
      try {
        const result = await factoryApi.story(selected, events.length);
        if (!active) return;
        if (result.events.length) {
          setEvents((old) => (result.reset ? result.events : [...old, ...result.events]));
          setPosition(result.total);
          const next = await factoryApi.detail(selected);
          if (active) setDetail(next);
        }
      } catch (err) {
        if (active) setError(String(err));
      }
    };
    const timer = window.setInterval(() => {
      void tick();
    }, 2000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [selected, live, detail, events.length]);
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
    if (!selected || !previewPath) return;
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
  }, [selected, previewPath, previewDigest]);
  const visibleEvents = events.slice(0, position);
  const cursor = visibleEvents[visibleEvents.length - 1];
  const records = detail?.records || {};
  const graph = useMemo(
    () => (detail ? detectGraph(detail.graph, { contract: detail.contract, tasks: detail.records.tasks }) : null),
    [detail],
  );
  const selectPanel = (value: Panel) => {
    setPanel(value);
    setFilePath('');
  };
  async function launch() {
    setLaunching(true);
    setError('');
    try {
      const result = await factoryApi.launch(template);
      await refresh();
      setSelected(result.id);
      setLive(true);
    } catch (err) {
      setError(String(err));
    } finally {
      setLaunching(false);
    }
  }
  return (
    <div className="factory-runs-page" data-testid="factory-runs-page">
      <aside className="factory-rail" data-testid="factory-runs-rail">
        <div className="factory-heading">
          <h1 data-testid="factory-runs-title">{t('factoryRuns.title')}</h1>
          <button data-testid="factory-runs-refresh" onClick={() => void refresh()}>
            {t('factoryRuns.refresh')}
          </button>
        </div>
        <p className="factory-muted" data-testid="factory-runs-description">
          {t('factoryRuns.description')}
        </p>
        <FactoryRunList runs={listing.runs} selected={selected} onSelect={setSelected} />
        <form
          className="factory-launch"
          data-testid="factory-runs-launch"
          onSubmit={(event) => {
            event.preventDefault();
            void launch();
          }}
        >
          <h2 data-testid="factory-runs-launch-title">{t('factoryRuns.launch')}</h2>
          <select
            data-testid="factory-runs-template"
            aria-label={t('factoryRuns.template')}
            value={template}
            onChange={(event) => setTemplate(event.target.value)}
            disabled={!listing.launch_enabled}
          >
            {listing.launch_templates.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          <button data-testid="factory-runs-launch-button" disabled={launching || !listing.launch_enabled || !template}>
            {t(launching ? 'factoryRuns.launching' : 'factoryRuns.launch')}
          </button>
          {(!listing.launch_enabled || !listing.launch_templates.length) && (
            <p className="factory-muted" data-testid="factory-runs-launch-disabled">
              {t('factoryRuns.launchDisabled')}
            </p>
          )}
        </form>
      </aside>
      <section className="factory-main" data-testid="factory-runs-main">
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
                <h2 data-testid="factory-runs-run-title">{detail.run.name}</h2>
                <p className="factory-muted">
                  {detail.run.task_id} · {detail.run.status}
                </p>
              </div>
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
            </header>
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
                  {value === 'artifacts' ? label('artifacts') : t(`factoryRuns.${value}`)}
                </button>
              ))}
            </nav>
            <section className="factory-evidence" data-testid="factory-runs-evidence">
              {panel === 'overview' && (
                <>
                  <div className="factory-stats">
                    <article>
                      <strong>{events.length}</strong>
                      <span>{t('factoryRuns.events')}</span>
                    </article>
                    <article>
                      <strong>{detail.files.length}</strong>
                      <span>{t('factoryRuns.files')}</span>
                    </article>
                    <article>
                      <strong>
                        {detail.files.filter((item) => ['mismatch', 'missing'].includes(item.integrity)).length}
                      </strong>
                      <span>{t('factoryRuns.mismatches')}</span>
                    </article>
                  </div>
                  <ol className="factory-timeline" data-testid="factory-runs-timeline">
                    {visibleEvents.map((event, index) => (
                      <li key={`${event.id}-${index}`} data-testid="factory-runs-event" data-variant={event.id}>
                        <time>{new Date(event.created * 1000).toLocaleTimeString()}</time>
                        <strong>{event.kind}</strong>
                        <span>{event.summary}</span>
                      </li>
                    ))}
                  </ol>
                </>
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
              {panel === 'measurements' && (
                <Measurements
                  observations={records.observations || []}
                  onOpenEvidence={(artifact) => {
                    const source = detail.files.find((item) => item.artifact_ids?.includes(artifact));
                    if (source) setFilePath(source.path);
                  }}
                />
              )}
              {panel !== 'overview' && panel !== 'graph' && (
                <EvidenceFileBrowser
                  key={`${selected}:${panel}`}
                  files={matchingFiles}
                  runFiles={detail.files}
                  selectedFile={selectedFile}
                  content={file}
                  error={fileError}
                  onSelect={setFilePath}
                />
              )}
            </section>
          </>
        )}
      </section>
    </div>
  );
}
