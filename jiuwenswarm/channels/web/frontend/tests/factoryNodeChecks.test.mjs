import assert from 'node:assert/strict';
import test from 'node:test';
import {
  attemptsOf,
  checkBadge,
  gateStatement,
  nodeActions,
  operatorEnabled,
  pauseStatement,
  primaryCapsule,
  resumeEnabled,
  summarizeNode,
  summarizeOutput,
} from '../src/features/factoryRuns/views/checkModel.ts';

// Test fixture in the compact node_checks form of GET /runs/{id}; not a recorded run.
const check = (obs_id, extra = {}) => ({
  obs_id,
  state: 'finished',
  passed: true,
  reason: 'passed',
  same_settings: true,
  superseded: false,
  cited: true,
  verifier: null,
  review: null,
  ...extra,
});
const output = (name, checks, extra = {}) => ({
  name,
  kind: 'diff',
  required: true,
  declared: true,
  verifier: 'weights.build_muse_nvfp4_reader.verify',
  stage: 'fixture',
  review: true,
  checks,
  ...extra,
});
const view = (outputs) => ({
  node_contract: 'ingest_nvfp4',
  helpful_ccs: ['weights.build_muse_nvfp4_reader', 'factory.source_workbench'],
  capability: 'weights.build_muse_nvfp4_reader.verify',
  outputs,
});

test('a done node whose required outputs all passed reads as closed with a full badge', () => {
  const node = { node_id: 'ingest_nvfp4', state: 'done' };
  const checks = view([
    output('converter', [check('nc:1', { verifier: { passed: true, stage_reached: 'fixture', checks: [] } })]),
    output('nvfp4_pack', [check('nc:2')], { kind: 'evidence', stage: 'native CC execution' }),
  ]);
  const summary = summarizeNode(checks, node);
  assert.equal(summary.gate.kind, 'closed');
  assert.equal(summary.gate.text, 'closed: all 2 required outputs passed their latest check');
  assert.deepEqual(summary.badge, { tone: 'passed', text: '2/2 checks' });
  assert.equal(summary.outputs[0].stageMet, true);
  assert.equal(primaryCapsule(checks), 'weights.build_muse_nvfp4_reader');
});

test('a failed verifier lists failures first, compares stages and halts the gate', () => {
  const failing = check('nc:3', {
    passed: false,
    reason: 'verifier failed: split_order',
    verifier: {
      passed: false,
      stage_reached: null,
      checks: [
        { name: 'source_map', status: 'pass', stage: 'fixture' },
        { name: 'split_order', status: 'fail', stage: 'fixture', detail: 'up half came first' },
        { name: 'lazy_repack', status: 'skipped' },
      ],
    },
    review: null,
  });
  const node = { node_id: 'ingest_nvfp4', state: 'running' };
  const checks = view([output('converter', [check('nc:1', { superseded: false }), failing]), output('nvfp4_pack', [])]);
  const row = summarizeOutput(checks.outputs[0]);
  assert.deepEqual(row.verifierChecks.map((c) => c.name), ['split_order', 'lazy_repack', 'source_map']);
  assert.equal(row.stageMet, false);
  assert.equal(row.history.length, 2);
  assert.equal(gateStatement(checks, node).text, 'open: output converter failed check: verifier failed: split_order');
  assert.deepEqual(checkBadge(checks, node), { tone: 'failed', text: 'gate halted' });
});

test('reviewer findings sort blockers first; running and uncited checks keep the node open', () => {
  const reviewed = check('nc:4', {
    cited: false,
    review: {
      verdict: 'fail',
      findings: [
        { severity: 'minor', problem: 'naming' },
        { severity: 'blocker', file: 'convert.py', line: 10, problem: 'dequantizes' },
      ],
    },
  });
  assert.deepEqual(summarizeOutput(output('converter', [reviewed])).findings.map((f) => f.severity), ['blocker', 'minor']);
  const node = { node_id: 'n', state: 'ready' };
  assert.equal(
    gateStatement(view([output('converter', [reviewed])]), node).text,
    'open: output converter passed; the node has yet to cite check nc:4',
  );
  const running = view([output('converter', [check('nc:5', { state: 'running', passed: false })])]);
  assert.deepEqual(checkBadge(running, node), { tone: 'running', text: 'checking' });
  assert.equal(gateStatement(view([output('converter', [])]), node).text, 'open: output converter has no node check yet');
  assert.equal(
    gateStatement(view([output('converter', [check('nc:6', { same_settings: false })])]), node).text,
    'open: output converter: the latest check used other check settings',
  );
});

test('held nodes say so; reopened nodes mark earlier checks and attempts as superseded', () => {
  const held = { node_id: 'requant_q2', state: 'proposed', hold: 'disk below 1.4 TB' };
  assert.deepEqual(gateStatement(view([]), held), { kind: 'held', text: 'held by operator: disk below 1.4 TB' });
  assert.deepEqual(checkBadge(view([output('pack', [])]), held), { tone: 'held', text: 'held' });
  const reopened = view([output('converter', [check('nc:1', { superseded: true })])]);
  assert.equal(
    gateStatement(reopened, { node_id: 'x', state: 'proposed' }).text,
    'open: output converter needs a fresh check after the operator reopened the node',
  );
  assert.deepEqual(attemptsOf({ attempt_ids: ['a1', 'a2', 'a3'], retry_from: 2 }), [
    { id: 'a1', superseded: true },
    { id: 'a2', superseded: true },
    { id: 'a3', superseded: false },
  ]);
  assert.equal(gateStatement(undefined, { node_id: 'plain' }), undefined);
  assert.equal(gateStatement(view([output('note', [], { required: false })]), { node_id: 'x' }).kind, 'unchecked');
});

test('operator controls exist only for live homes and fit the node state', () => {
  const controls = { operator: true, running: false, outcome: 'paused', resume: true };
  const live = { kind: 'live' };
  assert.equal(operatorEnabled({ kind: 'bundle' }, controls), false);
  assert.equal(operatorEnabled({ kind: 'live', curated: true }, controls), false);
  assert.equal(operatorEnabled(live, null), false);
  assert.deepEqual(nodeActions({ kind: 'bundle' }, controls, { node_id: 'n', state: 'failed' }), []);
  assert.deepEqual(nodeActions(live, controls, { node_id: 'n', state: 'proposed' }), ['hold']);
  assert.deepEqual(nodeActions(live, controls, { node_id: 'n', state: 'proposed', hold: 'why' }), ['release']);
  assert.deepEqual(nodeActions(live, controls, { node_id: 'n', state: 'failed' }), ['hold', 'reopen']);
  assert.deepEqual(nodeActions(live, controls, { node_id: 'n', state: 'done' }), ['reopen']);
  assert.deepEqual(nodeActions(live, controls, { node_id: 'n', state: 'superseded' }), []);
  assert.equal(resumeEnabled(live, controls), true);
  assert.equal(resumeEnabled(live, { ...controls, outcome: 'partial' }), true);
  assert.equal(resumeEnabled(live, { ...controls, outcome: 'accept', resume: false }), false);
  assert.equal(resumeEnabled(live, { ...controls, running: true }), false);
  assert.equal(resumeEnabled({ kind: 'bundle' }, controls), false);
});

test('the pause statement names held and failed nodes, else the controller stop reason', () => {
  const nodes = [
    { node_id: 'build_base_engine', state: 'done' },
    { node_id: 'requant_q2', state: 'proposed', hold: 'check the recipe first' },
  ];
  assert.deepEqual(pauseStatement(nodes, { outcome: 'paused' }), {
    paused: true,
    text: 'paused at requant_q2: held by operator: check the recipe first',
  });
  assert.deepEqual(pauseStatement(nodes, { outcome: null, running: true }), {
    paused: false,
    text: 'hold at requant_q2: held by operator: check the recipe first',
  });
  assert.deepEqual(pauseStatement([{ node_id: 'a', state: 'proposed' }], { outcome: 'paused', stop_reason: 'paused at a (x)' }), {
    paused: true,
    text: 'paused at a (x)',
  });
  assert.equal(pauseStatement([{ node_id: 'a', state: 'done' }], { outcome: 'accept' }), undefined);
});
