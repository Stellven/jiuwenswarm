import assert from 'node:assert/strict';
import test from 'node:test';

import {
  engineRequestGroup,
  engineRequestLabel,
  requestIndexFromSpeedSource,
  requestStateLabel,
} from '../src/features/factoryRuns/engineBenchModel.ts';

const row = (arm, prompt, state, path, record) => ({
  arm,
  request: { name: prompt, state },
  source: { path, record },
});

test('published cold cells use their load-local speed chronology even when p128 is omitted', () => {
  const run1 = [
    row('A', 'p512', 'cold', '/lab/5.speed.json', '/rows/3'),
    row('A', 'p2048', 'cold', '/lab/5.speed.json', '/rows/9'),
    row('AQB', 'p512', 'cold', '/lab/3.speed.json', '/rows/3'),
    row('AQB', 'p2048', 'cold', '/lab/3.speed.json', '/rows/9'),
  ];
  const run2 = [
    row('AQBC', 'p512', 'cold', '/lab/speed.json', '/rows/0'),
    row('AQB', 'p512', 'cold', '/lab/speed.json', '/rows/1'),
    row('AQB', 'p2048', 'cold', '/lab/speed.json', '/rows/6'),
    row('AQBC', 'p2048', 'cold', '/lab/speed.json', '/rows/7'),
  ];
  assert.deepEqual(run1.map(engineRequestLabel), Array(4).fill('After page drop'));
  assert.deepEqual(run2.map(engineRequestLabel), ['First request after start', ...Array(3).fill('After page drop')]);
  assert.deepEqual(run2.map(engineRequestGroup), ['startup', 'cold', 'cold', 'cold']);
  assert.equal(engineRequestLabel(row('A', 'p128', 'cold', '/lab/5.speed.json', '/rows/0')), 'First request after start');
});

test('sidecar or projected-row order cannot stand in for speed chronology', () => {
  assert.equal(requestIndexFromSpeedSource({ path: 'speed.json', record: '/rows/0' }), 0);
  assert.equal(requestIndexFromSpeedSource({ path: '/lab/3.ttft.json', record: '/rows/0' }), undefined);
  assert.equal(requestIndexFromSpeedSource({ path: '/lab/3.speed.json', record: '/cells/0' }), undefined);
  assert.equal(requestIndexFromSpeedSource({ path: '/lab/3.speed.json', record: 0 }), undefined);
  assert.equal(engineRequestLabel(row('AQBC', 'p512', 'cold', '/lab/3.ttft.json', '/rows/0')), 'Cold request');
  assert.equal(requestStateLabel('cold'), 'Cold request');
  assert.equal(requestStateLabel('warm', 0), 'Warm server');
});
