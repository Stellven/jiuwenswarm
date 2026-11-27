import assert from 'node:assert/strict';
import test from 'node:test';
import { contractDemoRuns } from '../src/features/factoryRuns/views/runListModel.ts';
import { liveReplayPosition } from '../src/features/factoryRuns/views/storyModel.ts';

test('the Demo list keeps the native route after archive publication', () => {
  const native = { id: 'native', task_id: 'native-demo', name: 'Run 4', demo_order: 4, updated: 1, contract_demo: true, live_demo: true };
  const archive = { ...native, id: 'archive', updated: 2, live_demo: false };
  assert.deepEqual(contractDemoRuns([archive, native]), [native]);
  assert.deepEqual(contractDemoRuns([native, archive]), [native]);
});

test('polling follows the latest row or preserves the earlier record under review', () => {
  const observation = (id) => ({ id, kind: 'observation' });
  const previous = ['first', 'second', 'third'].map(observation);
  const next = ['first', 'inserted', 'second', 'third', 'new'].map(observation);
  assert.equal(liveReplayPosition(previous, next, 3), 5);
  assert.equal(liveReplayPosition(previous, next, 2), 3);
  assert.equal(liveReplayPosition(previous, next, 0), 0);
});
