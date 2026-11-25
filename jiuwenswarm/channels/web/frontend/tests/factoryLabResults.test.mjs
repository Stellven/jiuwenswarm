import assert from 'node:assert/strict';
import test from 'node:test';
import { conditionOf, formatChange, labResults, referenceArm, requestOf } from '../src/features/factoryRuns/labModel.ts';

// Test fixture: a four-arm factory.contract/2 and a lab_report observation shaped like
// lab_manager.report records it. Numbers are invented for the test; this is not a run.
const contract = {
  schema: 'factory.contract/2',
  contract_id: 'fixture-four-arms',
  arms: [
    { id: 'A', role: 'baseline' },
    { id: 'B', role: 'candidate', from: 'A' },
    { id: 'C', role: 'combined', from: 'A' },
    { id: 'D', role: 'candidate', from: 'A' },
  ],
  workload: { requests: [{ id: 'p512' }, { id: 'p2048' }] },
  measurement: {
    primary: 'client_ttft_ms',
    metrics: {
      decode_tokens_per_second: { unit: 'tokens/s', better: 'higher' },
      client_ttft_ms: { unit: 'ms', better: 'lower' },
      request_total_ms: { unit: 'ms' },
    },
  },
  correctness: {
    reference: { arm: 'A' },
    checks: [
      { id: 'gate_unset_parity', does: 'E1 gate unset equals B.', applies_to: ['C'] },
      { id: 'gate_set_activation', does: 'Marker printed.', applies_to: ['C', 'D'] },
      { id: 'cold_smoke', does: 'Coherent text.', applies_to: ['baseline', 'candidate', 'combined'] },
    ],
  },
};
const ttft = { A: [1000, 400, 4000, 1600], B: [500, 200, 2000, 800], C: [250, 100, 1000, 400], D: [1100, 440, 4400, 1760] };
const results = [];
for (const [arm, values] of Object.entries(ttft)) {
  const cells = [
    ['p512', 'speed-cold'],
    ['p512', 'speed-warm'],
    ['p2048', 'speed-cold'],
    ['p2048', 'speed-warm'],
  ];
  cells.forEach(([request, test_id], index) => {
    results.push({ test_id, arm, request, metric: 'client_ttft_ms', unit: 'ms', value: values[index], statistic: 'median' });
    results.push({ test_id, arm, request, metric: 'decode_tokens_per_second', unit: 'tokens/s', samples: [10, arm === 'B' ? 14 : 12, 11] });
    results.push({ test_id, arm, request, metric: 'request_total_ms', unit: 'ms', value: arm === 'A' ? 100 : 90 });
  });
}
const report = (request_id, created, extra = {}) => ({
  obs_id: `${request_id}:report`,
  kind: 'lab_report',
  created,
  limitations: 'fixture',
  values: {
    request_id,
    valid: true,
    problems: [],
    outcome: 'completed',
    lab: { name: 'fixture-lab', kind: 'operator' },
    summary: 'Fixture report.',
    results,
    checks: [
      { test_id: 'parity', check: 'gate_unset_parity', arm: 'C', verdict: 'pass' },
      { test_id: 'activation', check: 'gate_set_activation', arm: 'C', verdict: 'pass' },
      { test_id: 'activation', check: 'gate_set_activation', arm: 'D', verdict: 'fail', detail: 'no marker' },
      { test_id: 'extra', check: 'lab_only_check', verdict: 'pass' },
    ],
    not_run: [{ test_id: 'memory', reason: 'sampler missing' }],
    ...extra,
  },
});
const files = [{ path: 'artifacts/ab/cd', artifact_ids: ['lab-req-2:report.json'] }];

test('arms, metrics and the reference arm come from the contract', () => {
  const model = labResults(contract, [report('lab-req-1', 1), report('lab-req-2', 2)], files);
  assert.deepEqual(model.arms.map((arm) => arm.id), ['A', 'B', 'C', 'D']);
  assert.deepEqual(model.reference, { arm: 'A', source: 'contract correctness reference' });
  assert.deepEqual(model.metrics.map((metric) => metric.id), ['client_ttft_ms', 'decode_tokens_per_second', 'request_total_ms']);
  assert.equal(model.reports.length, 2);
  assert.equal(model.reports[1].reportFile, 'artifacts/ab/cd');
  assert.equal(labResults({ contract_id: 'star-deepseek-v1' }, []), null);
  assert.deepEqual(referenceArm({ arms: [{ id: 'X', role: 'candidate' }, { id: 'Y', role: 'baseline' }] }), {
    arm: 'Y',
    source: 'contract arm with role baseline',
  });
  assert.equal(referenceArm({ comparison: { reference: 'B' }, correctness: { reference: { arm: 'A' } } }).arm, 'B');
});

test('each metric is laid out prompt by cold and warm with change vs the reference and its direction', () => {
  const [, latest] = labResults(contract, [report('lab-req-1', 1), report('lab-req-2', 2)], files).reports;
  const table = latest.tables.find((t) => t.metric.id === 'client_ttft_ms');
  assert.deepEqual(table.lines.map((line) => [line.request, line.condition]), [
    ['p512', 'cold'],
    ['p512', 'warm'],
    ['p2048', 'cold'],
    ['p2048', 'warm'],
  ]);
  const cold512 = table.lines[0].cells;
  assert.equal(cold512.A.reference, true);
  assert.equal(cold512.A.change, undefined);
  assert.equal(cold512.B.change, -0.5);
  assert.equal(cold512.B.verdict, 'better');
  assert.equal(cold512.C.change, -0.75);
  assert.ok(Math.abs(cold512.D.change - 0.1) < 1e-9);
  assert.equal(cold512.D.verdict, 'worse');
  assert.equal(cold512.B.rows[0].test_id, 'speed-cold');
  const decode = latest.tables.find((t) => t.metric.id === 'decode_tokens_per_second').lines[0].cells;
  assert.equal(decode.A.value, 11);
  assert.equal(decode.B.value, 11);
  assert.equal(decode.B.verdict, 'same');
  const total = latest.tables.find((t) => t.metric.id === 'request_total_ms').lines[0].cells;
  assert.equal(total.B.verdict, 'undetermined');
  assert.equal(formatChange(cold512.B.change), '−50%');
  assert.equal(formatChange(cold512.D.change), '+10%');
});

test('contract checks resolve roles and arms, report fails, unknown checks and not-run tests', () => {
  const [latest] = labResults(contract, [report('lab-req-2', 2)], files).reports;
  const checks = Object.fromEntries(latest.checks.map((check) => [check.id, check]));
  assert.equal(checks.gate_unset_parity.verdict, 'pass');
  assert.deepEqual(checks.gate_unset_parity.appliesTo, ['C']);
  assert.equal(checks.gate_set_activation.verdict, 'fail');
  assert.deepEqual(checks.cold_smoke.appliesTo, ['A', 'B', 'C', 'D']);
  assert.equal(checks.cold_smoke.verdict, 'no result');
  assert.equal(checks.lab_only_check.declared, false);
  assert.equal(latest.notRun[0].test_id, 'memory');
});

test('a rejected report keeps its problems; undeclared arms and metrics stay visible', () => {
  const rejected = { obs_id: 'r:report', kind: 'lab_report', created: 3, values: { request_id: 'r', valid: false, problems: ['contract: wrong digest'] } };
  const odd = report('lab-req-3', 4, {
    results: [
      { test_id: 't', arm: 'A', metric: 'mystery', unit: 'x', value: 2 },
      { test_id: 't', arm: 'E', metric: 'mystery', unit: 'x', value: 3 },
    ],
  });
  const model = labResults(contract, [rejected, odd]);
  assert.equal(model.reports[0].valid, false);
  assert.deepEqual(model.reports[0].problems, ['contract: wrong digest']);
  assert.equal(model.arms.find((arm) => arm.id === 'E').declared, false);
  const mystery = model.reports[1].tables[0];
  assert.equal(mystery.metric.declared, false);
  assert.equal(mystery.lines[0].cells.E.verdict, 'undetermined');
});

test('cold and warm are read from request or test ids, otherwise the test id is the condition', () => {
  assert.equal(conditionOf({ test_id: 'ttft', request: 'p512:cold' }), 'cold');
  assert.equal(requestOf({ request: 'p512:cold' }), 'p512');
  assert.equal(conditionOf({ test_id: 'warm_ttft' }), 'warm');
  assert.equal(conditionOf({ test_id: 'speed' }), 'speed');
  assert.equal(conditionOf({ test_id: 'coldstart' }), 'coldstart');
});
