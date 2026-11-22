import assert from 'node:assert/strict';
import test from 'node:test';

import { filterLogRows, parseLog, projectStoryLog } from '../src/features/factoryRuns/views/logModel.ts';

test('launch output extracts module, timestamp, and severity and keeps pipes in the message', () => {
  const [row] = parseLog('2026-11-20 02:20:41 | common | default_trace_id | WARNING | column A | column B\n');
  assert.deepEqual(row, {
    id: '1',
    timestamp: '2026-11-20 02:20:41',
    source: 'common',
    level: 'warning',
    message: 'column A | column B',
  });
});

test('plain output preserves whitespace and failure diagnostics while removing terminal escapes', () => {
  const rows = parseLog(
    '\x1b[32m  output\x1b[0m\r\n\r\nsolver.cpp:21:11: error: invalid argument\n' +
      'plugin.py:208: PytestDeprecationWarning: deprecated\n' +
      '[2026-11-20T07:20:41.425Z] [WARN] retrying\r' +
      '\x1b]8;;https://example.test\x07visible\x1b]8;;\x07\n' +
      '{"missing":"truncated',
  );
  assert.deepEqual(
    rows.map((row) => row.level),
    ['plain', 'plain', 'error', 'warning', 'warning', 'plain', 'plain'],
  );
  assert.deepEqual(
    rows.map((row) => row.id),
    ['1', '2', '3', '4', '5', '6', '7'],
  );
  assert.equal(rows[0].message, '  output');
  assert.equal(rows[1].message, '');
  assert.equal(rows[4].timestamp, '2026-11-20T07:20:41.425Z');
  assert.equal(rows[4].message, 'retrying');
  assert.equal(rows[5].message, 'visible');
  assert.equal(rows[6].message, '{"missing":"truncated');
  assert.deepEqual(parseLog(''), []);
});

test('session JSONL retains the source record and indexes searchable fields', () => {
  const start = '{"t":1795159241,"event":"turn.start","turn":2,"query":"inspect baseline"}';
  const tool = '{"t":1795159241,"event_type":"chat.tool_call","tool_call":{"name":"cc_material"}}';
  const failure = '{"t":1795159241,"event_type":"chat.error","error":"stream disconnected"}';
  const rows = parseLog([start, tool, failure].join('\n'));
  assert.equal(rows[0].source, 'turn.start');
  assert.equal(rows[0].message, '#2');
  assert.equal(rows[0].raw, start);
  assert.equal(rows[1].message, 'cc_material');
  assert.equal(rows[1].dateTime, '2026-11-20T07:20:41.000Z');
  assert.equal(rows[2].level, 'error');
  assert.equal(rows[2].message, 'stream disconnected');
  assert.deepEqual(filterLogRows(rows, '  BASELINE ', 'all'), [rows[0]]);
  assert.deepEqual(filterLogRows(rows, 'chat', 'error'), [rows[2]]);
  assert.deepEqual(filterLogRows(rows, '2026-11-20', 'info'), rows.slice(0, 2));
  assert.equal(filterLogRows(rows, '', 'all'), rows);
});

test('pytest progress lines retain test names and expose the reported outcome', () => {
  const [pass, fail] = parseLog(
    'tests/test_api.py::test_query PASSED [  0%]\ntests/test_api.py::test_publish FAILED [100%]',
  );
  assert.equal(pass.level, 'success');
  assert.equal(fail.level, 'error');
  assert.match(fail.message, /test_publish FAILED/);
});

test('story rows use source marks and preserve replay cursor and event order', () => {
  const rows = projectStoryLog([
    { id: 'build', cursor: 1, created: 0, kind: 'build', summary: 'failed', mark: '✗' },
    { id: 'build', cursor: 2, created: 1795159241, kind: 'build', summary: 'succeeded', mark: '✓' },
    { id: 'plan', cursor: 3, created: 1795159242, kind: 'replan/build', summary: 'retry' },
    { id: 'review', cursor: 4, created: 1795159243, kind: 'report_inconclusive', summary: 'inspect' },
  ]);
  assert.deepEqual(
    rows.map((row) => row.cursor),
    [1, 2, 3, 4],
  );
  assert.deepEqual(
    rows.map((row) => row.level),
    ['error', 'success', 'warning', 'warning'],
  );
  assert.equal(new Set(rows.map((row) => row.id)).size, rows.length);
  assert.equal(rows[0].timestamp, undefined);
  assert.equal(rows[1].timestamp, '2026-11-20 07:20:41Z');
  assert.equal(rows[2].kind, 'replan/build');
  assert.equal(rows[2].source, 'Replan: native build');
});
