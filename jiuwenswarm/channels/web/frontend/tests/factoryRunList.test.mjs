import assert from 'node:assert/strict';
import test from 'node:test';
import { runListEntries } from '../src/features/factoryRuns/views/runListModel.ts';

const run = (id, kind, updated, source_name) => ({
  id,
  kind,
  updated,
  source_name,
  name: 'spark-direct',
  task_id: 'spark-direct',
  status: kind === 'bundle' ? 'replay' : 'live',
});

test('deduplicates repeated run IDs and keeps the newest copy in its original position', () => {
  const first = run('1', 'bundle', 1000, 'export-early');
  const latest = { ...first, updated: 1200 };
  const live = run('2', 'live', 1050, 'home');
  assert.deepEqual(
    runListEntries([first, live, latest, first]).map(({ run }) => run),
    [latest, live],
  );
});

test('keeps separate exports and homes with a shared task title and shows their source names', () => {
  const inputs = [
    run('export-1', 'bundle', 1000, 'spark-direct-T0710Z'),
    run('export-2', 'bundle', 1100, 'spark-direct-T0720Z'),
    run('live-home', 'live', 1150, 'spark-direct-home'),
  ];
  assert.deepEqual(
    runListEntries(inputs).map(({ run, source, shortId }) => [run.id, source, shortId]),
    [
      ['export-1', 'spark-direct-T0710Z', undefined],
      ['export-2', 'spark-direct-T0720Z', undefined],
      ['live-home', 'spark-direct-home', undefined],
    ],
  );
});

test('same-minute rows from a legacy catalog use their IDs to distinguish matching metadata', () => {
  assert.deepEqual(
    runListEntries([run('abc0123456789', 'bundle', 1101), run('def0123456789', 'bundle', 1102)]).map(
      ({ shortId }) => shortId,
    ),
    ['abc01234', 'def01234'],
  );
});
