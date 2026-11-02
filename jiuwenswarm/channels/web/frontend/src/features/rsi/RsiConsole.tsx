import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  Activity,
  ArrowUpRight,
  Box,
  Check,
  ChevronRight,
  Clock3,
  FileCode2,
  GitBranch,
  Layers3,
  Moon,
  Play,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Sparkles,
  Square,
  Sun,
  X,
} from 'lucide-react';
import { ccCandidate, ccOperatorAction, ccSnapshot, ccSourceTargets, ccStartRun } from './ccApi';
import type { CcCandidateDetail, CcNode, CcSnapshot, CcSourceCatalog } from './ccTypes';
import { ccLineage } from './ccLineage';
import {
  consoleTargets,
  formatMeasure,
  isRunActive,
  nodeIteration,
  nodeStatus,
  percent,
  runStages,
  statusTone,
} from './consoleModel';
import { ConsoleFiles } from './components/ConsoleFiles';
import { ConsoleLineage } from './components/ConsoleLineage';
import '../../styles/themes/default/rsi-console.css';
import './styles/console.css';

const message = (error: unknown) => (error instanceof Error ? error.message : String(error));

function Panel({
  title,
  icon,
  action,
  children,
  className = '',
}: {
  title: string;
  icon: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rc-panel ${className}`} data-testid="rsi-console-panel" data-variant={title}>
      <header>
        <span className="rc-panel-icon">{icon}</span>
        <h2>{title}</h2>
        {action && <div className="rc-panel-action">{action}</div>}
      </header>
      {children}
    </section>
  );
}

function Meter({
  label,
  used,
  limit,
  suffix = '',
}: {
  label: string;
  used: number | null | undefined;
  limit?: number | null;
  suffix?: string;
}) {
  const fill = used != null && limit != null && limit > 0 ? Math.min(100, Math.max(0, (used / limit) * 100)) : 0;
  return (
    <div className="rc-meter" data-testid="rsi-console-budget-meter" data-variant={label}>
      <div>
        <span>{label}</span>
        <b>
          {formatMeasure(used, suffix)} <small>/ {formatMeasure(limit, suffix)}</small>
        </b>
      </div>
      <div
        className="rc-bar"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={limit ?? undefined}
        aria-valuenow={used ?? undefined}
        aria-valuetext={used == null ? 'Not reported' : `${used} of ${limit ?? 'unreported limit'}`}
      >
        <i style={{ width: `${fill}%` }} />
      </div>
    </div>
  );
}

function Score({
  label,
  value,
  previous,
}: {
  label: string;
  value: number | null | undefined;
  previous?: number | null;
}) {
  const delta = value != null && previous != null ? value - previous : null;
  return (
    <div className="rc-score-row">
      <span>{label}</span>
      <div className="rc-bar">
        <i style={{ width: `${Math.max(0, Math.min(100, (value ?? 0) * 100))}%` }} />
      </div>
      <b>{percent(value)}</b>
      {delta != null && (
        <small className={delta >= 0 ? 'rc-positive' : 'rc-negative'}>
          {delta >= 0 ? '+' : ''}
          {percent(delta)} vs parent
        </small>
      )}
    </div>
  );
}

export function RsiConsole({ onOpenHarness }: { onOpenHarness: () => void }) {
  const [snapshot, setSnapshot] = useState<CcSnapshot | null>(null);
  const [catalog, setCatalog] = useState<CcSourceCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [targetId, setTargetId] = useState('');
  const [runId, setRunId] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const [generation, setGeneration] = useState('all');
  const [modal, setModal] = useState<'files' | 'lineage' | null>(null);
  const [detail, setDetail] = useState<CcCandidateDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pendingRun, setPendingRun] = useState<{ id: string; target: string } | null>(null);
  const [uncertainLaunch, setUncertainLaunch] = useState<string | null>(null);
  const [appearance, setAppearance] = useState<'light' | 'dark'>(() =>
    document.documentElement.dataset.colorMode === 'dark' ? 'dark' : 'light',
  );
  const alive = useRef(true);
  const refreshInFlight = useRef(false);
  const actionInFlight = useRef(false);
  const log = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    if (refreshInFlight.current) return;
    refreshInFlight.current = true;
    if (alive.current) setRefreshing(true);
    try {
      const [view, source] = await Promise.allSettled([ccSnapshot(), ccSourceTargets()]);
      if (!alive.current) return;
      const errors: string[] = [];
      if (view.status === 'fulfilled') setSnapshot(view.value);
      else errors.push(`Run data: ${message(view.reason)}`);
      if (source.status === 'fulfilled') setCatalog(source.value);
      else errors.push(`Capsule catalog: ${message(source.reason)}`);
      setError(errors.length ? errors.join(' · ') : null);
    } finally {
      refreshInFlight.current = false;
      if (alive.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    document.documentElement.classList.add('rsi-console-open');
    void refresh();
    const timer = window.setInterval(() => {
      if (!document.hidden) void refresh();
    }, 5000);
    return () => {
      alive.current = false;
      document.documentElement.classList.remove('rsi-console-open');
      window.clearInterval(timer);
    };
  }, [refresh]);

  const targets = useMemo(() => consoleTargets(snapshot, catalog), [snapshot, catalog]);
  const target = targets.find((item) => item.id === targetId);
  const runs = useMemo(
    () => (snapshot?.runs ?? []).filter((item) => item.target_id === targetId),
    [snapshot, targetId],
  );
  const pending = pendingRun?.target === targetId;
  const run = runs.find((item) => item.id === runId) ?? (pending ? undefined : runs[runs.length - 1]);
  const nodes = useMemo(
    () => (snapshot?.nodes ?? []).filter((item) => item.target_id === targetId),
    [snapshot, targetId],
  );
  const tree = useMemo(() => ccLineage(nodes, run?.id, Boolean(run)), [nodes, run]);
  const children = tree.filter(
    ({ node }) =>
      node.parent_id != null && (!pending || node.run_id === pendingRun?.id) && (!run || node.run_id === run.id),
  );
  const filtered = children.filter((item) => generation === 'all' || item.depth === Number(generation));
  const selected = nodes.find((node) => node.id === selectedId);
  const iteration = selected ? nodeIteration(selected, snapshot?.runs ?? []) : undefined;
  const lineage = run?.lineage;
  const progress = run?.progress;
  const progressStale = Boolean(progress && (progress.stale || Date.now() / 1000 - progress.observed_at > 20));
  const maxRounds = lineage?.max_iterations ?? progress?.max_iterations;
  const completedRounds = lineage?.completed_iterations ?? progress?.completed_iterations;
  const activeRun = runs.find(isRunActive);
  const running = Boolean(activeRun || pendingRun?.target === targetId);
  const stages = runStages(run);
  const activeStage = stages.indexOf(run?.stage ?? '');
  const currentActivity = run?.activity[run.activity.length - 1];
  const closeModal = useCallback(() => setModal(null), []);
  const startBlocker = error
    ? 'Refresh the connection before starting a run.'
    : uncertainLaunch === targetId
      ? 'The previous launch could not be confirmed. Reconcile it with the operator before trying again.'
      : pending
        ? 'Waiting for the accepted run to be published.'
        : running
          ? 'A run is already active for this capsule.'
          : !target
            ? 'Select an available capsule.'
            : !target.run.allowed
              ? (target.run.blocker ?? 'This capsule is not ready to run.')
              : !target.revision
                ? 'The engine has not published a launch revision.'
                : null;

  useEffect(() => {
    if (!targets.some((item) => item.id === targetId)) setTargetId(targets[0]?.id ?? '');
  }, [targets, targetId]);
  useEffect(() => {
    if (pendingRun && snapshot?.runs.some((item) => item.id === pendingRun.id)) setPendingRun(null);
  }, [pendingRun, snapshot]);
  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [run?.activity.length, run?.id]);
  useEffect(() => {
    setDetail(null);
    setDetailError(null);
    if (!selected) {
      setDetailLoading(false);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    void ccCandidate(selected.id, selected.hash)
      .then((result) => {
        if (cancelled) return;
        if (result.node_id !== selected.id || result.candidate_hash !== selected.hash)
          throw new Error('The returned source does not match this candidate.');
        setDetail(result);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setDetailError(message(cause));
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selected?.id, selected?.hash]);

  function chooseTarget(id: string) {
    setTargetId(id);
    setRunId('');
    setSelectedId('');
    setGeneration('all');
    setNotice(null);
  }
  async function startRun() {
    if (!target || !target.revision || startBlocker || actionInFlight.current) return;
    actionInFlight.current = true;
    setBusy(true);
    setNotice(null);
    const id = target.id;
    try {
      const receipt = await ccStartRun(id, target.revision, crypto.randomUUID());
      setPendingRun({ id: receipt.run_id, target: id });
      setRunId(receipt.run_id);
      setNotice('Run accepted. Waiting for the engine to publish progress.');
      await refresh();
    } catch (cause) {
      setUncertainLaunch(id);
      setNotice(`${message(cause)} No automatic retry was sent.`);
    } finally {
      actionInFlight.current = false;
      if (alive.current) setBusy(false);
    }
  }
  async function operatorAction(action: 'admit' | 'activate', node: CcNode) {
    if (actionInFlight.current || !node[action].allowed || error) return;
    actionInFlight.current = true;
    setBusy(true);
    try {
      await ccOperatorAction(action, node.id, node.hash);
      setNotice(action === 'admit' ? 'Candidate admitted to the library.' : 'Candidate activated for future runs.');
      await refresh();
    } catch (cause) {
      setNotice(message(cause));
    } finally {
      actionInFlight.current = false;
      if (alive.current) setBusy(false);
    }
  }

  return (
    <div className="rsi-console" data-appearance={appearance} data-testid="rsi-console">
      <header className="rc-top">
        <div className="rc-brand">
          <div className="rc-mark">
            <Sparkles size={23} />
          </div>
          <div>
            <h1 data-testid="rsi-console-title">RSI Console</h1>
            <p>
              Recursive self-improvement <span>·</span> Capsule workspace
            </p>
          </div>
        </div>
        <div className="rc-top-actions">
          <span className="rc-run-state" role="status" data-testid="rsi-console-run-state">
            <i className={running ? 'live' : ''} />
            {loading
              ? 'Connecting'
              : error
                ? 'Connection unavailable'
                : pending
                  ? 'Awaiting progress'
                  : (run?.status.replace(/_/g, ' ') ?? 'Ready to improve')}
          </span>
          <button
            className="rc-icon"
            data-testid="rsi-console-refresh"
            aria-label="Refresh RSI data"
            disabled={refreshing}
            onClick={() => void refresh()}
          >
            <RefreshCw size={17} className={refreshing ? 'rc-spin' : ''} />
          </button>
          <button
            className="rc-icon"
            data-testid="rsi-console-theme"
            aria-label={appearance === 'light' ? 'Use dark theme' : 'Use light theme'}
            onClick={() => setAppearance(appearance === 'light' ? 'dark' : 'light')}
          >
            {appearance === 'light' ? <Moon size={17} /> : <Sun size={17} />}
          </button>
          <button className="rc-button rc-small rc-ghost" data-testid="rsi-console-harness" onClick={onOpenHarness}>
            Harness experiments <ArrowUpRight size={14} />
          </button>
        </div>
      </header>
      {error && (
        <div className="rc-notice rc-error" role="alert" data-testid="rsi-console-connection-error">
          {error} {snapshot && 'Showing the last received data.'}
        </div>
      )}
      {!error && snapshot?.blocker && (
        <div className="rc-notice" role="status" data-testid="rsi-console-publication-status">
          {snapshot.blocker}
        </div>
      )}
      {notice && (
        <div className="rc-notice" role="status" data-testid="rsi-console-notice">
          {notice}
          <button
            className="rc-icon"
            aria-label="Dismiss notice"
            data-testid="rsi-console-dismiss"
            onClick={() => setNotice(null)}
          >
            <X size={14} />
          </button>
        </div>
      )}
      <div className="rc-grid">
        <div className="rc-column rc-config">
          <Panel title="Run configuration" icon={<Settings2 size={16} />}>
            <div className="rc-body">
              <label className="rc-field">
                <span>Target to improve</span>
                <select
                  data-testid="rsi-console-target"
                  value={targetId}
                  disabled={busy || running || loading}
                  onChange={(event) => chooseTarget(event.target.value)}
                >
                  {!targets.length && (
                    <option value="">{loading ? 'Loading capsules…' : 'No capsules available'}</option>
                  )}
                  <optgroup label="Capsule catalog">
                    {targets.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </optgroup>
                </select>
              </label>
              <div className="rc-target-card" data-testid="rsi-console-target-summary">
                <div>
                  <Box size={16} />
                  <strong>{target?.name ?? 'Choose a capsule'}</strong>
                </div>
                <p>{target?.description ?? 'Available targets are loaded from your installed capsule catalog.'}</p>
                {target?.parent_hash && <span className="rc-mono">{target.parent_hash.slice(0, 16)}</span>}
              </div>
              <div className="rc-section-label">
                <span className="rc-eyebrow">RUN BUDGET</span>
                <span className="rc-pill muted">Engine managed</span>
              </div>
              <div className="rc-budget-fields">
                {[
                  ['RSI rounds', lineage?.max_iterations],
                  ['Children / round', null],
                  ['Generation call limit', run?.budget.generation_call_limit],
                  ['Max tokens', null],
                  ['Wall-clock (min)', run?.budget.limit_seconds == null ? null : run.budget.limit_seconds / 60],
                  ['Early-stop rounds', null],
                ].map(([label, value]) => (
                  <label className="rc-field" key={String(label)}>
                    <span>{label}</span>
                    <input
                      data-testid="rsi-console-budget-field"
                      data-variant={String(label)}
                      value={value == null ? 'Not reported' : String(value)}
                      readOnly
                      aria-readonly="true"
                    />
                  </label>
                ))}
              </div>
              <label className="rc-field">
                <span>Objective</span>
                <input data-testid="rsi-console-objective" value="Installed capsule objective" readOnly />
              </label>
              <p className="rc-hint">
                Budgets and objectives are set by the installed run policy. Browser overrides are not supported yet.
              </p>
              <div className="rc-actions rc-run-actions">
                <button
                  className="rc-button primary"
                  data-testid="rsi-console-start"
                  disabled={busy || Boolean(startBlocker)}
                  title={startBlocker ?? 'Start an RSI run'}
                  onClick={() => void startRun()}
                >
                  <Play size={15} />
                  {busy ? 'Submitting…' : 'Start run'}
                </button>
                <button
                  className="rc-button"
                  data-testid="rsi-console-stop"
                  disabled
                  title="Stopping capsule runs is not exposed by the engine yet"
                >
                  <Square size={13} /> Stop
                </button>
                <button
                  className="rc-button rc-ghost"
                  data-testid="rsi-console-clear"
                  disabled={running || busy}
                  onClick={() => {
                    setSelectedId('');
                    setGeneration('all');
                    setNotice(null);
                  }}
                >
                  Clear
                </button>
              </div>
              {startBlocker && (
                <p className="rc-hint" data-testid="rsi-console-start-blocker">
                  {startBlocker}
                </p>
              )}
            </div>
          </Panel>
          <Panel title="Budget usage" icon={<Clock3 size={16} />}>
            <div className="rc-body rc-meters">
              <Meter label="Rounds" used={completedRounds} limit={maxRounds} />
              <Meter label="Model calls" used={lineage?.model_calls ?? progress?.model_calls} />
              {progress && (
                <Meter label="Evaluation jobs started" used={progress.executions} limit={progress.execution_limit} />
              )}
              <Meter label="Tokens" used={null} />
              <Meter
                label="Wall-clock"
                used={run?.budget.elapsed_seconds == null ? null : run.budget.elapsed_seconds / 60}
                limit={run?.budget.limit_seconds == null ? null : run.budget.limit_seconds / 60}
                suffix="m"
              />
              <p className="rc-hint">— means the engine has not reported a measurement.</p>
            </div>
          </Panel>
        </div>
        <div className="rc-column rc-main">
          <Panel
            title="Improvement workflow"
            icon={<Activity size={16} />}
            action={
              <span className="rc-pill accent" data-testid="rsi-console-current-stage">
                {progressStale ? 'Updates delayed' : run ? run.stage : running ? 'Starting' : 'Awaiting run'}
              </span>
            }
          >
            <div className="rc-body">
              <div className="rc-round-strip">
                <span className="rc-eyebrow">ROUNDS</span>
                <div className="rc-rounds">
                  {Array.from({ length: Math.min(30, maxRounds ?? 0) }, (_, index) => (
                    <span
                      key={index}
                      className={`rc-round ${(completedRounds ?? 0) > index ? 'done' : ''}`}
                      data-testid="rsi-console-round"
                      data-variant={index + 1}
                    >
                      {(completedRounds ?? 0) > index ? <Check size={12} /> : index + 1}
                    </span>
                  ))}
                  {!maxRounds && <span className="rc-hint">No rounds reported</span>}
                  {(maxRounds ?? 0) > 30 && <span className="rc-hint">+{maxRounds! - 30}</span>}
                </div>
              </div>
              <div className="rc-stages" data-testid="rsi-console-stages">
                {(stages.length
                  ? stages
                  : [
                      'Parent evaluation',
                      'Benchmark baseline',
                      'Diagnose',
                      'Propose edits',
                      'Verify candidate',
                      'Benchmark candidate',
                      'Rank & select',
                      'Publishing results',
                    ]
                ).map((stage, index) => (
                  <div
                    className={`rc-stage ${stages.length && index === activeStage && !progressStale ? 'current' : ''}`}
                    key={stage}
                    data-testid="rsi-console-stage"
                    data-variant={stage}
                  >
                    <span className="rc-eyebrow">{String(index + 1).padStart(2, '0')}</span>
                    <strong>{stage}</strong>
                    <small>{stages.length ? 'Engine event' : 'Workflow'}</small>
                    <span className="rc-stage-status">
                      {stages.length
                        ? index === activeStage
                          ? progressStale
                            ? 'Last observed'
                            : run?.status.replace(/_/g, ' ')
                          : 'Recorded'
                        : 'Waiting'}
                    </span>
                  </div>
                ))}
              </div>
              <div className="rc-substep">
                <i className={running && !progressStale ? 'live' : ''} />
                <span>
                  {pending
                    ? 'Run accepted — waiting for published events'
                    : (currentActivity?.summary ?? 'Choose a capsule and start an improvement run.')}
                </span>
              </div>
              {progress && (
                <p className="rc-hint" data-testid="rsi-console-progress-observation">
                  {progressStale
                    ? 'Updates delayed — the current stage is unconfirmed.'
                    : 'Live progress · refreshes every 5 seconds.'}{' '}
                  Last observed {new Date(progress.observed_at * 1000).toLocaleTimeString()}.
                  {progress.iteration ? ` Round ${progress.iteration} of ${maxRounds ?? '—'}.` : ''}
                </p>
              )}
              <div className="rc-log" ref={log} role="log" aria-label="Run activity" data-testid="rsi-console-log">
                {run?.activity.length ? (
                  run.activity.map((entry) => (
                    <div key={entry.id}>
                      <time>
                        {Number.isNaN(Date.parse(entry.at)) ? entry.at : new Date(entry.at).toLocaleTimeString()}
                      </time>
                      <b>{entry.stage}</b>
                      <span>{entry.summary}</span>
                    </div>
                  ))
                ) : (
                  <p>No stage events received yet. Waiting for the worker’s progress feed.</p>
                )}
              </div>
              {lineage?.stop_reason && (
                <p className="rc-hint" data-testid="rsi-console-end-reason">
                  Run ended: {lineage.stop_reason.replace(/_/g, ' ')}
                </p>
              )}
              {run?.blockers.map((blocker) => (
                <p className="rc-notice" key={blocker}>
                  {blocker}
                </p>
              ))}
            </div>
          </Panel>
          <Panel
            title="Children"
            icon={<Layers3 size={16} />}
            action={
              <>
                <span className="rc-count">{children.length}</span>
                <button
                  className="rc-button rc-small"
                  data-testid="rsi-console-open-tree"
                  onClick={() => setModal('lineage')}
                >
                  <GitBranch size={14} /> Lineage tree
                </button>
              </>
            }
          >
            <div className="rc-children-toolbar">
              <label>
                <span>Generation</span>
                <select
                  data-testid="rsi-console-generation"
                  value={generation}
                  onChange={(event) => setGeneration(event.target.value)}
                >
                  <option value="all">All generations</option>
                  {[...new Set(children.map((item) => item.depth))]
                    .sort((a, b) => a - b)
                    .map((depth) => (
                      <option key={depth} value={depth}>
                        Generation {depth}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                <span>Run</span>
                <select
                  data-testid="rsi-console-run-select"
                  value={run?.id ?? ''}
                  disabled={running || busy}
                  onChange={(event) => {
                    setRunId(event.target.value);
                    setSelectedId('');
                    setGeneration('all');
                  }}
                >
                  {!runs.length && <option value="">No runs yet</option>}
                  {runs.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.id}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="rc-children" data-testid="rsi-console-children">
              {filtered.map(({ node, depth }) => {
                const row = nodeIteration(node, snapshot?.runs ?? []);
                return (
                  <button
                    key={node.id}
                    className="rc-child"
                    data-testid="rsi-console-child"
                    data-variant={node.id}
                    aria-pressed={selectedId === node.id}
                    onClick={() => setSelectedId(node.id)}
                  >
                    <div className="rc-child-heading">
                      <span className="rc-mono">{node.label}</span>
                      <span className={`rc-pill ${statusTone(nodeStatus(node))}`}>{nodeStatus(node)}</span>
                    </div>
                    <span className="rc-hint">
                      Generation {depth}
                      {row?.best ? ' · Best recorded candidate' : ''}
                    </span>
                    <div className="rc-child-scores">
                      <div>
                        Pass rate<b>{percent(row?.correctness_candidate)}</b>
                      </div>
                      <div>
                        Latency ratio<b>{formatMeasure(row?.latency_ratio, '×')}</b>
                      </div>
                      <div>
                        Calls<b>{formatMeasure(row?.model_calls)}</b>
                      </div>
                    </div>
                    <p>{row?.summary ?? row?.rationale ?? 'Select to inspect the published candidate.'}</p>
                    <span className="rc-child-footer">
                      <GitBranch size={12} />
                      <span>{node.parent_id}</span>
                      <ChevronRight size={14} />
                    </span>
                  </button>
                );
              })}
            </div>
            {!filtered.length && (
              <div className="rc-empty rc-children-empty" data-testid="rsi-console-children-empty">
                <div className="rc-empty-icon">
                  <Layers3 size={26} />
                </div>
                <h3>{children.length ? 'No children in this generation' : 'Room for the next improvement'}</h3>
                <p>
                  {children.length
                    ? 'Choose another generation to see its candidates.'
                    : 'Generated candidates will appear here with measured results and a traceable parent.'}
                </p>
              </div>
            )}
          </Panel>
          <div className="rc-footnote">
            <ShieldCheck size={14} />
            Measured evidence · Explicit admission · Activation for future runs
          </div>
        </div>
        <div className="rc-column rc-inspector">
          <Panel
            title="Inspector"
            icon={<Box size={16} />}
            action={<span className="rc-eyebrow">{selected ? 'CANDIDATE' : 'NO SELECTION'}</span>}
          >
            <div className="rc-body">
              {!selected ? (
                <div className="rc-empty rc-inspector-empty" data-testid="rsi-console-inspector-empty">
                  <div className="rc-empty-icon">
                    <Box size={28} />
                  </div>
                  <h3>A closer look</h3>
                  <p>Select a child to explore its proposal, measured scores, and source changes.</p>
                  <span className="rc-inspector-hint">
                    <span>01</span> Select a candidate
                  </span>
                  <span className="rc-inspector-hint">
                    <span>02</span> Compare with its parent
                  </span>
                  <span className="rc-inspector-hint">
                    <span>03</span> Review and activate
                  </span>
                </div>
              ) : (
                <>
                  <div className="rc-selected-title">
                    <h3 data-testid="rsi-console-selected-label">{selected.label}</h3>
                    <span className={`rc-pill ${statusTone(nodeStatus(selected))}`}>{nodeStatus(selected)}</span>
                  </div>
                  <dl className="rc-kv">
                    <dt>Capsule</dt>
                    <dd>{selected.target_id}</dd>
                    <dt>Generation</dt>
                    <dd>{ccLineage(nodes).find((item) => item.node.id === selected.id)?.depth ?? '—'}</dd>
                    <dt>Parent</dt>
                    <dd className="rc-mono">{selected.parent_id ?? 'Root capsule'}</dd>
                    <dt>Hash</dt>
                    <dd className="rc-mono" title={selected.hash}>
                      {selected.hash.slice(0, 16)}
                    </dd>
                    <dt>Admission</dt>
                    <dd>{selected.admission_status}</dd>
                    <dt>Activation</dt>
                    <dd>{selected.activation_status}</dd>
                  </dl>
                  <div className="rc-proposal">
                    <span className="rc-eyebrow">PROPOSAL</span>
                    <p>
                      {detail?.rationale ??
                        iteration?.rationale ??
                        iteration?.summary ??
                        'No proposal was published for this node.'}
                    </p>
                  </div>
                  <div className="rc-score-box">
                    <Score
                      label="Pass rate"
                      value={iteration?.correctness_candidate}
                      previous={iteration?.correctness_parent}
                    />
                    <dl className="rc-kv">
                      <dt>Latency ratio</dt>
                      <dd>{formatMeasure(iteration?.latency_ratio, '×')}</dd>
                      <dt>Benchmark gain</dt>
                      <dd>{percent(iteration?.benchmark?.relative_gain)}</dd>
                      <dt>Model calls</dt>
                      <dd>{formatMeasure(iteration?.model_calls)}</dd>
                    </dl>
                  </div>
                  <div className="rc-section-label">
                    <span className="rc-eyebrow">CAPTURED FILES</span>
                    {detail && <span className="rc-count">1</span>}
                  </div>
                  {detailLoading ? (
                    <p className="rc-hint">Loading source…</p>
                  ) : detailError ? (
                    <p className="rc-hint" role="status">
                      {detailError}
                    </p>
                  ) : (
                    detail && (
                      <button
                        className="rc-captured-file"
                        data-testid="rsi-console-captured-file"
                        onClick={() => setModal('files')}
                      >
                        <FileCode2 size={16} />
                        <span>{detail.path}</span>
                        <span className="rc-pill accent">
                          {detail.parent_code == null ? '?' : detail.parent_code === detail.candidate_code ? '=' : 'M'}
                        </span>
                      </button>
                    )
                  )}
                  <div className="rc-actions">
                    <button
                      className="rc-button"
                      data-testid="rsi-console-inspect-files"
                      onClick={() => setModal('files')}
                    >
                      <FileCode2 size={14} /> Inspect files
                    </button>
                    <button
                      className="rc-button"
                      data-testid="rsi-console-show-node"
                      onClick={() => setModal('lineage')}
                    >
                      <GitBranch size={14} /> Show in tree
                    </button>
                  </div>
                  <button
                    className="rc-button primary rc-full"
                    data-testid="rsi-console-improve-child"
                    disabled
                    title="The engine does not yet accept an arbitrary child as a new run target"
                  >
                    <Sparkles size={14} /> RSI this child
                  </button>
                  <p className="rc-hint">Starting a new run from a child is not supported by the current engine.</p>
                  <div className="rc-review">
                    <span className="rc-eyebrow">LIBRARY REVIEW</span>
                    <div className="rc-actions">
                      {(['admit', 'activate'] as const).map((action) => (
                        <button
                          className="rc-button rc-small"
                          key={action}
                          data-testid={`rsi-console-${action}`}
                          disabled={busy || Boolean(error) || !selected[action].allowed}
                          title={selected[action].blocker ?? undefined}
                          onClick={() => void operatorAction(action, selected)}
                        >
                          {action === 'admit' ? 'Admit to library' : 'Activate candidate'}
                        </button>
                      ))}
                    </div>
                    <p className="rc-hint">
                      {selected.activate.blocker ??
                        'Activation applies to future runs; existing runs keep their pinned capsule.'}
                    </p>
                  </div>
                </>
              )}
            </div>
          </Panel>
          <div className="rc-evidence-note">
            <ShieldCheck size={18} />
            <div>
              <strong>Evidence before improvement</strong>
              <p>Results reflect recorded evaluations. Missing measurements remain unknown.</p>
            </div>
          </div>
        </div>
      </div>
      {modal === 'files' && selected && (
        <ConsoleFiles
          node={selected}
          detail={detail}
          loading={detailLoading}
          error={detailError}
          onClose={closeModal}
        />
      )}
      {modal === 'lineage' && (
        <ConsoleLineage
          nodes={nodes}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onInspect={() => setModal('files')}
          onClose={closeModal}
        />
      )}
    </div>
  );
}
