import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  factoryApi,
  type EvidenceFile,
  type FileContent,
  type JsonRecord,
  type RunDetail,
  type RunList,
  type StoryEvent,
} from './api';
import { MarkdownRenderer } from '../../components/MarkdownRenderer';
import { Measurements } from './Measurements';
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
const patterns: Partial<Record<Panel, RegExp>> = {
  contract: /contract|task.*\.json/i,
  ontology: /ontology|dictionary|alignment|example\.md/i,
  capsules: /cc\.yaml|capsule|verif|digest|sha256/i,
  diffs: /\.diff$|\.patch$|scor/i,
  tests: /test|scor|verif|parity/i,
  measurements: /bench|measur|result|ledger|metrics/i,
  terminal: /session|\.log$|stdout|stderr|terminal/i,
  report: /report|summary.*\.md/i,
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
          key={String(node.node_id || node.id || index)}
          data-testid="factory-runs-graph-node"
          data-variant={String(node.node_id || node.id || index)}
        >
          <strong>{String(node.title || node.label || node.node_id || node.id || node.capability || '')}</strong>
          <small>{String(node.status || node.state || node.kind || '')}</small>
          <CapsuleChips value={node} />
          <JsonView value={node} />
        </article>
      ))}
      {nodes.length === 0 && <JsonView value={value} />}
    </div>
  );
}

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
  const [listing, setListing] = useState<RunList>({ runs: [], launch_templates: [], launch_enabled: false });
  const [selected, setSelected] = useState(entry?.run || '');
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [panel, setPanel] = useState<Panel>(entry?.file ? 'capsules' : 'overview');
  const [events, setEvents] = useState<StoryEvent[]>([]);
  const [position, setPosition] = useState(0);
  const [live, setLive] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [template, setTemplate] = useState('');
  const [file, setFile] = useState<FileContent | null>(null);
  const [filePath, setFilePath] = useState(entry?.file || '');
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
  useEffect(() => {
    setFile(null);
    if (!selected || !filePath) return;
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
  }, [selected, filePath]);
  const matchingFiles = useMemo(
    () => detail?.files.filter((item) => item.path === filePath || patterns[panel]?.test(item.display_path || item.path)) || [],
    [detail, filePath, panel],
  );
  const visibleEvents = events.slice(0, position);
  const cursor = visibleEvents[visibleEvents.length - 1];
  const records = detail?.records || {};
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
  const selectRun = (id: string) => {
    if (id === selected) return;
    window.history.replaceState(window.history.state, '', runHref(id));
    setFilePath('');
    setSelected(id);
  };
  const selectPanel = (value: Panel) => {
    setPanel(value);
    setFilePath('');
    setFile(null);
  };
  async function launch() {
    setLaunching(true);
    setError('');
    try {
      const result = await factoryApi.launch(template);
      await refresh();
      selectRun(result.id);
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
        <div className="factory-run-list" data-testid="factory-runs-list">
          {listing.runs.map((run) => (
            <div key={run.id} data-testid="factory-runs-run-entry" data-variant={run.id}>
              <button
                className="factory-run"
                style={{ width: '100%' }}
                data-testid="factory-runs-run"
                data-variant={run.id}
                aria-pressed={run.id === selected}
                onClick={() => selectRun(run.id)}
              >
                <strong>{run.name}</strong>
                <span>
                  {run.kind} · {run.status || t('factoryRuns.recorded')}
                </span>
                <small>{run.task_id}</small>
              </button>
              <CapsuleChips value={[run.task_id, run.objective]} />
            </div>
          ))}
          {!listing.runs.length && <p data-testid="factory-runs-empty">{t('factoryRuns.empty')}</p>}
        </div>
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
                <CapsuleChips value={[detail.stack, records.tasks?.map(({ component_cc, capability_cc }) => [component_cc, capability_cc])]} />
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
                  {t(`factoryRuns.${value}`)}
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
                        <span>{event.summary} <CapsuleChips value={capsuleEvent(event)} /></span>
                      </li>
                    ))}
                  </ol>
                </>
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
              {panel === 'capsules' && (
                <div className="cc-actions" data-testid="factory-runs-run-capsules">
                  <CapsuleChips value={[detail.stack, records.tasks?.map(({ component_cc, capability_cc }) => [component_cc, capability_cc])]} />
                  <a href={capsuleHref()} data-testid="factory-runs-capsule-browse">{copy('catalog')} →</a>
                </div>
              )}
              {panel === 'tests' && <JsonView value={records.evaluations || []} />}
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
                <div className="factory-file-grid">
                  <div className="factory-files" data-testid="factory-runs-files">
                    {matchingFiles.map((item) => (
                      <button
                        key={item.path}
                        data-testid="factory-runs-file"
                        data-variant={item.path}
                        aria-pressed={filePath === item.path}
                        onClick={() => setFilePath(item.path)}
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
                        <Digest file={file} />
                        {file.truncated && <p data-testid="factory-runs-truncated">{t('factoryRuns.truncated')}</p>}
                        {/\.md(?:$| ·)/i.test(file.display_path || file.path) && panel !== 'diffs' ? (
                          <MarkdownRenderer content={file.content} testId="factory-runs-markdown" />
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
