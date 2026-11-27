import assert from 'node:assert/strict';
import test from 'node:test';
import { detectGraph, graphProgress, taskGraphTimeline } from '../src/features/factoryRuns/views/graphModel.ts';

const taskId = 'spark-prefill';
const contractId = 'spark-prefill-main';
const cc = 'engine.build_expert_weight_cache';
const inspect = { node_id: 'inspect', title: 'Inspect evidence', kind: 'inspect', depends_on: [] };
const build = { node_id: 'build', title: 'Build candidate', kind: 'build', depends_on: ['inspect'], capability: cc };
const contract = { contract_id: contractId, ontology: { capsule_slices: [{ capsule: cc, path: 'ONTOLOGY.yaml' }] } };

test('native dependencies point toward dependents and retain supersession links', () => {
  const native = detectGraph({
    schema: 'factory.taskgraph/1',
    task_id: taskId,
    nodes: [{ ...inspect, state: 'superseded', superseded_by: 'build' }, build],
  });
  assert.equal(native.kind, 'taskgraph');
  assert.equal(native.nodes.find((node) => node.id === 'step:inspect').state, 'superseded');
  assert.deepEqual(
    native.links.map(({ source, target, kind }) => [source, target, kind]),
    [
      ['step:inspect', 'step:build', 'superseded'],
      ['step:inspect', 'step:build', 'dependency'],
      ['step:build', `capsule:${cc}`, 'capsule'],
    ],
  );
});

test('an older exported run can show its contract, task and declared capsule without plan patches', () => {
  const model = detectGraph(
    { schema: 'factory.taskgraph/1', task_id: taskId, nodes: [], history: [] },
    {
      contract,
      tasks: [
        {
          task_id: taskId,
          contract_id: '/exports/frozen-contract.json',
          component_cc: cc,
          resources: { capsules: [`${cc}@1.1.2`] },
        },
      ],
    },
  );
  assert.deepEqual(
    model.nodes.map((node) => node.kind),
    ['contract', 'task', 'capsule'],
  );
  assert.equal(model.nodes[2].details.reference, `${cc}@1.1.2`);
  assert.deepEqual(
    model.links.map(({ source, target }) => [source, target]),
    [
      [`contract:${contractId}`, `task:${taskId}`],
      [`task:${taskId}`, `capsule:${cc}`],
    ],
  );
  assert.deepEqual(
    detectGraph(contract).nodes.map(({ kind }) => kind),
    ['contract', 'capsule'],
  );
});

test('ontology maps and explicit endpoint arrays retain relation names and entity descriptions', () => {
  const yamlShape = detectGraph({
    entities: { component: 'Expert cache within weight residency.' },
    relations: { modifies_region: 'component -> engine region', measures: 'observation_point -> quantity' },
  });
  assert.equal(yamlShape.kind, 'ontology');
  assert.equal(
    yamlShape.nodes.find((node) => node.id === 'entity:component').details.description,
    'Expert cache within weight residency.',
  );
  assert.deepEqual(
    yamlShape.links.map(({ source, target, label }) => [source, target, label]),
    [
      ['entity:component', 'entity:engine region', 'modifies_region'],
      ['entity:observation_point', 'entity:quantity', 'measures'],
    ],
  );
  const structured = detectGraph({ relations: [{ source: 'A', target: 'B', relation: 'contains' }] });
  assert.equal(structured.links[0].label, 'contains');
});

test('owner Mermaid block syntax keeps labels and grouping without executing directives', () => {
  const model = detectGraph(`%%{init: {"flowchart":{"htmlLabels":false}}}%%
block-beta
  columns 3
  block:g_layer[" "]
    columns 1
    h_layer["Model forward + MoE ↗"]
    op_embedding["Embeddings + norm / residual"]
    op_attention["Attention ↔ sequence state"]
  end
  style g_layer fill:#ebeff7,stroke:#a6bcb7
  click op_attention href "javascript:example()"`);
  assert.equal(model.kind, 'ontology');
  assert.equal(model.nodes.find((node) => node.id === 'group:g_layer').label, 'Model forward + MoE ↗');
  assert.deepEqual(
    model.links.map(({ kind, source, target }) => [kind, source, target]),
    [
      ['member', 'group:g_layer', 'entity:op_embedding'],
      ['member', 'group:g_layer', 'entity:op_attention'],
    ],
  );
  assert.ok(model.nodes.every((node) => !('href' in node.details)));
});

test('plain data and malformed relation shapes do not produce spurious graphs', () => {
  assert.equal(detectGraph({ nodes: [{ id: 4, title: 'Metric' }] }), null);
  assert.equal(detectGraph({ relations: { component: 'a non-directional description' } }), null);
  assert.equal(detectGraph('block-beta\n block:incomplete["Incomplete"]\n child["Child"]'), null);
});

test('replay highlights committed patches and attempt events while restoring past node state', () => {
  const graph = detectGraph({
    schema: 'factory.taskgraph/1',
    task_id: taskId,
    nodes: [
      { ...inspect, state: 'done' },
      { ...build, state: 'done', attempt_ids: ['try-build'] },
    ],
    history: [
      { rev: 1, decision_rev: 0, created: 10, patch: { add: [inspect] } },
      {
        rev: 2,
        decision_rev: 1,
        created: 20,
        patch: {
          add: [{ ...build, state: 'running', attempt_ids: ['try-build'] }],
          update: [{ node_id: 'inspect', state: 'done', evidence_ids: ['result:inspection'] }],
        },
      },
      {
        rev: 3,
        decision_rev: 1,
        created: 40,
        patch: { update: [{ node_id: 'build', state: 'done', evidence_ids: ['result:build'] }] },
      },
    ],
  });
  const events = [
    { id: 'earlier-same-timestamp', created: 10 },
    { id: `${taskId}:plan:1`, created: 10 },
    { id: `${taskId}:plan:2`, created: 20 },
    { id: 'try-build:0', created: 30 },
    { id: `${taskId}:plan:3`, created: 40 },
  ];
  const initial = graphProgress(graph, { events, position: 1 });
  assert.equal(initial.get('step:inspect').phase, 'upcoming');
  assert.equal(initial.get('step:build').details, undefined);
  const seed = graphProgress(graph, { events, position: 2 });
  assert.equal(seed.get('step:inspect').phase, 'current');
  assert.equal(seed.get('step:inspect').details.state, 'proposed');
  assert.equal(seed.get('step:build').phase, 'upcoming');
  const running = graphProgress(graph, { events, position: 4 });
  assert.equal(running.get('step:build').phase, 'current');
  assert.equal(running.get('step:build').details.state, 'running');
  assert.deepEqual(running.get('step:build').details.evidence_ids, []);
  assert.equal(running.get('step:inspect').phase, 'seen');
  const done = graphProgress(graph, { events, position: 5 });
  assert.equal(done.get('step:build').details.state, 'done');
  assert.deepEqual(done.get('step:build').details.attempt_ids, ['try-build']);
});

test('the task chain follows native completion order across curated steps', () => {
  const packageNode = { node_id: 'package', depends_on: ['inspect'] };
  const graph = detectGraph(
    {
      schema: 'factory.taskgraph/1',
      task_id: taskId,
      nodes: [inspect, build, packageNode].map((node) => ({ ...node, state: 'done' })),
      history: [
        { rev: 1, created: 10, patch: { add: [inspect, build, packageNode] } },
        { rev: 2, created: 30, patch: { update: [{ node_id: 'inspect', state: 'done' }] } },
        { rev: 3, created: 50, patch: { update: [{ node_id: 'package', state: 'done' }] } },
        {
          rev: 4,
          created: 70.01,
          origin: 'decision',
          decision_rev: 7,
          patch: { update: [{ node_id: 'build', state: 'done' }] },
        },
      ],
    },
    { contract, tasks: [{ task_id: taskId, contract_id: contractId }] },
  );
  const events = [
    { id: taskId, created: 10, kind: 'task' },
    { id: 'scheduling-summary', created: 63, kind: 'node_contract_final', graph_nodes: ['build', 'inspect'] },
    { id: 'check-build', created: 45, kind: 'node_check', graph_nodes: ['build'] },
    { id: 'read-package', created: 60, kind: 'observation' },
    { id: `${taskId}:decision:7`, created: 70, kind: 'decision' },
  ];
  const at = (position) =>
    taskGraphTimeline(graph, { events, position, curated: { steps: [] } }).map(({ planId, replayState }) => [
      planId,
      replayState,
    ]);
  assert.deepEqual(at(1), [['inspect', 'current'], ['package', 'not-reached'], ['build', 'not-reached']]);
  assert.deepEqual(at(2), at(1));
  assert.deepEqual(at(3), [['inspect', 'done'], ['package', 'current'], ['build', 'not-reached']]);
  assert.deepEqual(at(4), [['inspect', 'done'], ['package', 'done'], ['build', 'current']]);
  assert.deepEqual(at(5), [['inspect', 'done'], ['package', 'done'], ['build', 'done']]);
});

test('reopen resets downstream progress until the native terminal stop is reached', () => {
  const release = { node_id: 'release', depends_on: ['build'] };
  const graph = detectGraph({
    schema: 'factory.taskgraph/1',
    task_id: taskId,
    nodes: [inspect, build, release],
    history: [
      { rev: 1, created: 10, patch: { add: [inspect, build, release] } },
      { rev: 2, created: 20, patch: { update: [{ node_id: 'inspect', state: 'done' }] } },
      { rev: 3, created: 30, patch: { update: [{ node_id: 'build', state: 'done' }] } },
      { rev: 4, created: 35, patch: { reopen: [{ node_id: 'inspect', reason: 'Recheck inputs' }] } },
      { rev: 5, created: 40, patch: { update: [{ node_id: 'inspect', state: 'done' }] } },
    ],
  });
  const events = [
    { id: `${taskId}:plan:3`, created: 30 },
    { id: `${taskId}:plan:4`, created: 35 },
    { id: `${taskId}:plan:5`, created: 40 },
    { id: 'terminal-record', created: 45 },
  ];
  const runState = { state: 'stopped', since: 45, source: 'terminal-record' };
  const at = (position) => taskGraphTimeline(graph, { events, position, runState }).map(({ replayState }) => replayState);
  assert.deepEqual(at(1), ['done', 'done', 'current']);
  assert.deepEqual(at(2), ['current', 'not-reached', 'not-reached']);
  assert.deepEqual(at(3), ['done', 'current', 'not-reached']);
  assert.deepEqual(at(4), ['done', 'stopped', 'stopped']);
  assert.deepEqual(at(2), ['current', 'not-reached', 'not-reached']);
});

test('the chain gets capsule IDs from the exact admitted final node contract', () => {
  const final = (node, digest, bound_ccs, task_id = taskId) => ({
    task_id,
    kind: 'node_contract_final',
    values: { node_id: node, digest, final: { work: { bound_ccs } } },
  });
  const graph = detectGraph(
    {
      schema: 'factory.taskgraph/1',
      task_id: taskId,
      nodes: [inspect, { ...build, final_contract: 'bound' }],
    },
    {
      observations: [
        final('build', 'bound', ['factory.builder', 'engine.kv_reuse_lab']),
        final('build', 'older', ['factory.source_workbench']),
        final('inspect', 'bound', ['factory.capped_runner']),
        final('build', 'bound', ['factory.node_check'], 'different-task'),
      ],
    },
  );
  assert.deepEqual(taskGraphTimeline(graph).map(({ boundCCs }) => boundCCs), [[], ['factory.builder', 'engine.kv_reuse_lab']]);
});
