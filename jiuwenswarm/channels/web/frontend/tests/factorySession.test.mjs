import assert from 'node:assert/strict';
import test from 'node:test';
import { sessionElapsed, sessionStatus } from '../src/features/factoryRuns/sessionPresentation.ts';

test('only a fresh running snapshot can show running now', () => {
  assert.equal(sessionStatus(undefined), 'loading');
  assert.equal(sessionStatus({ status: 'running' }), 'running');
  assert.equal(sessionStatus({ status: 'running' }, true), 'unavailable');
  assert.equal(sessionStatus({ status: 'waiting' }), 'waiting');
  assert.equal(sessionStatus({ status: 'finished' }), 'finished');
  assert.equal(sessionStatus({ status: 'unknown' }), 'unknown');
});

test('render active elapsed time without fabricating a duration for missing evidence', () => {
  assert.equal(sessionElapsed(null), null);
  assert.equal(sessionElapsed(-1), null);
  assert.equal(sessionElapsed(Infinity), null);
  assert.equal(sessionElapsed(0), '00:00:00');
  assert.equal(sessionElapsed(61.9), '00:01:01');
  assert.equal(sessionElapsed(3661.9), '01:01:01');
});
