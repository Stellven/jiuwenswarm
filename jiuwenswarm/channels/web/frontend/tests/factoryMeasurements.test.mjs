import assert from 'node:assert/strict';
import test from 'node:test';
import { aggregateMeasurements, chartScale, focusedP4Reports, promptOptions } from '../src/features/factoryRuns/measurementModel.ts';

const phase = 'reconnaissance';
const prompt = { tokens: 512, hash: 'pinned-test-prompt' };
const source = (line) => ({ line, integrity: 'ledger-match' });
const identity = (arm) => ({ arm, phase, prompt_tokens: prompt.tokens, prompt_sha256: prompt.hash });
const sample = (line, arm, ttft_s, extra = {}) => ({
  ...identity(arm),
  ttft_s,
  decode_tps: ttft_s,
  source: source(line),
  ...extra,
});
const ledger = (samples, summaries = []) => ({ samples, summaries, issues: [] });
const find = (rows, arm) => rows.find((row) => row.arm === arm).metrics;

function focused(name, budget, byte, subject = 'C3') {
  const ref = (suffix) => ({ artifact_id: `${name}/${suffix}`, sha256: byte.repeat(64) });
  const manifest = ref('launch.json');
  const analysis = ref('analysis.json');
  const verifier = ref('verify-receipt.json');
  const report = ref('report.md');
  const refs = [manifest, analysis, verifier, report];
  const effect = { estimate: 1.2, observed_range: [-1, 2], conditional_ci95: [-0.2, 1.9] };
  const observation = {
    kind: 'factory_iteration_report',
    source_artifacts: refs.map(({ artifact_id }) => artifact_id),
    values: {
      schema: 'spark-factory-iteration/1',
      plan: { manifest },
      report: { ...report, status: 'verified-p4', summary: name },
      lab: { status: 'complete' },
      analysis: {
        ccs: [{ id: 'factory.spark_gap_analysis', release: 'a'.repeat(64) }],
        result_artifact: analysis,
        output_artifact_ids: [analysis.artifact_id, verifier.artifact_id],
        focused_comparison: {
          schema: 'spark-p4-focused/1',
          subject_arm: subject,
          budget_mib: budget,
          allocated_mib: budget - 10,
          profiles: {
            'A+': { profile_sha256: 'a'.repeat(64), binary_sha256: 'b'.repeat(64) },
            [subject]: { profile_sha256: byte.repeat(64), binary_sha256: byte.repeat(64) },
          },
          verification: verifier,
          rows: [512, 2048].map((prompt_tokens) => ({
            prompt_tokens, n: 10,
            control: { ttft_s: 5, decode_tps: 18 },
            candidate: { ttft_s: 4, decode_tps: 20 },
            paired_ttft_seconds_saved_vs_Aplus: effect,
            paired_decode_tps_gained_vs_Aplus: effect,
          })),
        },
      },
    },
  };
  const files = refs.map(({ artifact_id, sha256 }) => ({
    path: artifact_id, artifact_ids: [artifact_id], sha256, integrity: 'verified', size: 12,
  }));
  return { observation, files };
}

test('verified P4 cards retain exact launch, budget and candidate version identities', () => {
  const fixtures = [focused('cache-30', 30720, 'c'), focused('cache-60', 61440, 'd'),
    focused('cache-30-new', 30720, 'e', 'C3-direct')];
  const inputs = fixtures.map(({ observation }) => observation);
  const files = fixtures.flatMap((item) => item.files);
  const cards = focusedP4Reports(inputs, files);
  assert.deepEqual(cards.map(({ budgetMib }) => budgetMib), [30720, 61440, 30720]);
  assert.deepEqual(cards.map(({ subject }) => subject), ['C3', 'C3', 'C3-direct']);
  assert.equal(new Set(cards.map(({ key }) => key)).size, 3);
  assert.equal(cards[2].summary, 'cache-30-new');
  assert.equal(cards[2].candidateProfile.binarySha256, 'e'.repeat(64));
  assert.deepEqual(cards[0].rows[0].ttftSaved.ci, [-0.2, 1.9]);
  assert.equal(cards[1].rows[1].n, 10);
  const mismatch = files.map((file) => file.path === 'cache-60/verify-receipt.json' ?
    { ...file, sha256: '0'.repeat(64) } : file);
  assert.deepEqual(focusedP4Reports(inputs, mismatch).map(({ budgetMib }) => budgetMib), [30720, 30720]);
});

test('preserves warm-sample median, observed range and independent scope counts', () => {
  const data = ledger(
    [1, 2, 3, 100, 200].map((value, index) =>
      sample(index + 1, 'A', value, {
        peak_memory_bytes: index > 1 ? 20 : 10,
        memory_source: source(index > 1 ? 8 : 7),
      }),
    ),
  );
  const rows = aggregateMeasurements(data, phase, prompt);
  assert.deepEqual(
    rows.map((row) => row.arm),
    ['A', 'A+', 'C1', 'C2', 'C3', 'C4', 'C5', 'D', 'S'],
  );
  const metrics = find(rows, 'A');
  assert.equal(metrics.ttft_s.value, 3);
  assert.equal(metrics.ttft_s.n, 5);
  assert.deepEqual(metrics.ttft_s.range, [1, 200]);
  assert.equal(metrics.ttft_s.interval, undefined);
  assert.equal(metrics.decode_tps.value, 3);
  assert.equal(metrics.peak_memory_bytes.value, 20);
  assert.equal(metrics.peak_memory_bytes.n, 2);
  assert.deepEqual(metrics.peak_memory_bytes.sources, [source(7), source(8)]);
});

test('derived comparisons cite all matching control rows and retain the full closure scale', () => {
  const data = ledger([sample(1, 'A', 10), sample(2, 'S', 5), sample(3, 'C1', 20), sample(4, 'D', 2)]);
  const rows = aggregateMeasurements(data, phase, prompt);
  assert.equal(find(rows, 'C1').gap.value, -2);
  assert.equal(find(rows, 'D').gap.value, 1.6);
  assert.deepEqual(find(rows, 'D').gap.sources, [source(4), source(1), source(2)]);
  assert.deepEqual(find(rows, 'D').inverse_a.sources, [source(4), source(1)]);
  const scale = chartScale(rows, 'gap');
  assert.equal(scale.position(-2), 0);
  assert.equal(scale.position(1.6), 100);
});

test('prompt hash and phase isolate control cohorts; a zero or negative stock gap remains unavailable', () => {
  const data = ledger([
    sample(1, 'A', 5),
    sample(2, 'S', 5),
    sample(3, 'A', 500, { phase: 'final' }),
    sample(4, 'S', 2, { prompt_sha256: 'different-prompt' }),
  ]);
  const rows = aggregateMeasurements(data, phase, prompt);
  assert.equal(find(rows, 'A').ttft_s.value, 5);
  assert.ok(rows.every((row) => row.metrics.gap === undefined));
  assert.equal(promptOptions(data, phase).length, 2);
  assert.equal(find(aggregateMeasurements(data, 'final', prompt), 'A').ttft_s.value, 500);
});

test('only source-provided confidence intervals for the exact input rows are rendered', () => {
  const interval = { low: 2, high: 4, level: 0.9, n: 2, source_lines: [1, 2] };
  const data = ledger(
    [sample(1, 'A', 2), sample(2, 'A', 4)],
    [
      { ...identity('A'), source: source(3), intervals: { ttft_s: interval } },
      { ...identity('A'), source: source(4), intervals: { ttft_s: { ...interval, source_lines: [1, 9] } } },
    ],
  );
  const stats = find(aggregateMeasurements(data, phase, prompt), 'A').ttft_s;
  assert.deepEqual(stats.interval, interval);
  assert.deepEqual(stats.intervalSource, source(3));
});
