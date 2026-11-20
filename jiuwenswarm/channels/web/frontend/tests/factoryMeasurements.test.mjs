import assert from 'node:assert/strict';
import test from 'node:test';
import { aggregateMeasurements, chartScale, promptOptions } from '../src/features/factoryRuns/measurementModel.ts';

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
