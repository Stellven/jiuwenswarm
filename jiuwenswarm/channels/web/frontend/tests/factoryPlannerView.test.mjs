import assert from 'node:assert/strict';
import test from 'node:test';
import { comparisonDraft, draftChain } from '../src/features/factoryRuns/views/plannerViewModel.ts';

test('the Plan chain uses only the planner’s recorded order', () => {
  assert.deepEqual(draftChain(null), []);
  const recorded = {
    plan_order: ['first', 'removed', 'last'],
    run_order: ['last', 'first', 'added'],
    nodes: ['added', 'removed', 'last', 'first'].map((node_id) => ({ node_id })),
  };
  assert.deepEqual(draftChain(recorded).map((node) => node.node_id), ['first', 'removed', 'last']);
});

test('each scheduler final shows only the draft tied to its preliminary digest', () => {
  const original = { objective: 'Original planner objective' };
  const updated = { objective: 'Amended draft objective' };
  const draftSource = { digest: 'updated' };
  const node = {
    draft: original,
    finals: [
      { preliminary_digest: 'missing', preliminary: null },
      { preliminary_digest: 'updated', preliminary: updated, preliminary_source: draftSource },
    ],
  };
  assert.equal(comparisonDraft(node).draft, updated);
  assert.equal(comparisonDraft(node).source, draftSource);
  assert.equal(comparisonDraft(node, 0).draft, null);
  assert.equal(comparisonDraft({ ...node, finals: [] }).draft, original);
});
