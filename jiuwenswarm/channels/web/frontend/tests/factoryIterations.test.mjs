import assert from 'node:assert/strict';
import test from 'node:test';
import { buildIterations } from '../src/features/factoryRuns/iterationModel.ts';

const file = (path, ids) => ({ path, artifact_ids: ids, sha256: 'digest', integrity: 'verified', size: 1 });

test('connects a specific report to a later plan only by recorded evidence ID', () => {
  const records = {
    factory_loop_cycles: [
      { cycle_id: 'first', number: 1, record: { decision_rev: 1, evidence_id: 'report:1', attempt_id: 'a' } },
      { cycle_id: 'second', number: 2, record: { decision_rev: 2, evidence_id: 'report:2' } },
    ],
    decisions: [
      { rev: 1, action: { type: 'build', cycle_id: 'first', capsules: ['builder.example'], template_id: 'pilot' } },
      { rev: 2, parent_rev: 1, action: { cycle_id: 'second', template_id: 'main' }, evidence_ids: ['report:1'] },
      { rev: 3, parent_rev: 2, action: { template_id: 'unrelated' }, evidence_ids: ['other'] },
    ],
    observations: [
      { obs_id: 'report:1', kind: 'factory_loop_result', values: { verdict: 'pilot_ok' } },
      { obs_id: 'report:2', kind: 'factory_loop_result', values: { verdict: 'accept' } },
      {
        obs_id: 'attributed',
        kind: 'gap_attribution',
        values: { cycle_id: 'first' },
        source_artifacts: ['phase-breakdown.json'],
      },
      { obs_id: 'not-attributed', kind: 'gap_attribution', values: {} },
    ],
    attempts: [{ attempt_id: 'a', result_refs: ['build.patch'] }],
  };
  const iterations = buildIterations(records, [
    file('build.patch', ['build.patch']),
    file('phase-breakdown.json', ['phase-breakdown.json']),
    file('unrelated.patch', ['unrelated.patch']),
  ]);
  assert.deepEqual(
    iterations.map(({ id }) => id),
    ['first', 'second'],
  );
  assert.deepEqual(
    iterations[0].linkedFiles.map(({ kind }) => kind),
    ['diff', 'analysis'],
  );
  assert.deepEqual(iterations[0].capsuleIds, ['builder.example']);
  assert.deepEqual(
    iterations[0].analysisObservations.map(({ obs_id }) => obs_id),
    ['attributed'],
  );
  assert.equal(iterations[0].reportData.verdict, 'pilot_ok');
  assert.deepEqual(
    iterations[0].nextDecisions.map(({ decision, cited }) => [decision.rev, cited]),
    [[2, ['report:1']]],
  );
  assert.deepEqual(iterations[1].nextDecisions, []);
});

test('recovers old cycles from highest factory_loop observation and identifies operator provenance', () => {
  const [iteration] = buildIterations(
    {
      observations: [
        { kind: 'factory_loop', values: { cycle: { cycle_id: 'cycle', number: 2, event: 2, state: 'collected' } } },
        { kind: 'factory_loop', values: { cycle: { cycle_id: 'cycle', number: 2, event: 1, state: 'selected' } } },
        { kind: 'operator_orchestration', values: { cycle_id: 'cycle', llm_agent: false } },
        { kind: 'factory_loop_result', obs_id: 'sourced-analysis', values: { cycle_id: 'cycle', status: 'succeeded' } },
      ],
    },
    [],
  );
  assert.equal(iteration.number, 2);
  assert.equal(iteration.state, 'collected');
  assert.equal(iteration.operator, true);
  assert.equal(iteration.resultId, 'sourced-analysis');
  assert.deepEqual(buildIterations({ decisions: [{ rev: 1, action: { type: 'inspect' } }] }, []), []);
});

test('reads the new report observation schema, artifact scope, and the next plan citation', () => {
  const observe = (id, values) => ({
    kind: 'factory_iteration_report',
    obs_id: `iteration:${id}`,
    values: { schema: 'spark-factory-iteration/1', iteration_id: id, ...values },
  });
  const [baseline, next] = buildIterations({
    tasks: [{ task_id: 'campaign' }],
    observations: [
      observe('baseline', {
        plan: { rationale: 'Run controls', builder_ccs: [] },
        lab: { status: 'historical-reconnaissance', result_artifact_ids: ['timing.json'] },
        analysis: { ccs: [{ id: 'analysis.gap' }], output_artifact_ids: ['phases.json'] },
        report: { artifact_id: 'report.md', sha256: 'pinned', status: 'historical-reconnaissance' },
      }),
      observe('candidate', {
        plan: { decision_id: 'campaign:decision:4', incoming_report_ids: ['report.md'], builder_ccs: [{ id: 'builder.recorder' }] },
        do: { diff_artifact_id: { task_id: 'candidate-home-task', artifact_id: 'change.patch', sha256: 'remote' } },
      }),
    ],
    decisions: [{ decision_id: 'campaign:decision:4', rev: 4, evidence_ids: ['report.md'], hypothesis: 'Instrument prefill' }],
  }, [
    file('report.md', ['report.md']),
    file('phases.json', ['phases.json']),
    file('timing.json', ['timing.json']),
    file('unrelated-local.patch', ['change.patch']),
  ]);
  assert.equal(baseline.linkedNextId, 'candidate');
  assert.equal(baseline.labState, 'historical-reconnaissance');
  assert.equal(baseline.linkedFiles[0].file.integrity, 'mismatch');
  assert.deepEqual(baseline.analysisCapsules, ['analysis.gap']);
  assert.equal(next.plan.hypothesis, 'Instrument prefill');
  assert.deepEqual(next.capsuleIds, ['builder.recorder']);
  assert.deepEqual(next.linkedFiles, []);
  assert.deepEqual(next.remoteReferences[0], {
    id: 'change.patch', taskId: 'candidate-home-task', sha256: 'remote', kind: 'diff',
  });
});

test('an operator report without an originating decision can still be cited by a later plan', () => {
  const [iteration] = buildIterations({
    observations: [{
      kind: 'factory_iteration_report',
      obs_id: 'baseline:report',
      created: 12,
      values: { schema: 'spark-factory-iteration/1', iteration_id: 'baseline', report: { artifact_id: 'r.md' } },
    }],
    decisions: [
      { rev: 1, created: 10, evidence_ids: ['r.md'] },
      { rev: 2, created: 13, evidence_ids: ['r.md'] },
    ],
  }, []);
  assert.deepEqual(iteration.nextDecisions.map(({ decision }) => decision.rev), [2]);
});

test('separates predecessor context from planner input and preserves citations to superseded reports', () => {
  const observe = (id, obs_id, values) => ({
    kind: 'factory_iteration_report',
    obs_id,
    values: { schema: 'spark-factory-iteration/1', iteration_id: id, ...values },
  });
  const first = observe('first', 'first:report', { report: { artifact_id: 'report.md', revision: 1 } });
  const second = observe('first', 'first:report:v2', { report: { artifact_id: 'report-v2.md', revision: 2 } });
  const followup = observe('second', 'second:report', {
    predecessor_report_ids: [{ task_id: 'campaign', artifact_id: 'report.md' }],
    plan: { incoming_report_ids: [] },
  });
  const iterations = buildIterations({ observations: [first, second, followup, first] }, []);
  assert.equal(iterations[0].reportId, 'report-v2.md');
  assert.equal(iterations[0].reportAliases.get('first:report'), 'report.md');
  assert.equal(iterations[0].linkedNextId, '');
  assert.deepEqual(iterations[1].inputs, []);
  assert.equal(iterations[1].remoteReferences[0].kind, 'prior');
});
