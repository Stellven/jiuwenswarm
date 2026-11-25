/**
 * How a task graph node is checked: the node contract's CCs and verifiers, each
 * output's latest host `node_check` observation and the done-gate statement.
 * Input is the compact `node_checks` block of GET /runs/{id} (factory_http.node_check_view);
 * the statements mirror node_check.pending, the host's done rule.
 */

export type VerifierCheck = { name?: string; status?: string; stage?: string; detail?: string };
export type ReviewFinding = { severity?: string; file?: string; line?: number | null; problem?: string };
export type CheckRow = {
  obs_id: string;
  created?: number;
  state?: string;
  passed: boolean;
  reason?: string;
  kind?: string;
  same_settings: boolean;
  superseded: boolean;
  cited: boolean;
  reused_from?: string | null;
  seconds?: number | null;
  verifier?: {
    cc?: string;
    capability?: string;
    state?: string;
    passed?: boolean;
    stage_reached?: string | null;
    reason?: string;
    checks: VerifierCheck[];
  } | null;
  review?: {
    verdict?: string | null;
    summary?: string;
    passed?: boolean;
    reason?: string;
    reviewer?: string;
    packet_artifact?: string;
    reply_artifact?: string;
    findings: ReviewFinding[];
  } | null;
  found?: string[] | null;
  artifacts?: string[];
};
export type CheckOutput = {
  name: string;
  kind?: string | null;
  required: boolean;
  declared: boolean;
  verifier?: string | null;
  stage?: string | null;
  review: boolean;
  inputs?: Record<string, unknown> | null;
  criteria?: string[];
  checks: CheckRow[];
};
export type NodeCheckView = {
  node_contract?: string | null;
  objective?: string | null;
  helpful_ccs: string[];
  capability?: string | null;
  requirement_ids?: string[];
  outputs: CheckOutput[];
  reopened_at?: number | null;
};
export type NodeCheckIndex = Record<string, NodeCheckView>;
export type PlanNode = {
  node_id?: unknown;
  state?: unknown;
  hold?: unknown;
  retry_from?: unknown;
  attempt_ids?: unknown;
  reason?: unknown;
};

/** The capsule verifiers' evidence ladder, weakest first (node_check.STAGES). */
export const STAGES = ['fixture', 'native CC execution', 'compile', 'runtime acceptance', 'hardware measurement'];

export type OutputStatus = 'passed' | 'failed' | 'running' | 'unchecked' | 'stale';
export type OutputSummary = {
  output: CheckOutput;
  status: OutputStatus;
  latest?: CheckRow;
  /** Why this output keeps the node open; undefined when it does not. */
  blocking?: string;
  stageRequired?: string;
  stageReached?: string;
  /** undefined when no stage is required or no verifier result exists. */
  stageMet?: boolean;
  /** Verifier check list of the latest check, failures first. */
  verifierChecks: VerifierCheck[];
  findings: ReviewFinding[];
  history: CheckRow[];
};
export type GateStatement = { kind: 'closed' | 'open' | 'held' | 'unchecked'; text: string };
export type CheckBadge = { tone: 'passed' | 'pending' | 'failed' | 'running' | 'held'; text: string };

const text = (value: unknown) => (typeof value === 'string' && value.trim() ? value.trim() : undefined);

function statusRank(status: string | undefined) {
  const value = (status ?? '').toLowerCase();
  if (['fail', 'failed', 'error', 'blocker'].includes(value)) return 0;
  if (['pass', 'passed', 'ok'].includes(value)) return 2;
  return 1;
}

const severityRank = (value: string | undefined) => {
  const index = ['blocker', 'major', 'minor'].indexOf(value ?? '');
  return index < 0 ? 3 : index;
};

export function stageMet(required: string | null | undefined, reached: string | null | undefined) {
  if (!required) return undefined;
  if (!reached) return false;
  const want = STAGES.indexOf(required);
  const got = STAGES.indexOf(reached);
  return want >= 0 && got >= want;
}

export function summarizeOutput(output: CheckOutput, nodeDone = false): OutputSummary {
  const history = [...output.checks];
  const latest = history[history.length - 1];
  const verifierChecks = [...(latest?.verifier?.checks ?? [])]
    .map((check, index) => ({ check, index }))
    .sort((a, b) => statusRank(a.check.status) - statusRank(b.check.status) || a.index - b.index)
    .map(({ check }) => check);
  const findings = [...(latest?.review?.findings ?? [])].sort((a, b) => severityRank(a.severity) - severityRank(b.severity));
  const base = {
    output,
    latest,
    stageRequired: output.stage ?? undefined,
    stageReached: latest?.verifier?.stage_reached ?? undefined,
    stageMet: latest?.verifier ? stageMet(output.stage, latest.verifier.stage_reached) : undefined,
    verifierChecks,
    findings,
    history,
  };
  const name = output.name;
  if (!latest) return { ...base, status: 'unchecked', blocking: `output ${name} has no node check yet` };
  if (latest.superseded)
    return { ...base, status: 'stale', blocking: `output ${name} needs a fresh check after the operator reopened the node` };
  if (latest.state !== 'finished') return { ...base, status: 'running', blocking: `output ${name}: check running` };
  if (output.declared && !latest.same_settings)
    return { ...base, status: 'stale', blocking: `output ${name}: the latest check used other check settings` };
  if (!latest.passed)
    return { ...base, status: 'failed', blocking: `output ${name} failed check: ${latest.reason || 'no reason recorded'}` };
  if (!latest.cited && !nodeDone)
    return { ...base, status: 'passed', blocking: `output ${name} passed; the node has yet to cite check ${latest.obs_id}` };
  return { ...base, status: 'passed' };
}

export function nodeHold(node: PlanNode | undefined) {
  return text(node?.hold);
}

export function summarizeNode(view: NodeCheckView | undefined, node: PlanNode | undefined) {
  const done = node?.state === 'done';
  const outputs = (view?.outputs ?? []).map((output) => summarizeOutput(output, done));
  return { outputs, gate: gateStatement(view, node, outputs), badge: checkBadge(view, node, outputs) };
}

export function gateStatement(
  view: NodeCheckView | undefined,
  node: PlanNode | undefined,
  outputs = (view?.outputs ?? []).map((output) => summarizeOutput(output, node?.state === 'done')),
): GateStatement | undefined {
  const hold = nodeHold(node);
  if (hold) return { kind: 'held', text: `held by operator: ${hold}` };
  if (!view) return undefined;
  const required = outputs.filter((row) => row.output.required);
  if (!required.length) return { kind: 'unchecked', text: 'no required output is checked; the host gate does not apply' };
  const passed = required.filter((row) => row.status === 'passed');
  const all = `${required.length === 1 ? 'the' : `all ${required.length}`} required output${required.length === 1 ? '' : 's'}`;
  if (node?.state === 'done') {
    const later = required.find((row) => row.status !== 'passed');
    return later
      ? { kind: 'closed', text: `closed earlier; since then ${later.blocking}` }
      : { kind: 'closed', text: `closed: ${all} passed ${required.length === 1 ? 'its' : 'their'} latest check` };
  }
  const blocking = required.find((row) => row.blocking && row.status !== 'passed') ?? required.find((row) => row.blocking);
  if (blocking) return { kind: 'open', text: `open: ${blocking.blocking}` };
  return {
    kind: 'open',
    text: `open: ${passed.length === 1 ? 'the' : `all ${passed.length}`} required output${passed.length === 1 ? '' : 's'} passed; the node can close`,
  };
}

export function checkBadge(
  view: NodeCheckView | undefined,
  node: PlanNode | undefined,
  outputs = (view?.outputs ?? []).map((output) => summarizeOutput(output, node?.state === 'done')),
): CheckBadge | undefined {
  if (nodeHold(node)) return { tone: 'held', text: 'held' };
  const required = outputs.filter((row) => row.output.required);
  if (!view || !required.length) return undefined;
  if (required.some((row) => row.status === 'failed')) return { tone: 'failed', text: 'gate halted' };
  if (required.some((row) => row.status === 'running')) return { tone: 'running', text: 'checking' };
  const passed = required.filter((row) => row.status === 'passed').length;
  return { tone: passed === required.length ? 'passed' : 'pending', text: `${passed}/${required.length} checks` };
}

/** The capsule a node mainly works with: its capability's capsule, else the first helpful CC. */
export function primaryCapsule(view: NodeCheckView | undefined, capability?: unknown) {
  const value = text(view?.capability) ?? text(capability);
  if (value) {
    const parts = value.split('@', 1)[0].split('.');
    return parts.length > 2 ? parts.slice(0, 2).join('.') : parts.join('.');
  }
  return view?.helpful_ccs?.[0];
}

/** Attempts with retry_from: earlier ones no longer count after an operator reopen. */
export function attemptsOf(node: PlanNode | undefined) {
  const ids = Array.isArray(node?.attempt_ids) ? node.attempt_ids.filter((id): id is string => typeof id === 'string') : [];
  const from = typeof node?.retry_from === 'number' ? node.retry_from : 0;
  return ids.map((id, index) => ({ id, superseded: index < from }));
}

export type Controls = {
  operator?: boolean;
  running?: boolean;
  outcome?: string | null;
  stop_reason?: string | null;
  resume?: boolean;
} | null;
export type OperatorOp = 'hold' | 'release' | 'reopen';
export type NodeOperator = {
  actions: (node: PlanNode) => OperatorOp[];
  run: (nodeId: string, op: OperatorOp, reason: string) => Promise<void>;
};
export type RunKind = { kind: 'bundle' | 'live'; curated?: boolean };

/** Operator controls exist only for live factory homes, never for bundles or curated replays. */
export function operatorEnabled(run: RunKind, controls: Controls | undefined) {
  return run.kind === 'live' && !run.curated && Boolean(controls?.operator);
}

export function nodeActions(run: RunKind, controls: Controls | undefined, node: PlanNode | undefined): OperatorOp[] {
  if (!operatorEnabled(run, controls) || !node || typeof node.node_id !== 'string') return [];
  const state = typeof node.state === 'string' ? node.state : '';
  if (['cancelled', 'superseded'].includes(state)) return [];
  const actions: OperatorOp[] = [];
  if (nodeHold(node)) actions.push('release');
  else if (state !== 'done') actions.push('hold');
  if (['failed', 'done', 'blocked'].includes(state)) actions.push('reopen');
  return actions;
}

export function resumeEnabled(run: RunKind, controls: Controls | undefined) {
  return (
    operatorEnabled(run, controls) &&
    Boolean(controls?.resume) &&
    !controls?.running &&
    ['paused', 'partial'].includes(controls?.outcome ?? '')
  );
}

/** "paused at requant_q2: held by operator: …" from the graph's held/failed nodes, else the controller's stop reason. */
export function pauseStatement(nodes: readonly PlanNode[], controls: Controls | undefined) {
  const stops = nodes
    .map((node) => {
      const id = text(node.node_id);
      const hold = nodeHold(node);
      if (!id) return undefined;
      if (hold) return `${id}: held by operator: ${hold}`;
      if (node.state === 'failed') return `${id}: failed: ${text(node.reason) ?? 'no reason recorded'}`;
      return undefined;
    })
    .filter((value): value is string => Boolean(value));
  const held = nodes.filter((node) => nodeHold(node)).length;
  if (controls?.outcome === 'paused') {
    if (stops.length) return { paused: true, text: `paused at ${stops.join('; ')}` };
    return { paused: true, text: text(controls.stop_reason) ?? 'paused' };
  }
  if (held) {
    const holds = stops.filter((stop) => stop.includes(': held by operator: '));
    return { paused: false, text: `hold at ${holds.join('; ')}` };
  }
  return undefined;
}
