import assert from 'node:assert/strict';
import test from 'node:test';
import { projectResearchWorkflow } from '../node_modules/.cache/research-shell/components/teamArea/researchWorkflow.js';

const fixture = {
  run_id: 'run:1',
  client_request_id: 'request:1',
  revision: 3,
  status: 'in_progress',
  stage: 'screening',
  candidate_refs: [{ id: 'candidate', sha256: 'a'.repeat(64) }],
  accepted_refs: [],
  reasons: [],
  node_statuses: [
    { node_id: 'screening', attempt_id: 'attempt:1', lifecycle_status: 'Evaluating', skipped_because: null },
  ],
};

test('evaluating candidates are visible without claiming completion or acceptance', () => {
  const value = projectResearchWorkflow(fixture);
  assert.equal(value.completed_agent_count, 0);
  assert.equal(value.phases[0].description, 'Evaluating');
  assert.equal(value.recovered, true);
  assert.deepEqual(value.research.accepted_refs, []);
  assert.equal(value.research.candidate_refs.length, 1);
});

test('negative scientific outcomes do not turn completed infrastructure into a failure', () => {
  const value = projectResearchWorkflow({
    ...fixture,
    status: 'completed',
    node_statuses: [{ ...fixture.node_statuses[0], lifecycle_status: 'Completed' }],
  });
  assert.equal(value.status, 'completed');
  assert.equal(value.completed_agent_count, 1);
  assert.equal(projectResearchWorkflow({ ...fixture, status: 'partial' }).status, 'failed');
});

for (const status of ['in_progress', 'halted']) {
  test(`finite ${status} before a node preserves empty stage and no manufactured phases`, () => {
    const reasons = status === 'halted' ? ['finite_fixture'] : [];
    const value = projectResearchWorkflow({
      ...fixture, status, stage: '', candidate_refs: [], accepted_refs: [], reasons, node_statuses: [],
    });
    assert.equal(value.summary, '');
    assert.equal(value.status, status === 'in_progress' ? 'running' : 'failed');
    assert.deepEqual(value.phases, []);
    assert.equal(value.agent_count, 0);
    assert.equal(value.completed_agent_count, 0);
    assert.deepEqual(value.research.reasons, reasons);
    assert.equal(value.error, reasons.length ? 'finite_fixture' : undefined);
    assert.ok(!JSON.stringify(value).includes('intention_compiler'));
  });
}
