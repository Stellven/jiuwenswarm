import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
  artifactReplayOrigins,
  capsuleCard,
  contractDiff,
  nodeReplayOrigins,
  replayLabel,
  revisionEvent,
  runOperations,
  unassignedOutputs,
} from '../src/features/factoryRuns/views/nodeEvidenceModel.ts';
import { readDiff } from '../src/features/factoryRuns/views/diffModel.ts';
import { collapseEvents } from '../src/features/factoryRuns/views/storyModel.ts';

test('the contract model makes a readable preliminary-to-final patch with stable object ordering', () => {
  const { patch, before, after } = contractDiff({
    preliminary: { slots: { b: 2, a: 1 }, work: { capability: 'inspect', bound_ccs: [] } },
    final: { work: { bound_ccs: ['weights.reader'], capability: 'inspect' }, slots: { a: 1, b: 2 } },
  });
  assert.match(before, /"a": 1,\n    "b": 2/);
  assert.match(after, /"bound_ccs": \[\n      "weights.reader"/);
  const files = readDiff(patch).files;
  assert.deepEqual(
    files.map(({ previousPath, path }) => [previousPath, path]),
    [['preliminary.json', 'final.json']],
  );
  assert.equal(files[0].added, 3);
  assert.equal(files[0].removed, 1);
  assert.equal(contractDiff({ preliminary: { a: 1, b: 2 }, final: { b: 2, a: 1 } }).patch, undefined);
  assert.equal(contractDiff({ preliminary: null, final: { stage: 'final' } }).before, undefined);
});

test('the capsule card keeps checks and failed history attached to their capsule or output', () => {
  const patch = { id: 'converter', name: 'converter', kind: 'diff' };
  const reviewHistory = [
    { obs_id: 'before', passed: false },
    { obs_id: 'after', passed: true },
  ];
  const output = {
    name: 'converter',
    verifier: 'weights.build_muse_nvfp4_reader.verify',
    review: true,
    review_mode: 'blocking',
    checks: reviewHistory,
  };
  const view = { outputs: [output, { name: 'pack', verifier: 'factory.capped_runner.verify', checks: [] }] };
  const capsule = {
    id: 'weights.build_muse_nvfp4_reader',
    version: '1.2.0',
    kind: 'builder',
    outputs: [patch],
    calls: { count: 3, failures: [{ error: 'fixture absent' }] },
  };
  const model = capsuleCard(capsule, view);
  assert.equal(model.version, '1.2.0');
  assert.equal(model.failures, 1);
  assert.deepEqual(model.checkView.outputs, [output]);
  assert.deepEqual(model.checkView.outputs[0].checks, reviewHistory);
  assert.deepEqual(capsuleCard({ ...capsule, outputs: [], checks: [output] }).checkView.outputs, [output]);
  assert.deepEqual(unassignedOutputs([patch, { id: 'manifest' }], [capsule]), [{ id: 'manifest' }]);
});

test('replayed outputs retain the source run and original duration across views', () => {
  const origin = { run_id: 'muse-2bit-ttft-v4', job_id: 'recorded-job', duration_seconds: 8158 };
  assert.equal(replayLabel(origin), 'Replayed from muse-2bit-ttft-v4, originally 136 min');
  assert.equal(replayLabel([]), undefined);
  assert.equal(replayLabel({}), undefined);
  const event = { kind: 'run', summary: 'Quantize', cursor: 1, created: 1 };
  const replayed = { ...event, cursor: 2, node_id: 'requant', replayed_from: origin };
  assert.equal(collapseEvents([event, replayed]).length, 2);
  assert.equal(nodeReplayOrigins([event, replayed], 1).has('requant'), false);
  assert.deepEqual(nodeReplayOrigins([event, replayed], 2).get('requant'), [origin]);
  const artifacts = artifactReplayOrigins([
    { values: { replayed_from: origin }, source_artifacts: ['pack-manifest'] },
    { values: { kind: 'diff' }, source_artifacts: ['fresh-patch'] },
  ]);
  assert.deepEqual(artifacts.get('pack-manifest'), [origin]);
  assert.equal(artifacts.has('fresh-patch'), false);
});

test('operator actions follow live permissions and show each graph revision in the timeline', () => {
  const controls = { operator: true, pause: true, resume: true, revise: true, revise_apply: true };
  assert.deepEqual(runOperations({ kind: 'bundle' }, controls), []);
  assert.deepEqual(runOperations({ kind: 'live', curated: true }, controls), []);
  assert.deepEqual(runOperations({ kind: 'live' }, null), []);
  assert.deepEqual(runOperations({ kind: 'live' }, { ...controls, revise_apply: false }), [
    'pause',
    'resume',
    'revise-preview',
  ]);
  assert.deepEqual(runOperations({ kind: 'live' }, controls), ['pause', 'resume', 'revise-preview', 'revise-apply']);
  const event = { kind: 'taskgraph_patch', rev: 2, cursor: 1, summary: 'Run revised' };
  assert.equal(revisionEvent(event), 2);
  assert.equal(revisionEvent({ ...event, kind: 'build' }), undefined);
  assert.equal(collapseEvents([event, { ...event, cursor: 2, rev: 3 }]).length, 2);
});

const recordedPath = process.env.FACTORY_NODE_EVIDENCE_SAMPLE;
if (recordedPath) {
  test('recorded node responses preserve their bindings, artifacts and readable contract changes', () => {
    const nodes = JSON.parse(readFileSync(recordedPath, 'utf8'));
    const cards = nodes.flatMap((node) => node.capsules.map((row) => capsuleCard(row)));
    assert.ok(cards.some((card) => card.version && card.calls?.count > 0));
    assert.ok(cards.some((card) => card.outputs?.some((output) => output.artifact_ids.length > 0)));
    assert.ok(
      cards.some((card) => card.checkView?.outputs.some((output) => output.checks.some((check) => check.passed))),
    );
    assert.ok(
      nodes.some((node) => {
        const patch = contractDiff(node.contract).patch;
        return patch && readDiff(patch)?.files.length;
      }),
    );
  });
}

test('featured and historical sources remain visible alongside the Nov 20 demos', async () => {
  const { groupRunEntries, runListEntries } = await import('../src/features/factoryRuns/views/runListModel.ts');
  const run = (id, extra) => ({ id, name: id, kind: 'live', status: 'live', updated: 1, ...extra });
  const groups = groupRunEntries(
    runListEntries([
      run('r8', { featured: true, demo: true }),
      run('v4', { read_only: true }),
      run('nov20', { demo: true }),
      run('scratch', { scratch: true }),
    ]),
  );
  assert.deepEqual(
    groups.featured.map(({ run }) => run.id),
    ['r8'],
  );
  assert.deepEqual(
    groups.history.map(({ run }) => run.id),
    ['v4'],
  );
  assert.deepEqual(
    groups.demo.map(({ run }) => run.id),
    ['nov20'],
  );
  assert.equal(groups.hidden, 1);
});

test('native story node links preserve the historical task graph and highlight the revised node', async () => {
  const { detectGraph, graphProgress } = await import('../src/features/factoryRuns/views/graphModel.ts');
  const nodes = [
    { node_id: 'pin', title: 'Pin', state: 'done', depends_on: [] },
    { node_id: 'batch', title: 'Batch', state: 'proposed', depends_on: ['pin'] },
  ];
  const graph = detectGraph({
    schema: 'factory.taskgraph/1',
    task_id: 'r8',
    nodes,
    history: [
      { rev: 1, created: 1, patch: { add: nodes.map((node) => ({ ...node, state: 'proposed' })) } },
      {
        rev: 2,
        created: 2,
        patch: { revise: [{ action: 'update', node_id: 'batch', depends_on: ['pin'], check: 'new' }] },
      },
    ],
  });
  const events = [
    { id: 'r8:plan:1', kind: 'taskgraph_patch', summary: 'Seed', cursor: 1, created: 1 },
    { id: 'r8:plan:2', kind: 'revise', rev: 2, summary: 'Update batch', cursor: 2, created: 2, graph_nodes: ['batch'] },
  ];
  const progress = graphProgress(graph, { events, position: 2 });
  assert.equal(progress.get('step:pin').phase, 'seen');
  assert.equal(progress.get('step:batch').phase, 'current');
  assert.equal(progress.get('step:batch').details.check, 'new');
  assert.equal(revisionEvent(events[1]), 2);
});
