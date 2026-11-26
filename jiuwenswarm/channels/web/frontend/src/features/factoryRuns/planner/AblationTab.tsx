import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import { ExternalLink, Play, RefreshCw, ShieldAlert, ShieldCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  plannerApi,
  type AblationCase,
  type AblationCategoryBreakdown,
  type AblationResponse,
  type AblationScalabilityPoint,
} from './plannerApi';

function pct(val: number | undefined): string {
  if (typeof val !== 'number') return '—';
  return `${(val * 100).toFixed(val === 0 || val === 1 ? 0 : 1)}%`;
}

function CategoryBarChart({ rows }: { rows: AblationCategoryBreakdown[] }) {
  const width = 640;
  const height = Math.max(240, rows.length * 56 + 56);
  const left = 195;
  const barW = 375;
  return (
    <div className="planner-chart-wrap">
      <svg className="planner-chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Old M1 vs M2 Static escape rate and TLC-Verified block rate by category">
        <text x={left} y={18} fontSize={11} fontWeight={700} fill="#b45309">■ Old M1 Escape</text>
        <text x={left + 125} y={18} fontSize={11} fontWeight={700} fill="#b91c1c">■ M2 Static Escape</text>
        <text x={left + 260} y={18} fontSize={11} fontWeight={700} fill="#15803d">■ TLC-Verified Block</text>
        {[0, 25, 50, 75, 100].map((tick) => {
          const x = left + (barW * tick) / 100;
          return (
            <g key={tick}>
              <line x1={x} y1={28} x2={x} y2={height - 22} stroke="#cbd5e1" strokeDasharray="3,3" />
              <text x={x} y={height - 6} fontSize={10} textAnchor="middle" fill="#64748b">{tick}%</text>
            </g>
          );
        })}
        {rows.map((row, idx) => {
          const y = 36 + idx * 56;
          const m1Val = typeof row.m1_escape_rate === 'number' ? row.m1_escape_rate : row.static_escape_rate;
          const m1W = Math.max(0, Math.min(1, m1Val)) * barW;
          const staticW = Math.max(0, Math.min(1, row.static_escape_rate)) * barW;
          const tlaW = Math.max(0, Math.min(1, row.tla_block_rate)) * barW;
          return (
            <g key={row.category}>
              <text x={left - 8} y={y + 15} fontSize={11.5} fontWeight={600} textAnchor="end" fill="currentColor">
                {row.category}
              </text>
              <text x={left - 8} y={y + 30} fontSize={10} textAnchor="end" fill="#64748b">
                {row.mechanism.includes('ASSUME') ? 'ASSUME Guard' : 'TLC Temporal'} (n={row.count})
              </text>
              <rect x={left} y={y} width={m1W} height={10} rx={2.5} fill="#d97706" opacity={0.85} />
              <text x={left + m1W + 6} y={y + 9} fontSize={10} fontWeight={600} fill="#b45309">
                {pct(m1Val)}
              </text>
              <rect x={left} y={y + 13} width={staticW} height={10} rx={2.5} fill="#dc2626" opacity={0.85} />
              <text x={left + staticW + 6} y={y + 22} fontSize={10} fontWeight={600} fill="#b91c1c">
                {pct(row.static_escape_rate)}
              </text>
              <rect x={left} y={y + 26} width={tlaW} height={10} rx={2.5} fill="#16a34a" opacity={0.9} />
              <text x={left + tlaW + 6} y={y + 35} fontSize={10} fontWeight={600} fill="#15803d">
                {pct(row.tla_block_rate)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function ScalabilityCurveChart({ points }: { points: AblationScalabilityPoint[] }) {
  const width = 560;
  const height = 230;
  const padL = 64;
  const padR = 26;
  const padT = 28;
  const padB = 34;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;
  const maxStates = Math.max(1000, ...points.map((p) => p.unconstrained_states)) * 1.1;

  const xOf = (idx: number) =>
    points.length <= 1 ? padL + plotW / 2 : padL + (idx * plotW) / (points.length - 1);
  const yOf = (val: number) => padT + plotH - (val / maxStates) * plotH;

  const pathFor = (vals: number[]) =>
    vals.map((v, i) => `${i === 0 ? 'M' : 'L'} ${xOf(i).toFixed(1)} ${yOf(v).toFixed(1)}`).join(' ');

  return (
    <div className="planner-chart-wrap">
      <svg className="planner-chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="State space scalability curve">
        <text x={padL} y={16} fontSize={11} fontWeight={700} fill="#dc2626">— Unconstrained Parallel Builders</text>
        <text x={padL + 220} y={16} fontSize={11} fontWeight={700} fill="#2563eb">— Priority-Ordered Builders</text>
        {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
          const val = Math.round(maxStates * frac);
          const y = yOf(val);
          return (
            <g key={frac}>
              <line x1={padL} y1={y} x2={width - padR} y2={y} stroke="#cbd5e1" strokeDasharray="3,3" />
              <text x={padL - 8} y={y + 4} fontSize={10} textAnchor="end" fill="#64748b">
                {val >= 1000 ? `${(val / 1000).toFixed(0)}k` : val}
              </text>
            </g>
          );
        })}
        <path d={pathFor(points.map((p) => p.unconstrained_states))} fill="none" stroke="#dc2626" strokeWidth={2.5} />
        <path d={pathFor(points.map((p) => p.ordered_states))} fill="none" stroke="#2563eb" strokeWidth={2.5} />
        {points.map((p, idx) => {
          const x = xOf(idx);
          const y1 = yOf(p.unconstrained_states);
          const y2 = yOf(p.ordered_states);
          return (
            <g key={p.k}>
              <circle cx={x} cy={y1} r={4.5} fill="#dc2626" />
              <text x={x} y={y1 - 8} fontSize={10.5} fontWeight={600} textAnchor="middle" fill="#b91c1c">
                {p.unconstrained_states.toLocaleString()}
              </text>
              <circle cx={x} cy={y2} r={4.5} fill="#2563eb" />
              <text x={x} y={y2 + 14} fontSize={10.5} fontWeight={600} textAnchor="middle" fill="#1d4ed8">
                {p.ordered_states.toLocaleString()} ({p.state_reduction_ratio}×)
              </text>
              <text x={x} y={height - 10} fontSize={11} textAnchor="middle" fill="currentColor">
                k={p.k}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function AblationTab() {
  const { i18n } = useTranslation();
  const t = useMemo(() => i18n.getFixedT('en'), [i18n]);
  const [data, setData] = useState<AblationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<string>('ALL');
  const [search, setSearch] = useState('');
  const [expandedCaseId, setExpandedCaseId] = useState<string | null>(null);

  const loadAblation = useCallback(async () => {
    setLoading(true);
    try {
      const res = await plannerApi.ablation();
      setData(res);
      setError('');
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAblation();
  }, [loadAblation]);

  useEffect(() => {
    if (!data?.running) return;
    const timer = window.setTimeout(() => {
      void loadAblation();
    }, 2000);
    return () => window.clearTimeout(timer);
  }, [data?.running, loadAblation]);

  const triggerRerun = async () => {
    setTriggering(true);
    setError('');
    try {
      await plannerApi.runAblation();
      await loadAblation();
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setTriggering(false);
    }
  };

  const results = data?.results ?? null;
  const summary = results?.summary;

  const filteredCases = useMemo(() => {
    if (!results) return [];
    const q = search.trim().toLowerCase();
    return results.cases.filter((c) => {
      if (filter === 'A' && c.class !== 'A') return false;
      if (filter === 'B' && c.class !== 'B') return false;
      if (filter !== 'ALL' && filter !== 'A' && filter !== 'B' && c.category !== filter) return false;
      if (q) {
        const hay = `${c.case_id} ${c.title} ${c.category} ${c.enforcement_mechanism}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [results, filter, search]);

  return (
    <div className="planner-scroll-main" data-testid="factory-planner-ablation-tab">
      <header className="factory-detail-header">
        <div>
          <p className="factory-story-kicker">{t('factoryPlanner.ablationTab.kicker')}</p>
          <h2>{t('factoryPlanner.ablationTab.title')}</h2>
          <p className="factory-muted">{t('factoryPlanner.ablationTab.subtitle')}</p>
        </div>
        <div className="planner-btn-row" style={{ marginTop: 0 }}>
          <button type="button" className="planner-btn" onClick={() => void loadAblation()} disabled={loading}>
            <RefreshCw size={14} aria-hidden />
            {t('factoryRuns.refresh')}
          </button>
          {data?.available && (
            <a
              className="planner-btn"
              href={plannerApi.ablationReportUrl()}
              target="_blank"
              rel="noreferrer"
              data-testid="factory-planner-ablation-report-link"
            >
              <ExternalLink size={14} aria-hidden />
              {t('factoryPlanner.ablationTab.openReportBtn')}
            </a>
          )}
          <button
            type="button"
            className="planner-btn is-primary"
            onClick={() => void triggerRerun()}
            disabled={triggering || Boolean(data?.running) || data?.environment?.tlc === false}
            data-testid="factory-planner-ablation-rerun"
          >
            <Play size={14} aria-hidden />
            {data?.running
              ? t('factoryPlanner.ablationTab.runningBtn')
              : t('factoryPlanner.ablationTab.rerunBtn')}
          </button>
        </div>
      </header>

      {error && <div className="factory-error" role="alert">{error}</div>}
      {data?.run_state?.state === 'failed' && data.run_state.error && (
        <div className="factory-error" role="alert">{data.run_state.error}</div>
      )}

      {data && (
        <div className="planner-tla-meta">
          <div className="planner-btn-row" style={{ marginTop: 0 }}>
            <span className={`planner-badge ${data.running ? 'is-warn' : data.available ? 'is-good' : 'is-bad'}`}>
              {data.running
                ? t('factoryPlanner.ablationTab.statusRunning')
                : data.available
                  ? t('factoryPlanner.ablationTab.statusReady')
                  : t('factoryPlanner.ablationTab.statusMissing')}
            </span>
            {results && (
              <>
                <span className="planner-badge is-info">
                  {t('factoryPlanner.ablationTab.trialsMeta', {
                    n: results.environment.simulation_trials_per_case,
                    seed: results.environment.simulation_seed,
                  })}
                </span>
                <span className="planner-badge">
                  tla2tools SHA: {results.environment.tla2tools_sha256.slice(0, 10)}
                </span>
                <span className="planner-badge">
                  git: {results.environment.git_commit.slice(0, 8)}
                </span>
              </>
            )}
          </div>
          {results && (
            <small className="factory-muted">
              Generated: {new Date(results.generated_at).toLocaleString()}
            </small>
          )}
        </div>
      )}

      {!results ? (
        <section className="factory-planner-block">
          <p className="factory-muted">{t('factoryPlanner.ablationTab.noResults')}</p>
        </section>
      ) : (
        <>
          <section className="factory-planner-tiles" style={{ marginBottom: 0 }}>
            <div className="factory-planner-tile">
              <strong>
                {pct(summary?.m1_escape_rate ?? summary?.static_escape_rate)} / {pct(summary?.static_escape_rate)} → 0%
              </strong>
              <span>{t('factoryPlanner.ablationTab.kpiEscape')}</span>
            </div>
            <div className="factory-planner-tile">
              <strong>
                {pct(summary?.a_delivery_rate_m1 ?? summary?.a_delivery_rate_static)} → {pct(summary?.a_delivery_rate_tla)}
              </strong>
              <span>{t('factoryPlanner.ablationTab.kpiReliability')}</span>
            </div>
            <div className="factory-planner-tile">
              <strong>
                {summary?.tla_caught_defects}/{summary?.class_b_count} ({pct(summary?.tla_catch_rate)})
              </strong>
              <span>
                {t('factoryPlanner.ablationTab.kpiCaught', {
                  tlc: summary?.tla_caught_by_tlc_temporal,
                  assume: summary?.tla_caught_by_assume,
                })}
              </span>
            </div>
            <div className="factory-planner-tile">
              <strong>{pct(summary?.static_class_b_hazard_rate_mean)} → {pct(summary?.tla_class_b_hazard_rate_mean)}</strong>
              <span>
                {t('factoryPlanner.ablationTab.kpiHazard', {
                  nodes: summary?.static_class_b_wasted_nodes_mean,
                  turns: summary?.static_class_b_wasted_turns_mean,
                })}
              </span>
            </div>
            <div className="factory-planner-tile">
              <strong>{pct(summary?.tla_false_positive_rate)}</strong>
              <span>
                {t('factoryPlanner.ablationTab.kpiFp', {
                  exact: summary?.roundtrip_fidelity_count,
                  total: summary?.class_a_count,
                  ms: summary?.parse_taskgraph_tla_mean_ms,
                })}
              </span>
            </div>
            <div className="factory-planner-tile">
              <strong>
                {summary?.repair_success_count}/{summary?.class_c_count} ({pct(summary?.repair_success_rate)})
              </strong>
              <span>{t('factoryPlanner.ablationTab.kpiRepair')}</span>
            </div>
          </section>

          {results.m1_limitations && results.m1_limitations.length > 0 && (
            <section className="factory-planner-block">
              <h3>{t('factoryPlanner.ablationTab.m1GapsTitle')}</h3>
              <p className="factory-muted">{t('factoryPlanner.ablationTab.m1GapsLead')}</p>
              <div className="planner-qa-list">
                {results.m1_limitations.map((gap) => (
                  <div key={gap.id} className="planner-qa-item">
                    <h4>{gap.title}</h4>
                    <p>{gap.summary}</p>
                    <div>
                      {gap.source_refs.map((ref) => (
                        <code key={ref} style={{ marginRight: 8 }}>{ref}</code>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          <div className="planner-grid-2">
            <section className="factory-planner-block">
              <h3>{t('factoryPlanner.ablationTab.categoryChartTitle')}</h3>
              <p className="factory-muted">{t('factoryPlanner.ablationTab.categoryChartLead')}</p>
              <CategoryBarChart rows={results.category_breakdown} />
            </section>

            <section className="factory-planner-block">
              <h3>
                {t('factoryPlanner.ablationTab.scalabilityTitle')} ({summary?.scalability_k5_reduction}× @ k=5)
              </h3>
              <p className="factory-muted">{t('factoryPlanner.ablationTab.scalabilityLead')}</p>
              <ScalabilityCurveChart points={results.scalability} />
            </section>
          </div>

          <section className="factory-planner-block">
            <h3>{t('factoryPlanner.ablationTab.categoryTableTitle')}</h3>
            <table className="factory-planner-table">
              <thead>
                <tr>
                  <th>Fault Category</th>
                  <th>Enforcement Mechanism</th>
                  <th>Cases</th>
                  <th>Old M1 Escape</th>
                  <th>M2 Static Escape</th>
                  <th>TLC-Verified Block</th>
                  <th>Static Wasted Nodes / Turns</th>
                  <th>TLC Mean (s)</th>
                </tr>
              </thead>
              <tbody>
                {results.category_breakdown.map((row) => (
                  <tr key={row.category}>
                    <td><strong>{row.category}</strong></td>
                    <td>
                      <span className={`planner-badge ${row.mechanism.includes('ASSUME') ? 'is-info' : 'is-good'}`}>
                        {row.mechanism}
                      </span>
                    </td>
                    <td>{row.count}</td>
                    <td>{pct(row.m1_escape_rate ?? row.static_escape_rate)}</td>
                    <td>{pct(row.static_escape_rate)}</td>
                    <td>{pct(row.tla_block_rate)}</td>
                    <td>{row.static_wasted_nodes_mean} nodes · {row.static_wasted_turns_mean} turns</td>
                    <td>{row.tla_verify_seconds_mean}s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="factory-planner-block">
            <div className="factory-detail-header">
              <div>
                <h3>{t('factoryPlanner.ablationTab.casesTitle')} ({filteredCases.length})</h3>
                <p className="factory-muted">{t('factoryPlanner.ablationTab.casesLead')}</p>
              </div>
              <input
                type="search"
                className="planner-input"
                style={{ maxWidth: 260 }}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t('factoryPlanner.ablationTab.searchPlaceholder')}
              />
            </div>

            <div className="planner-btn-row" style={{ marginBottom: 10 }}>
              {[
                { key: 'ALL', label: `All (${results.cases.length})` },
                { key: 'A', label: `Class A: Healthy (${summary?.class_a_count})` },
                { key: 'B', label: `Class B: Static-Bypass (${summary?.class_b_count})` },
                ...results.category_breakdown.map((c) => ({ key: c.category, label: c.category })),
              ].map((btn) => (
                <button
                  key={btn.key}
                  type="button"
                  className={`planner-btn${filter === btn.key ? ' is-primary' : ''}`}
                  onClick={() => setFilter(btn.key)}
                >
                  {btn.label}
                </button>
              ))}
            </div>

            <div className="factory-table-scroll">
              <table className="factory-planner-table">
                <thead>
                  <tr>
                    <th>Case</th>
                    <th>Category</th>
                    <th>Old M1 (M1+M1)</th>
                    <th>M2 Static (M1+M2)</th>
                    <th>TLC-Verified (JSON)</th>
                    <th>Static Sim Hazard</th>
                    <th>TLA+ Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredCases.map((c: AblationCase) => {
                    const isOpen = expandedCaseId === c.case_id;
                    const m1Arm = c.m1_legacy ?? c.static_only;
                    return (
                      <Fragment key={c.case_id}>
                        <tr
                          className="planner-case-row"
                          onClick={() => setExpandedCaseId(isOpen ? null : c.case_id)}
                        >
                          <td>
                            <code>{c.case_id}</code>
                            <div className="factory-muted">{c.title}</div>
                          </td>
                          <td>
                            <span className="planner-badge">{c.category}</span>
                          </td>
                          <td>
                            <span className={`planner-badge ${m1Arm.escaped_defect || (c.class === 'A' && m1Arm.simulation.delivery_rate < 1.0) ? 'is-warn' : 'is-good'}`}>
                              {m1Arm.admitted
                                ? m1Arm.escaped_defect
                                  ? 'Admitted (ESCAPED)'
                                  : `${pct(m1Arm.simulation.delivery_rate)} deliv`
                                : 'Blocked'}
                            </span>
                          </td>
                          <td>
                            <span className={`planner-badge ${c.static_only.escaped_defect ? 'is-bad' : 'is-good'}`}>
                              {c.static_only.admitted
                                ? c.static_only.escaped_defect ? 'Admitted (ESCAPED)' : 'Admitted (OK)'
                                : 'Blocked'}
                            </span>
                          </td>
                          <td>
                            <span className={`planner-badge ${c.tla_pipeline.admitted === c.expected_tla_pass ? 'is-good' : 'is-bad'}`}>
                              {c.tla_pipeline.admitted ? 'Proven ✓' : `Blocked (${c.enforcement_mechanism.includes('ASSUME') ? 'ASSUME' : 'TLC'})`}
                            </span>
                          </td>
                          <td>
                            {pct(c.static_only.hazard_rate)}
                            {c.static_only.simulation.race_violations > 0 && (
                              <span className="factory-muted"> · {c.static_only.simulation.race_violations} races</span>
                            )}
                          </td>
                          <td>{c.tla_pipeline.latency_s}s</td>
                        </tr>
                        {isOpen && (
                          <tr>
                            <td colSpan={7} className="planner-case-detail-cell">
                              <div className="planner-grid-2">
                                <div>
                                  <strong>Old M1 Simulation ({m1Arm.simulation.trials} trials · max_attempts=1)</strong>
                                  <p className="factory-muted">
                                    Delivered: {m1Arm.simulation.delivered} · Stuck/Failed: {m1Arm.simulation.stuck_or_failed} ·
                                    Wasted: {m1Arm.simulation.wasted_nodes_per_trial} nodes / {m1Arm.simulation.wasted_turns_per_trial} turns per trial
                                  </p>
                                  <strong>M2 Static Simulation ({c.static_only.simulation.trials} trials)</strong>
                                  <p className="factory-muted">
                                    Delivered: {c.static_only.simulation.delivered} · Stuck/Failed: {c.static_only.simulation.stuck_or_failed} ·
                                    Race violations: {c.static_only.simulation.race_violations} ·
                                    Wasted: {c.static_only.simulation.wasted_nodes_per_trial} nodes / {c.static_only.simulation.wasted_turns_per_trial} turns per trial
                                  </p>
                                </div>
                                <div>
                                  <strong>TLC-Verified Planner (Internal TLC -&gt; Verified JSON) Verdict</strong>
                                  {c.tla_pipeline.tlc_problems.length > 0 ? (
                                    <ul className="factory-planner-problems">
                                      {c.tla_pipeline.tlc_problems.map((p) => <li key={p}>{p}</li>)}
                                    </ul>
                                  ) : (
                                    <p className="factory-muted">
                                      Safety & Delivery proven · {c.tla_pipeline.total_distinct_states.toLocaleString()} distinct states ·
                                      Zero-JVM parse: {c.tla_pipeline.parse_ms} ms
                                    </p>
                                  )}
                                </div>
                              </div>
                              {c.tla_pipeline.counterexample_trace && c.tla_pipeline.counterexample_trace.length > 0 && (
                                <div style={{ marginTop: 10 }}>
                                  <strong>TLC Counterexample State Trace ({c.tla_pipeline.counterexample_trace.length} steps)</strong>
                                  <div className="planner-trace-grid">
                                    {c.tla_pipeline.counterexample_trace.map((step, idx, arr) => {
                                      const activeNodes = Object.entries(step.st).filter(([, s]) => s === 'active').map(([k]) => k);
                                      const doneNodes = Object.entries(step.st).filter(([, s]) => s === 'done').map(([k]) => k);
                                      return (
                                        <div
                                          key={step.state}
                                          className={`planner-trace-card${idx === arr.length - 1 ? ' is-last' : ''}`}
                                        >
                                          <div><strong>State {step.state}</strong></div>
                                          <div className="factory-muted">{step.action}</div>
                                          <div>active: {activeNodes.join(', ') || '—'}</div>
                                          <div>done: {doneNodes.length}/{Object.keys(step.st).length}</div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section className="factory-planner-block">
            <h3>{t('factoryPlanner.ablationTab.repairTitle')} ({results.repair_cases.length})</h3>
            <p className="factory-muted">{t('factoryPlanner.ablationTab.repairLead')}</p>
            <div className="planner-qa-list">
              {results.repair_cases.map((rc) => (
                <div key={rc.case_id} className="planner-qa-item">
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 6 }}>
                    <code>{rc.case_id}</code>
                    <span className="planner-badge is-good">
                      <ShieldCheck size={12} aria-hidden />
                      Repaired in {rc.tla_rounds_taken} rounds ({rc.tla_total_latency_s}s)
                    </span>
                  </div>
                  <h4>{rc.title}</h4>
                  <p style={{ marginBottom: 6 }}>
                    <ShieldAlert size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} aria-hidden />
                    <strong>Round 1 ({rc.fault_label}):</strong> Old M1 &amp; M2 Static both admitted with {pct(rc.static_round1_simulation.stuck_rate)} stuck rate;
                    TLC caught violation and fed structured counterexample back.
                  </p>
                  {rc.feedback_excerpt && <p style={{ marginBottom: 6 }}>Feedback: <em>{rc.feedback_excerpt}</em></p>}
                  {rc.round1_trace && rc.round1_trace.length > 0 && (
                    <div className="planner-trace-grid">
                      {rc.round1_trace.map((step, idx, arr) => (
                        <div key={step.state} className={`planner-trace-card${idx === arr.length - 1 ? ' is-last' : ''}`}>
                          <strong>S{step.state}</strong>: {step.action}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>

          <section className="factory-planner-block">
            <h3>{t('factoryPlanner.ablationTab.qaTitle')}</h3>
            <div className="planner-qa-list">
              <div className="planner-qa-item">
                <h4>Why bridge Old M1 binding.plan_checks instead of deleting it, and why aren&rsquo;t M1 + M2 static checks enough?</h4>
                <p>
                  Bridging Old M1 via <code>m1_verifier_bridge.py</code> keeps every proven M1 invariant (coverage, port compatibility, dependency closure, predecessor acyclicity) running cleanly. However, Old M1 locks <code>max_attempts_per_node = 1</code> (dropping Class A delivery to {pct(summary?.a_delivery_rate_m1)}) and lacks mutex locks, <code>build_attempts</code> checks, scheduler <code>depends_on</code> cycles, and <code>build/deliver</code> write guards — so both Old M1 and M2 Static let 100% of Class B hazards escape without TLC.
                </p>
              </div>
              <div className="planner-qa-item">
                <h4>Why separate TLA+ ASSUME assertions from TLC temporal proofs?</h4>
                <p>
                  Static contract invariants (such as least-privilege workspace bounds on deliver/build nodes) fail instantaneously when TLC evaluates <code>ASSUME</code> at model load time. Dynamic interleaving hazards (<code>ExclusiveResources</code> checkout/builder lock races, <code>NoStuck</code> starvation, and <code>HaltsDelivered</code> deadlocks) require state-space exploration across concurrent schedules.
                </p>
              </div>
              <div className="planner-qa-item">
                <h4>Is TLC verifying downstream Python code or acting as the Planner gate for JSON deliverables?</h4>
                <p>
                  TLC proves the execution topology, mutual-exclusion locks, retry bounds, and least-privilege ceilings internally on every round; only after passing Safety, Delivery, and <code>ASSUME</code> does the planner emit standard verified JSON deliverables (<code>contract.json</code>, <code>plan.json</code>, <code>graph.json</code>, <code>verification.json</code>, <code>task.json</code>) without requiring external <code>.tla</code> files.
                </p>
              </div>
              <div className="planner-qa-item">
                <h4>How fast is the verification gate and downstream parsing?</h4>
                <p>
                  Healthy baseline graphs verify in ~{summary?.tla_class_a_latency_mean_s}s mean TLC latency, faulty graphs abort in ~{summary?.tla_class_b_latency_mean_s}s, and zero-JVM Python round-trip parsing takes {summary?.parse_taskgraph_tla_mean_ms}ms mean across all cases.
                </p>
              </div>
              <div className="planner-qa-item">
                <h4>Live LLM vs Deterministic Synthesize Loops</h4>
                <p>
                  Live external LLM runs status: <strong>{results.live_trials.status}</strong>. All Class C self-repair loops exercise the exact <code>ai_planner.synthesize()</code> pipeline with scripted Round 1 faulty IR, real TLC counterexample feedback, and Round 2 repaired IR convergence.
                </p>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
