import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowRight, Download, ExternalLink, KeyRound, LogOut, RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { GraphViewer } from '../views/GraphViewer';
import { detectGraph } from '../views/graphModel';
import { capsuleApi, type CapsuleCard } from '../cc/capsuleApi';
import { capsuleHref, plannerHref, runHref, type PlannerTab } from '../cc/navigation';
import { AblationTab } from './AblationTab';
import { GraphTlaInspector } from './GraphTlaInspector';
import {
  plannerApi,
  type CodexAuthStatus,
  type Comparison,
  type ExecutionModel,
  type PlanDetail,
  type PlannerEnvironment,
  type PlanRound,
  type PlanIr,
  type PlanSummary,
  type RequirementsEntry,
  type Selection,
  type RoundText,
  type TlcRun,
} from './plannerApi';
import './planner.css';

const LIVE: ReadonlySet<string> = new Set(['pending', 'running']);

const MUSE_SPARK_816B_PRESET = {
  format: 'factory.task-input/1',
  task_id: 'muse-spark-816b-nvfp4-dgx',
  objective:
    'Build the customized llama.cpp-based inference engine for Muse-Spark-Open-816B-A42B-NVFP4 targeting DGX Spark (sm_121, 128GB unified memory), optimizing TTFT and throughput under NVFP4 weight placement, expert weight caching, demand prediction, and gate parity.',
  subject: {
    engine: {
      name: 'llama.cpp',
      source: 'https://github.com/ggml-org/llama.cpp',
      revision: '9048bad8d6e3a0f9f1726e238e451181c7e02613',
    },
    model: {
      name: 'Muse-Spark-Open-816B-A42B-NVFP4',
      format: 'safetensors-nvfp4',
    },
  },
  target: {
    profile: 'spark-gb10',
    machine: 'DGX Spark GB10',
    arch: 'arm64',
    cuda: '13',
    sm: '121',
    node_count: 1,
  },
  acceptance_criteria: [
    { id: 'gate_unset_parity', kind: 'correctness', description: 'When all capsule gates are unset, greedy output matches stock baseline byte for byte.' },
    { id: 'gate_set_activation', kind: 'correctness', description: 'When gates are enabled, the customized engine emits capsule activation telemetry.' },
    { id: 'client_ttft_ms', kind: 'metric', description: 'End-to-end TTFT latency (ms, lower is better) on Muse-Spark-Open-816B-A42B-NVFP4.' },
    { id: 'decode_tokens_per_second', kind: 'metric', description: 'Sustained decode throughput (tokens/s, higher is better) on DGX Spark.' },
  ],
  constraints: {
    allowed_effects: ['workspace.read', 'workspace.write', 'process.exec'],
    budget: { max_turns: 300, wall_clock_s: 21600 },
  },
  notes: [
    'Baseline model: Muse-Spark-Open-816B-A42B-NVFP4; HW target: DGX Spark (sm_121).',
    'Every optimization remains behind an explicit runtime gate with byte-identical fallback.',
  ],
};

function seconds(start?: number, end?: number) {
  if (!start) return null;
  return Math.max(0, Math.round((end ?? Date.now() / 1000) - start));
}

function formatCount(value: number | null | undefined) {
  return typeof value === 'number' ? value.toLocaleString() : '—';
}

export function PlannerPage({
  plan,
  initialTab,
}: {
  plan?: string;
  initialTab?: PlannerTab;
}) {
  const { i18n } = useTranslation();
  const t = useMemo(() => i18n.getFixedT('en'), [i18n]);
  const [activeTab, setActiveTab] = useState<PlannerTab>(initialTab ?? 'live');
  const [environment, setEnvironment] = useState<PlannerEnvironment | null>(null);
  const [codexAuth, setCodexAuth] = useState<CodexAuthStatus>({ state: 'checking' });

  const refreshCodexStatus = useCallback(async () => {
    try {
      const next = await plannerApi.codexStatus();
      setCodexAuth(next);
    } catch {
      setCodexAuth({ state: 'unavailable' });
    }
  }, []);

  useEffect(() => {
    void refreshCodexStatus();
  }, [refreshCodexStatus]);

  useEffect(() => {
    const interval = codexAuth.state === 'signing_in' ? 2000 : 12000;
    const timer = window.setInterval(() => void refreshCodexStatus(), interval);
    return () => window.clearInterval(timer);
  }, [codexAuth.state, refreshCodexStatus]);

  useEffect(() => {
    if (i18n.resolvedLanguage !== 'en') {
      void i18n.changeLanguage('en');
    }
  }, [i18n]);

  useEffect(() => {
    if (initialTab) setActiveTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    void plannerApi
      .requirements()
      .then((res) => setEnvironment(res.environment))
      .catch(() => {});
  }, []);

  const switchTab = (tab: PlannerTab) => {
    setActiveTab(tab);
    window.location.hash = plannerHref(tab === 'live' ? plan : undefined, tab);
  };

  return (
    <div className="planner-shell" data-testid="factory-planner-page" data-appearance="light">
      <nav className="planner-subnav" aria-label={t('factoryPlanner.tabs.aria')}>
        <div className="planner-subnav-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'live'}
            className="planner-subnav-tab"
            data-testid="factory-planner-tab-live"
            onClick={() => switchTab('live')}
          >
            {t('factoryPlanner.tabs.live')}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'ablation'}
            className="planner-subnav-tab"
            data-testid="factory-planner-tab-ablation"
            onClick={() => switchTab('ablation')}
          >
            {t('factoryPlanner.tabs.ablation')}
          </button>
        </div>
        <div className="planner-subnav-meta">
          <span
            className={`planner-badge ${codexAuth.state === 'ready' ? 'is-good' : codexAuth.state === 'signing_in' ? 'is-info' : 'is-warn'}`}
            data-testid="factory-planner-codex-badge"
          >
            {codexAuth.state === 'ready'
              ? `Codex Ready${codexAuth.plan ? ` (${codexAuth.plan})` : ''}`
              : codexAuth.state === 'signing_in'
                ? 'Codex Signing In…'
                : codexAuth.state === 'checking'
                  ? 'Checking Codex…'
                  : 'Codex Sign-In Required'}
          </span>
          <span
            className={`planner-badge ${environment?.tlc ? 'is-good' : environment === null ? '' : 'is-bad'}`}
            data-testid="factory-planner-tlc"
          >
            {environment === null
              ? t('factoryRuns.loading')
              : environment.tlc
                ? t('factoryPlanner.tlcReadyShort')
                : t('factoryPlanner.tlcMissingShort')}
          </span>
        </div>
      </nav>

      <div className="planner-body">
        {activeTab === 'live' && (
          <LivePlannerView
            plan={plan}
            onEnvironment={setEnvironment}
            codexAuth={codexAuth}
            onCodexAuthChange={setCodexAuth}
            refreshCodexStatus={refreshCodexStatus}
          />
        )}
        {activeTab === 'ablation' && <AblationTab />}
      </div>
    </div>
  );
}

function CodexAuthCard({
  status,
  onChange,
  onRefresh,
}: {
  status: CodexAuthStatus;
  onChange: (next: CodexAuthStatus) => void;
  onRefresh: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [authError, setAuthError] = useState('');

  const isValidAuthUrl = (raw?: string | null): string | null => {
    if (!raw) return null;
    try {
      const url = new URL(raw);
      if (
        url.protocol === 'https:' &&
        ['auth.openai.com', 'auth0.openai.com', 'auth.chatgpt.com'].includes(url.hostname)
      ) {
        return url.href;
      }
    } catch {
      return null;
    }
    return null;
  };

  const handleLogin = async (deviceCode = false) => {
    setBusy(true);
    setAuthError('');
    const loginWin = window.open('about:blank', '_blank');
    if (loginWin) loginWin.opener = null;
    try {
      const res = await plannerApi.codexLogin(deviceCode);
      onChange(res);
      const valid = isValidAuthUrl(res.auth_url);
      if (valid && loginWin && !loginWin.closed) {
        loginWin.location.replace(valid);
      } else if (loginWin) {
        loginWin.close();
      }
    } catch (err) {
      loginWin?.close();
      setAuthError(String(err instanceof Error ? err.message : err));
      await onRefresh();
    } finally {
      setBusy(false);
    }
  };

  const handleCancel = async () => {
    setBusy(true);
    setAuthError('');
    try {
      const res = await plannerApi.codexCancel(status.login_attempt_id);
      onChange(res);
    } catch (err) {
      setAuthError(String(err instanceof Error ? err.message : err));
      await onRefresh();
    } finally {
      setBusy(false);
    }
  };

  const handleLogout = async () => {
    setBusy(true);
    setAuthError('');
    try {
      const res = await plannerApi.codexLogout();
      onChange(res);
    } catch (err) {
      setAuthError(String(err instanceof Error ? err.message : err));
    } finally {
      setBusy(false);
    }
  };

  const safeUrl = isValidAuthUrl(status.auth_url);

  return (
    <div className="planner-custom-editor" data-testid="factory-planner-codex-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <strong style={{ fontSize: 12.5 }}>
          <KeyRound size={13} style={{ verticalAlign: '-2px', marginRight: 5 }} aria-hidden />
          Codex Subscription
        </strong>
        <span
          className={`planner-badge ${status.state === 'ready' ? 'is-good' : status.state === 'signing_in' ? 'is-info' : 'is-warn'}`}
        >
          {status.state === 'ready'
            ? `Signed in${status.plan ? ` · ${status.plan}` : ''}`
            : status.state === 'signing_in'
              ? 'Signing in…'
              : status.state === 'checking'
                ? 'Checking…'
                : status.state === 'unavailable'
                  ? 'Unavailable'
                  : 'Sign-in required'}
        </span>
      </div>

      {status.state === 'ready' ? (
        <div className="planner-btn-row" style={{ marginTop: 8 }}>
          <button type="button" className="planner-btn" onClick={() => void onRefresh()} disabled={busy}>
            <RefreshCw size={12} aria-hidden /> Refresh
          </button>
          <button type="button" className="planner-btn" onClick={() => void handleLogout()} disabled={busy}>
            <LogOut size={12} aria-hidden /> Sign out
          </button>
        </div>
      ) : status.state === 'signing_in' ? (
        <div style={{ marginTop: 8, fontSize: 12 }}>
          <p className="factory-muted" style={{ margin: '0 0 6px' }}>
            {status.user_code
              ? 'Open the verification link below and enter this device code:'
              : 'Complete ChatGPT sign-in in the opened tab (or Cancel & switch to Device Code if localhost callback fails).'}
          </p>
          {status.user_code && (
            <p style={{ margin: '0 0 6px' }}>
              Device Code: <code style={{ fontSize: 13, fontWeight: 700 }}>{status.user_code}</code>
            </p>
          )}
          <div className="planner-btn-row" style={{ marginTop: 4 }}>
            {safeUrl && (
              <a href={safeUrl} target="_blank" rel="noreferrer" className="planner-btn is-primary">
                Open Sign-In URL <ExternalLink size={12} aria-hidden />
              </a>
            )}
            {!status.user_code && (
              <button
                type="button"
                className="planner-btn"
                onClick={() => void handleLogin(true)}
                disabled={busy}
                data-testid="factory-planner-codex-switch-device"
              >
                Use Device Code
              </button>
            )}
            <button type="button" className="planner-btn" onClick={() => void onRefresh()} disabled={busy}>
              Check status
            </button>
            <button type="button" className="planner-btn" onClick={() => void handleCancel()} disabled={busy}>
              Cancel / Retry
            </button>
          </div>
        </div>
      ) : (
        <div style={{ marginTop: 8 }}>
          <div className="planner-btn-row" style={{ marginTop: 0 }}>
            <button
              type="button"
              className="planner-btn is-primary"
              onClick={() => void handleLogin(false)}
              disabled={busy || status.state === 'unavailable'}
              data-testid="factory-planner-codex-signin"
            >
              {busy ? 'Starting…' : 'Sign in (Browser)'}
            </button>
            <button
              type="button"
              className="planner-btn"
              onClick={() => void handleLogin(true)}
              disabled={busy || status.state === 'unavailable'}
              data-testid="factory-planner-codex-device"
            >
              Use Device Code
            </button>
            <button type="button" className="planner-btn" onClick={() => void onRefresh()} disabled={busy}>
              Refresh
            </button>
          </div>
          <small className="factory-muted" style={{ display: 'block', marginTop: 5 }}>
            Tip: Use Device Code if accessing via remote IP (100.x) where localhost:1455 redirect cannot reach this host.
          </small>
        </div>
      )}

      {(authError || status.error) && (
        <p className="factory-error" style={{ marginTop: 6, marginBottom: 0, fontSize: 12 }}>
          {authError || status.error}
        </p>
      )}
    </div>
  );
}

function LivePlannerView({
  plan,
  onEnvironment,
  codexAuth,
  onCodexAuthChange,
  refreshCodexStatus,
}: {
  plan?: string;
  onEnvironment: (env: PlannerEnvironment) => void;
  codexAuth: CodexAuthStatus;
  onCodexAuthChange: (next: CodexAuthStatus) => void;
  refreshCodexStatus: () => Promise<void>;
}) {
  const { i18n } = useTranslation();
  const t = useMemo(() => i18n.getFixedT('en'), [i18n]);
  const [requirements, setRequirements] = useState<RequirementsEntry[]>([]);
  const [environment, setEnvironment] = useState<PlannerEnvironment | null>(null);
  const [chosen, setChosen] = useState('');
  const [customJson, setCustomJson] = useState('');
  const [runs, setRuns] = useState<PlanSummary[]>([]);
  const [busy, setBusy] = useState<string[]>([]);
  const [detail, setDetail] = useState<PlanDetail | null>(null);
  const [capsules, setCapsules] = useState<CapsuleCard[]>([]);
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(false);
  const selected = plan || runs[0]?.id || '';

  const capsuleNameById = useMemo(
    () => new Map(capsules.map((card) => [card.id, card.name])),
    [capsules],
  );

  const refreshRuns = useCallback(async () => {
    try {
      const result = await plannerApi.runs();
      setRuns(result.runs);
      setBusy(result.busy);
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const result = await plannerApi.requirements();
        setRequirements(result.requirements);
        setEnvironment(result.environment);
        onEnvironment(result.environment);
        setChosen((old) => old || result.requirements.find((r) => !r.problems.length)?.id || '');
      } catch (err) {
        setError(String(err instanceof Error ? err.message : err));
      }
    })();
    void capsuleApi
      .catalog(controller.signal, false)
      .then((res) => setCapsules(res.capsules))
      .catch(() => {});
    void refreshRuns();
    return () => controller.abort();
  }, [refreshRuns, onEnvironment]);

  const chosenEntry = requirements.find((r) => r.id === chosen);

  useEffect(() => {
    if (chosenEntry?.document) {
      setCustomJson(JSON.stringify(chosenEntry.document, null, 2));
    }
  }, [chosenEntry]);

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    let stopped = false;
    let timer: number;
    const tick = async () => {
      try {
        const next = await plannerApi.detail(selected);
        if (stopped) return;
        setDetail(next);
        if (LIVE.has(next.status.state)) {
          timer = window.setTimeout(tick, 2000);
        } else {
          void refreshRuns();
        }
      } catch (err) {
        if (!stopped) setError(String(err instanceof Error ? err.message : err));
      }
    };
    void tick();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [selected, refreshRuns]);

  const startPreset = async () => {
    setStarting(true);
    setError('');
    try {
      const { id } = await plannerApi.start(chosen);
      await refreshRuns();
      window.location.hash = plannerHref(id, 'live');
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setStarting(false);
    }
  };

  const startCustomJson = async () => {
    setStarting(true);
    setError('');
    try {
      const parsed = JSON.parse(customJson) as Record<string, unknown>;
      const { id } = await plannerApi.startCustom(parsed);
      await refreshRuns();
      window.location.hash = plannerHref(id, 'live');
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setStarting(false);
    }
  };

  const canStart = Boolean(environment?.tlc && chosenEntry && !chosenEntry.problems.length && !busy.length && !starting);
  const canStartCustom = Boolean(environment?.tlc && customJson.trim() && !busy.length && !starting);

  return (
    <div className="factory-runs-page factory-planner" data-testid="factory-planner-live-tab">
      <aside className="factory-rail" data-testid="factory-planner-rail">
        <div className="factory-heading">
          <div>
            <h1>{t('factoryPlanner.title')}</h1>
            <p className="factory-muted">{t('factoryPlanner.description')}</p>
          </div>
          <button
            type="button"
            className="factory-story-icon-button"
            onClick={() => void refreshRuns()}
            aria-label={t('factoryRuns.refresh')}
            title={t('factoryRuns.refresh')}
          >
            <RefreshCw size={16} aria-hidden />
          </button>
        </div>

        <CodexAuthCard status={codexAuth} onChange={onCodexAuthChange} onRefresh={refreshCodexStatus} />

        <label className="factory-planner-field">
          <span>{t('factoryPlanner.requirements')}</span>
          <select value={chosen} onChange={(event) => setChosen(event.target.value)} data-testid="factory-planner-requirements">
            {requirements.map((entry) => (
              <option key={entry.id} value={entry.id}>{entry.id}</option>
            ))}
          </select>
        </label>

        {chosenEntry && (
          <div className="factory-planner-requirement">
            <p>{chosenEntry.objective}</p>
            <div className="planner-taskinput-meta">
              {chosenEntry.contract_id && (
                <div className="factory-muted">{t('factoryPlanner.contract')}: <code>{chosenEntry.contract_id}</code></div>
              )}
              {chosenEntry.document?.subject?.engine?.name && (
                <div className="factory-muted">
                  Engine: <code>{chosenEntry.document.subject.engine.name}</code>
                  {chosenEntry.document.subject.engine.revision ? ` @ ${chosenEntry.document.subject.engine.revision}` : ''}
                </div>
              )}
              {chosenEntry.document?.subject?.model?.name && (
                <div className="factory-muted">
                  {t('factoryPlanner.subject')}: {chosenEntry.document.subject.model.name}
                  {chosenEntry.document.subject.model.format ? ` (${chosenEntry.document.subject.model.format})` : ''}
                </div>
              )}
              {chosenEntry.document?.target && (
                <div className="factory-muted">
                  {t('factoryPlanner.target')}: {chosenEntry.document.target.machine}
                  {chosenEntry.document.target.sm ? ` (sm_${chosenEntry.document.target.sm})` : ''}
                  {chosenEntry.document.target.node_count ? ` · ${chosenEntry.document.target.node_count} node` : ''}
                </div>
              )}
              {chosenEntry.document?.constraints?.allowed_effects && (
                <div className="planner-effects-row" aria-label="Allowed effects">
                  {chosenEntry.document.constraints.allowed_effects.map((eff) => (
                    <span key={eff} className="planner-badge">{eff}</span>
                  ))}
                </div>
              )}
              {chosenEntry.document?.constraints?.budget && (
                <div className="factory-muted">
                  Budget: {Object.entries(chosenEntry.document.constraints.budget).map(([k, v]) => `${k}=${v}`).join(' · ')}
                </div>
              )}
              {chosenEntry.document?.acceptance_criteria && chosenEntry.document.acceptance_criteria.length > 0 && (
                <details>
                  <summary className="factory-muted" style={{ cursor: 'pointer' }}>
                    {t('factoryPlanner.criteriaCount', { n: chosenEntry.document.acceptance_criteria.length })}
                  </summary>
                  <ul className="planner-criteria-list">
                    {chosenEntry.document.acceptance_criteria.map((ac) => (
                      <li key={ac.id}><code>{ac.id}</code> ({ac.kind}): {ac.description}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
            {chosenEntry.notes.length > 0 && (
              <ul>{chosenEntry.notes.map((note) => <li key={note}>{note}</li>)}</ul>
            )}
            {chosenEntry.problems.map((problem) => <p key={problem} className="factory-error">{problem}</p>)}
          </div>
        )}

        <button
          type="button"
          className="factory-story-launch-button"
          onClick={() => void startPreset()}
          disabled={!canStart}
          data-testid="factory-planner-start"
        >
          {starting ? t('factoryPlanner.starting') : t('factoryPlanner.start')}
        </button>

        <details className="planner-custom-editor">
          <summary>{t('factoryPlanner.customInput.toggle')}</summary>
          <p className="factory-muted" style={{ margin: '6px 0 0', fontSize: 12 }}>
            {t('factoryPlanner.customInput.lead')}
          </p>
          <textarea
            className="planner-json-textarea"
            value={customJson}
            onChange={(e) => setCustomJson(e.target.value)}
            spellCheck={false}
          />
          <div className="planner-btn-row">
            <button
              type="button"
              className="planner-btn"
              onClick={() => setCustomJson(JSON.stringify(MUSE_SPARK_816B_PRESET, null, 2))}
              data-testid="factory-planner-load-muse-spark"
            >
              {t('factoryPlanner.customInput.loadMuseSpark')}
            </button>
            <button
              type="button"
              className="planner-btn is-primary"
              disabled={!canStartCustom}
              onClick={() => void startCustomJson()}
              data-testid="factory-planner-start-custom"
            >
              {t('factoryPlanner.customInput.submit')}
            </button>
            {chosenEntry?.document && (
              <button
                type="button"
                className="planner-btn"
                onClick={() => setCustomJson(JSON.stringify(chosenEntry.document, null, 2))}
              >
                {t('factoryPlanner.customInput.reset')}
              </button>
            )}
          </div>
        </details>

        {busy.length > 0 && <p className="factory-muted">{t('factoryPlanner.busy')}</p>}
        <h2>{t('factoryPlanner.history')}</h2>
        {runs.length === 0 && <p className="factory-muted">{t('factoryPlanner.empty')}</p>}
        <ul className="factory-planner-runs" data-testid="factory-planner-runs">
          {runs.map((run) => (
            <li key={run.id}>
              <a href={plannerHref(run.id, 'live')} aria-current={run.id === selected ? 'page' : undefined}>
                <strong>{run.requirements_id ?? run.id}</strong>
                <span className={`factory-planner-state is-${run.state}`}>{t(`factoryPlanner.state.${run.state}`)}</span>
                <small>{run.created ? new Date(run.created * 1000).toLocaleString() : run.id}</small>
              </a>
            </li>
          ))}
        </ul>
      </aside>

      <section className="factory-main" data-testid="factory-planner-main">
        {error && <div className="factory-error" role="alert">{error}</div>}
        {detail ? (
          <PlanView detail={detail} capsuleNameById={capsuleNameById} />
        ) : (
          <div className="factory-planner-view">
            <PipelineStepper detail={null} />
            <p className="factory-muted">{t('factoryPlanner.pick')}</p>
          </div>
        )}
      </section>
    </div>
  );
}

type StepState = 'done' | 'active' | 'error' | 'pending';

function PipelineStepper({ detail }: { detail: PlanDetail | null }) {
  const { i18n } = useTranslation();
  const t = useMemo(() => i18n.getFixedT('en'), [i18n]);
  const state = detail?.status.state;
  const lastRound = detail?.rounds[detail.rounds.length - 1];
  const isRunning = Boolean(state && LIVE.has(state));
  const phase = detail?.status.phase;

  const hasReq = Boolean(detail?.requirements || detail?.status.requirements_id);
  const hasSelection = Boolean(detail?.selection);
  const hasIr = Boolean(detail?.ir);
  const hasCompile = Boolean(detail?.derivation?.length || detail?.plan);
  const staticFailed = lastRound?.layer === 'static' || lastRound?.layer === 'ir' || lastRound?.layer === 'parse';
  const tlcFailed = lastRound?.layer === 'tla';
  const hasVerifiedJson = Boolean(detail?.outputs?.['graph.json']);
  const hasGraphTla = Boolean(detail?.outputs?.['graph.tla'] || detail?.graph_tla_info?.present);
  const hasDeliverable = hasVerifiedJson || hasGraphTla;
  const succeeded = state === 'succeeded';

  const steps: Array<{ id: string; title: string; state: StepState; detail: string }> = [
    {
      id: 'task_input',
      title: t('factoryPlanner.pipeline.taskInput'),
      state: hasReq ? 'done' : 'pending',
      detail: detail?.status.requirements_id ?? 'TaskInput JSON',
    },
    {
      id: 'selection',
      title: t('factoryPlanner.pipeline.selection'),
      state: hasSelection ? 'done' : isRunning && hasReq ? 'active' : 'pending',
      detail: detail?.selection
        ? `${detail.selection.candidates.length} cc`
        : 'CC Library',
    },
    {
      id: 'ir',
      title: t('factoryPlanner.pipeline.planIr'),
      state: hasIr ? 'done' : isRunning && phase === 'model' ? 'active' : state === 'rejected' ? 'error' : 'pending',
      detail: detail?.ir?.steps?.length ? `${detail.ir.steps.length} steps` : 'Autonomous Steps',
    },
    {
      id: 'compile',
      title: t('factoryPlanner.pipeline.compile'),
      state: hasCompile ? 'done' : isRunning && phase === 'static' ? 'active' : 'pending',
      detail: detail?.derivation ? `${detail.derivation.length} rules` : 'plan_compile.py',
    },
    {
      id: 'static',
      title: t('factoryPlanner.pipeline.staticChecks'),
      state: succeeded || hasDeliverable || (lastRound && !staticFailed)
        ? 'done'
        : staticFailed
          ? 'error'
          : isRunning && phase === 'static'
            ? 'active'
            : 'pending',
      detail: staticFailed ? 'Problems caught' : 'M1 Bridged + M2',
    },
    {
      id: 'tlc',
      title: t('factoryPlanner.pipeline.tlc'),
      state: detail?.verification?.passed || succeeded
        ? 'done'
        : tlcFailed
          ? 'error'
          : isRunning && phase === 'checking'
            ? 'active'
            : 'pending',
      detail: detail?.verification
        ? `${detail.verification.runs.map((r) => r.run).join(' + ')}`
        : 'Internal Safety + Delivery',
    },
    {
      id: 'handoff',
      title: t('factoryPlanner.pipeline.handoff'),
      state: succeeded && hasDeliverable ? 'done' : 'pending',
      detail: hasVerifiedJson
        ? 'graph.json ✓'
        : hasGraphTla
          ? 'graph.tla ✓'
          : 'graph.json',
    },
  ];

  return (
    <section className="planner-stepper" data-testid="factory-planner-pipeline" aria-label={t('factoryPlanner.pipeline.aria')}>
      {steps.map((step, idx) => (
        <div key={step.id} className={`planner-step is-${step.state}`}>
          <div className="planner-step-num">
            <span>0{idx + 1}</span>
            <span>{step.state === 'done' ? '✓' : step.state === 'error' ? '✗' : step.state === 'active' ? '●' : '○'}</span>
          </div>
          <div className="planner-step-title">{step.title}</div>
          <div className="planner-step-detail">{step.detail}</div>
        </div>
      ))}
    </section>
  );
}

function PlanView({
  detail,
  capsuleNameById,
}: {
  detail: PlanDetail;
  capsuleNameById: Map<string, string>;
}) {
  const { i18n } = useTranslation();
  const t = useMemo(() => i18n.getFixedT('en'), [i18n]);
  const { status } = detail;
  const graph = useMemo(() => (detail.graph ? detectGraph(detail.graph) : null), [detail.graph]);
  const caught = detail.rounds.filter((round) => round.problems.length > 0).length;
  const states = (detail.verification?.runs ?? []).reduce((sum, run) => sum + (run.distinct_states ?? 0), 0);
  const hasVerifiedJson = Boolean(detail.outputs['graph.json']);
  const hasGraphTla = Boolean(detail.outputs['graph.tla'] || detail.graph_tla_info?.present);
  const hasDeliverable = hasVerifiedJson || hasGraphTla;
  const soleOutputs = useMemo(() => {
    if (detail.outputs['graph.json']) {
      return [['graph.json', detail.outputs['graph.json']] as const];
    }
    if (detail.outputs['graph.tla']) {
      return [['graph.tla', detail.outputs['graph.tla']] as const];
    }
    return [];
  }, [detail.outputs]);

  return (
    <div className="factory-planner-view" data-testid="factory-planner-view">
      <PipelineStepper detail={detail} />

      <header className="factory-detail-header">
        <div>
          <p className="factory-story-kicker">{detail.id}</p>
          <h2>{status.requirements_id ?? detail.id}</h2>
        </div>
        <span className={`factory-planner-state is-${status.state}`} data-testid="factory-planner-state">
          {t(`factoryPlanner.state.${status.state}`)}
          {LIVE.has(status.state) && status.round ? ` · ${t('factoryPlanner.round', { n: status.round })}` : ''}
          {LIVE.has(status.state) && status.phase ? ` · ${t(`factoryPlanner.phase.${status.phase}`, status.phase)}` : ''}
        </span>
      </header>
      {status.error && <p className="factory-error" role="alert">{status.error}</p>}

      {status.state === 'succeeded' && (
        <section className="factory-planner-value" data-testid="factory-planner-value">
          <h3>{t('factoryPlanner.value.title')}</h3>
          <div className="factory-planner-tiles">
            <Tile label={t('factoryPlanner.value.nodes')} value={formatCount(status.nodes)} />
            <Tile label={t('factoryPlanner.value.rounds')} value={String(detail.rounds.length)} />
            <Tile label={t('factoryPlanner.value.caught')} value={String(caught)} />
            <Tile label={t('factoryPlanner.value.states')} value={formatCount(states)} />
            <Tile label={t('factoryPlanner.value.duration')} value={`${seconds(status.started, status.finished) ?? '—'} s`} />
          </div>
          {detail.verification && <Proof runs={detail.verification.runs} />}
        </section>
      )}

      {status.state === 'succeeded' && hasDeliverable && (
        <section className="planner-handoff-banner" data-testid="factory-planner-handoff">
          <div>
            <strong>{t('factoryPlanner.handoff.title')}</strong>
            <p className="factory-muted" style={{ margin: '4px 0 0' }}>
              {t('factoryPlanner.handoff.description')}
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
            {hasVerifiedJson ? (
              <a
                href={plannerApi.graphJsonUrl(detail.id)}
                download="graph.json"
                className="planner-btn is-primary"
                data-testid="factory-planner-download-graph-json"
              >
                <Download size={14} aria-hidden />
                {t('factoryPlanner.downloadGraphJson')}
              </a>
            ) : (
              <a
                href={plannerApi.graphTlaUrl(detail.id)}
                download="graph.tla"
                className="planner-btn is-primary"
                data-testid="factory-planner-download-graph-tla"
              >
                <Download size={14} aria-hidden />
                {t('factoryPlanner.downloadGraphTla')}
              </a>
            )}
            <a href={runHref()} className="planner-btn" data-testid="factory-planner-open-runs">
              {t('factoryPlanner.handoff.cta')}
              <ArrowRight size={14} aria-hidden />
            </a>
          </div>
        </section>
      )}

      {detail.selection && (
        <Decisions selection={detail.selection} ir={detail.ir} capsuleNameById={capsuleNameById} />
      )}
      {detail.derivation && detail.derivation.length > 0 && <DerivationLog entries={detail.derivation} />}
      {graph && (
        <section className="factory-planner-block">
          <h3>{t('factoryPlanner.graph')}</h3>
          <div className="factory-planner-graph"><GraphViewer graph={graph} /></div>
        </section>
      )}
      {detail.verification && <ExecutionContract model={detail.verification.execution_model} />}
      {detail.comparison && <ComparisonView comparison={detail.comparison} />}

      <section className="factory-planner-block">
        <h3>{t('factoryPlanner.rounds')}</h3>
        <ol className="factory-planner-rounds" data-testid="factory-planner-rounds">
          {detail.rounds.map((round) => <RoundView key={round.round} plan={detail.id} round={round} />)}
        </ol>
      </section>

      {hasGraphTla && <GraphTlaInspector planId={detail.id} info={detail.graph_tla_info} />}

      {status.state === 'succeeded' && soleOutputs.length > 0 && (
        <section className="factory-planner-block">
          <h3>{t('factoryPlanner.outputs')}</h3>
          <ul className="factory-planner-outputs">
            {soleOutputs.map(([name, path]) => (
              <li key={name} style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
                <code>{path}</code>
                {name === 'graph.json' && (
                  <a
                    href={plannerApi.graphJsonUrl(detail.id)}
                    download="graph.json"
                    className="planner-btn is-primary"
                    data-testid="factory-planner-download-output-graph-json"
                  >
                    <Download size={14} aria-hidden />
                    {t('factoryPlanner.downloadGraphJson')}
                  </a>
                )}
                {name === 'graph.tla' && (
                  <a href={plannerApi.graphTlaUrl(detail.id)} download="graph.tla" target="_blank" rel="noreferrer">
                    {t('factoryPlanner.downloadGraphTla')}
                  </a>
                )}
              </li>
            ))}
          </ul>
          <p className="factory-muted">{t('factoryPlanner.initHint')}</p>
        </section>
      )}
    </div>
  );
}

function Decisions({
  selection,
  ir,
  capsuleNameById,
}: {
  selection: Selection;
  ir: PlanIr | null;
  capsuleNameById: Map<string, string>;
}) {
  const { i18n } = useTranslation();
  const t = useMemo(() => i18n.getFixedT('en'), [i18n]);
  const chosen = new Map((ir?.selected_capsules ?? []).map((b) => [b.capsule, b]));
  const preflight = new Map((ir?.preflight ?? []).map((p) => [p.unit, p]));
  const selectedUnits = new Set(
    ir?.units?.map((u) => u.id)
      ?? (ir?.selected_capsules ?? []).map((s) => selection.candidates.find((c) => c.capsule === s.capsule)?.unit).filter(Boolean)
  );
  const shownRisks = selection.risks.filter((r) => selectedUnits.size === 0 || selectedUnits.has(r.unit));

  const renderCapsuleLink = (capsuleId: string) => {
    const resolvedName = capsuleNameById.get(capsuleId);
    return resolvedName ? (
      <a href={capsuleHref(resolvedName)} className="planner-capsule-link" title={capsuleId}>
        {capsuleId}
        <ExternalLink size={11} aria-hidden />
      </a>
    ) : (
      <code>{capsuleId}</code>
    );
  };

  return (
    <section className="factory-planner-block" data-testid="factory-planner-decisions">
      <h3>{t('factoryPlanner.decisions.title')}</h3>
      <p className="factory-muted">{t('factoryPlanner.decisions.lead')}</p>
      {ir?.unrealizable && (
        <p className="factory-error">{ir.unrealizable.why}</p>
      )}
      {ir?.steps && ir.steps.length > 0 && (
        <>
          <h4>{t('factoryPlanner.decisions.steps')}</h4>
          <table className="factory-planner-table">
            <thead>
              <tr>
                <th>{t('factoryPlanner.decisions.stepId')}</th>
                <th>{t('factoryPlanner.decisions.stepKind')}</th>
                <th>{t('factoryPlanner.decisions.stepDeps')}</th>
                <th>{t('factoryPlanner.decisions.stepCapsules')}</th>
                <th>{t('factoryPlanner.decisions.stepObjective')}</th>
              </tr>
            </thead>
            <tbody>
              {ir.steps.map((step) => (
                <tr key={step.id} className="factory-planner-picked">
                  <td><code>{step.id}</code></td>
                  <td><code>{step.kind}</code></td>
                  <td className="factory-muted">{step.depends_on?.length ? step.depends_on.join(', ') : '—'}</td>
                  <td>
                    {step.capsules?.length ? (
                      <div className="factory-planner-step-ccs">
                        {step.capsules.map((cid, idx) => (
                          <span key={`${step.id}-${cid}`}>
                            {idx > 0 ? ', ' : ''}
                            {renderCapsuleLink(cid)}
                          </span>
                        ))}
                      </div>
                    ) : '—'}
                  </td>
                  <td>{step.objective}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      <table className="factory-planner-table">
        <thead>
          <tr>
            <th>{t('factoryPlanner.decisions.candidates')}</th>
            <th>{t('factoryPlanner.decisions.choice')}</th>
          </tr>
        </thead>
        <tbody>
          {selection.candidates.map((c) => {
            const pick = chosen.get(c.capsule);
            return (
              <tr key={c.capsule} className={pick ? 'factory-planner-picked' : undefined}>
                <td>
                  {renderCapsuleLink(c.capsule)}{' '}
                  <span className="factory-muted">
                    {t('factoryPlanner.decisions.features', {
                      match: c.features.name_match, acceptance: c.features.acceptance ?? '—', files: c.features.files,
                    })}
                    {c.features.hardware.match === false ? ` · ⚠ ${c.features.hardware.detail}` : ''}
                  </span>
                </td>
                <td>{pick ? pick.why : '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {shownRisks.length > 0 && (
        <>
          <h4>{t('factoryPlanner.decisions.preflight')}</h4>
          <ul className="factory-planner-problems">
            {shownRisks.map((risk) => {
              const decision = preflight.get(risk.unit);
              return (
                <li key={risk.unit}>
                  <strong>{risk.unit}</strong>: {risk.detail} →{' '}
                  {decision ? `${decision.add ? t('factoryPlanner.decisions.add') : t('factoryPlanner.decisions.skip')} — ${decision.why}` : '—'}
                </li>
              );
            })}
          </ul>
        </>
      )}
      {selection.interference.length > 0 && (
        <>
          <h4>{t('factoryPlanner.decisions.interference')}</h4>
          <table className="factory-planner-table">
            <thead><tr><th>{t('factoryPlanner.decisions.pair')}</th><th>{t('factoryPlanner.decisions.files')}</th><th>{t('factoryPlanner.decisions.regions')}</th><th>{t('factoryPlanner.decisions.weight')}</th></tr></thead>
            <tbody>
              {selection.interference.map((pair) => (
                <tr key={`${pair.a}-${pair.b}`}>
                  <td>{pair.a} × {pair.b}</td>
                  <td>{pair.files.join(', ') || '—'}</td>
                  <td>{pair.regions.join(', ') || '—'}</td>
                  <td><strong>{pair.weight}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {Object.keys(selection.merge_options).length > 0 && (
        <>
          <h4>{t('factoryPlanner.decisions.merge')}</h4>
          <ul className="factory-planner-options">
            {Object.entries(selection.merge_options).map(([name, option]) => (
              <li key={name} className={ir?.merge?.option === name ? 'factory-planner-picked' : undefined}>
                <strong>{name}</strong> · {option.summary}{' '}
                <span className="factory-muted">{option.stages.map((s) => `${s.id}(${s.members.join(', ')})`).join(' → ')}</span>
                {ir?.merge?.option === name && <div>✓ {ir.merge.why}</div>}
              </li>
            ))}
          </ul>
        </>
      )}
      {ir?.units && ir.units.length > 0 && (
        <>
          <h4>{t('factoryPlanner.decisions.units')}</h4>
          <ul className="factory-planner-options">
            {ir.units.map((u) => (
              <li key={u.id}>
                <code>{u.id}</code>:{' '}
                {u.capsules.map((cid, idx) => (
                  <span key={cid}>
                    {idx > 0 ? ', ' : ''}
                    {renderCapsuleLink(cid)}
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </>
      )}
      {ir?.priority && ir.priority.length > 0 && (
        <>
          <h4>{t('factoryPlanner.decisions.priority')}</h4>
          <ul className="factory-planner-options">
            {ir.priority.map((pair, idx) => (
              <li key={`${pair.join('-')}-${idx}`}>{pair[0]} → {pair[1]}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function DerivationLog({ entries }: { entries: Array<{ node: string; rule: string; detail: string }> }) {
  const { i18n } = useTranslation();
  const t = useMemo(() => i18n.getFixedT('en'), [i18n]);
  return (
    <details className="factory-planner-block" data-testid="factory-planner-derivation">
      <summary><strong>{t('factoryPlanner.derivation.title', { count: entries.length })}</strong></summary>
      <p className="factory-muted">{t('factoryPlanner.derivation.lead')}</p>
      <table className="factory-planner-table">
        <thead>
          <tr>
            <th>{t('factoryPlanner.node')}</th>
            <th>{t('factoryPlanner.derivation.rule')}</th>
            <th>{t('factoryPlanner.derivation.detail')}</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry, idx) => (
            <tr key={`${entry.node}-${entry.rule}-${idx}`}>
              <td><code>{entry.node}</code></td>
              <td>{entry.rule}</td>
              <td>{entry.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="factory-planner-tile">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function Proof({ runs }: { runs: TlcRun[] }) {
  const { i18n } = useTranslation();
  const t = useMemo(() => i18n.getFixedT('en'), [i18n]);
  return (
    <div className="factory-planner-proof">
      {runs.map((run) => (
        <div key={run.run}>
          <p>
            <strong>{t(`factoryPlanner.tlcRun.${run.run}`)}</strong>{' · '}
            {t('factoryPlanner.tlcStats', { states: formatCount(run.distinct_states), seconds: run.seconds })}
          </p>
          <ul className="factory-planner-chips">
            {run.checked.map((name) => <li key={name} title={t(`factoryPlanner.property.${name}`, name)}>✓ {name}</li>)}
          </ul>
        </div>
      ))}
    </div>
  );
}

function ExecutionContract({ model }: { model: ExecutionModel }) {
  const { i18n } = useTranslation();
  const t = useMemo(() => i18n.getFixedT('en'), [i18n]);
  return (
    <section className="factory-planner-block" data-testid="factory-planner-contract">
      <h3>{t('factoryPlanner.contractTitle')}</h3>
      <p className="factory-muted">{t('factoryPlanner.maxParallel', { n: model.max_parallel })}</p>
      <table className="factory-planner-table">
        <thead><tr><th>{t('factoryPlanner.node')}</th><th>{t('factoryPlanner.limit')}</th><th>{t('factoryPlanner.exclusive')}</th></tr></thead>
        <tbody>
          {Object.keys(model.limits).map((node) => (
            <tr key={node}>
              <td><code>{node}</code></td>
              <td>{model.limits[node]}</td>
              <td>{(model.exclusive[node] ?? []).join(', ') || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function ComparisonView({ comparison }: { comparison: Comparison }) {
  const { i18n } = useTranslation();
  const t = useMemo(() => i18n.getFixedT('en'), [i18n]);
  const changed = comparison.rows.filter((row) => row.differences.length || row.reference !== row.planned);
  return (
    <section className="factory-planner-block" data-testid="factory-planner-comparison">
      <h3>{t('factoryPlanner.comparison.title')}</h3>
      <p className={comparison.structurally_equivalent ? 'factory-planner-ok' : 'factory-planner-warn'}>
        {comparison.structurally_equivalent ? t('factoryPlanner.comparison.equivalent') : t('factoryPlanner.comparison.different')}
      </p>
      {comparison.missing.length > 0 && <p>{t('factoryPlanner.comparison.missing')}: {comparison.missing.join(', ')}</p>}
      {comparison.extra.length > 0 && <p>{t('factoryPlanner.comparison.extra')}: {comparison.extra.join(', ')}</p>}
      {changed.length === 0 ? <p className="factory-muted">{t('factoryPlanner.comparison.none')}</p> : (
        <table className="factory-planner-table">
          <thead><tr><th>{t('factoryPlanner.comparison.reference')}</th><th>{t('factoryPlanner.comparison.planned')}</th><th>{t('factoryPlanner.comparison.differences')}</th></tr></thead>
          <tbody>
            {changed.map((row) => (
              <tr key={row.planned}>
                <td><code>{row.reference}</code></td>
                <td><code>{row.planned}</code></td>
                <td>{row.differences.map((d) => (
                  <div key={d.field}><strong>{d.field}</strong>: {JSON.stringify(d.reference)} → {JSON.stringify(d.planned)}</div>
                ))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function RoundView({ plan, round }: { plan: string; round: PlanRound }) {
  const { i18n } = useTranslation();
  const t = useMemo(() => i18n.getFixedT('en'), [i18n]);
  const [open, setOpen] = useState<'prompt' | 'reply' | null>(null);
  const [text, setText] = useState<RoundText | null>(null);
  const [error, setError] = useState('');
  const show = async (name: 'prompt' | 'reply') => {
    if (open === name) {
      setOpen(null);
      return;
    }
    setOpen(name);
    setText(null);
    setError('');
    try {
      setText(await plannerApi.roundText(plan, round.round, name));
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    }
  };
  const layer = round.error ? 'error' : round.layer ?? (round.finished ? 'passed' : 'pending');
  return (
    <li className={`factory-planner-round is-${layer}`} data-testid="factory-planner-round">
      <p>
        <strong>{t('factoryPlanner.round', { n: round.round })}</strong>{' · '}
        {t(`factoryPlanner.layer.${layer}`, layer)}
        {round.nodes ? ` · ${t('factoryPlanner.roundNodes', { n: round.nodes })}` : ''}
      </p>
      {round.error && <p className="factory-error">{round.error}</p>}
      {round.problems.length > 0 && (
        <>
          <p className="factory-muted">{t('factoryPlanner.problems')}</p>
          <ul className="factory-planner-problems">{round.problems.map((p) => <li key={p}>{p}</li>)}</ul>
        </>
      )}
      {round.warnings.length > 0 && (
        <ul className="factory-planner-warnings">{round.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
      )}
      {round.verification?.runs.map((run) => (
        <p key={run.run} className="factory-muted">
          TLC {t(`factoryPlanner.tlcRun.${run.run}`)} · {run.passed ? '✓' : '✗'} ·{' '}
          {t('factoryPlanner.tlcStats', { states: formatCount(run.distinct_states), seconds: run.seconds })}
        </p>
      ))}
      <div className="factory-planner-round-actions">
        {round.prompt_chars > 0 && (
          <button type="button" onClick={() => void show('prompt')} aria-pressed={open === 'prompt'}>{t('factoryPlanner.viewPrompt')}</button>
        )}
        {round.reply_chars > 0 && (
          <button type="button" onClick={() => void show('reply')} aria-pressed={open === 'reply'}>{t('factoryPlanner.viewReply')}</button>
        )}
      </div>
      {open && error && <p className="factory-error">{error}</p>}
      {open && text && <pre className="factory-planner-text">{text.text}</pre>}
    </li>
  );
}
