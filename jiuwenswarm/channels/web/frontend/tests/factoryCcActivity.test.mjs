import assert from 'node:assert/strict';
import test from 'node:test';
import { capsuleFactsAt, nodeVerifierAt, reopenBoundary } from '../src/features/factoryRuns/views/ccActivityModel.ts';
import { readFactoryEntry, recordHref } from '../src/features/factoryRuns/cc/navigation.ts';

test('a verifier pass never implies worker use, and absence of a declaration stays distinct', () => {
  const activity = {
    capsules: [
      { id: 'verifies', bound_at: 20, uses: [], verifier_declaration: 'declared',
        verifier_records: [{ id: 'verified', created: 40, status: 'pass' }] },
      { id: 'worker', bound_at: 10, uses: [{ id: 'called', created: 30, kind: 'receipt' }],
        verifier_records: [], verifier_declaration: 'none' },
    ],
  };
  assert.deepEqual(capsuleFactsAt(activity, 15).map((fact) => fact.id), ['worker']);
  assert.deepEqual(capsuleFactsAt(activity, 35).map((fact) => [fact.use, fact.verifier]), [
    ['bound-not-used', 'no-cc-verifier-record'], ['used', 'no-verifier-declared'],
  ]);
  assert.deepEqual(capsuleFactsAt(activity, 40).map((fact) => [fact.use, fact.verifier]), [
    ['bound-not-used', 'pass'], ['used', 'no-verifier-declared'],
  ]);
});

test('binding intervals and reopened nodes preserve the recorded time boundary', () => {
  const activity = {
    closures: [
      { id: 'first-closure', decision_id: 'native:decision:1', created: 20, state: 'done' },
      { id: 'reopen', created: 25, state: 'reopened' },
      { id: 'second-closure', decision_id: 'native:decision:4', created: 42, state: 'done' },
    ],
    node_checks: [{ id: 'old-check', created: 19, status: 'pass' }],
    capsules: [{
      id: 'cc', version: '2', uses: [], verifier_declaration: 'declared', verifier_records: [],
      bindings: [{ version: '1', source: { created: 1 }, unbound_at: 25 }, { version: '2', source: { created: 30 } }],
    }],
  };
  assert.equal(capsuleFactsAt(activity, 20)[0].version, '1');
  assert.deepEqual(capsuleFactsAt(activity, 26), []);
  assert.equal(capsuleFactsAt(activity, 31)[0].version, '2');
  assert.equal(nodeVerifierAt(activity, 20, reopenBoundary(activity, 20), true).status, 'pass');
  assert.equal(nodeVerifierAt(activity, 31, reopenBoundary(activity, 31), false).status, 'no-node-check');
  const result = nodeVerifierAt(activity, 42, reopenBoundary(activity, 42), true);
  assert.equal(result.status, 'closed-by-decision');
  assert.equal(result.closure.decision_id, 'native:decision:4');
  assert.equal(readFactoryEntry(recordHref('run-id', result.closure.decision_id)).record, 'native:decision:4');
});
