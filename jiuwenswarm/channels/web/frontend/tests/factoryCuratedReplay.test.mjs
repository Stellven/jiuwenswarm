import assert from 'node:assert/strict';
import test from 'node:test';
import {
  collapseEvents,
  curatedStepFor,
  keyFilesFor,
  keyFlags,
  presentEvent,
  recordedCheckRoles,
} from '../src/features/factoryRuns/views/storyModel.ts';
import {
  collapsibleNodes,
  detectGraph,
  graphProgress,
  hiddenUnder,
  visibleGraphNodes,
} from '../src/features/factoryRuns/views/graphModel.ts';
import { groupRunEntries, runListEntries } from '../src/features/factoryRuns/views/runListModel.ts';

const event = (cursor, kind, summary, extra = {}) => ({ id: `e${cursor}`, cursor, created: cursor, kind, summary, ...extra });

const curated = {
  schema: 'factory.curated-replay/1',
  title: 'Replay 1',
  summary: 'Curated replay: selected real records from 1 factory home',
  source_homes: ['home'],
  steps: [
    {
      step: 1,
      presentation_title: 'The task',
      original_kind: 'task',
      graph_nodes: ['contract:star-deepseek-v1', 'step:inspect'],
      key_files: [
        { path: 'evidence/a/contract.json', label: 'Task contract · star-deepseek-v1.json', why: 'The contract' },
        { path: 'evidence/a/missing.json', label: 'Not bundled', why: 'Dropped' },
      ],
    },
    {
      step: 2,
      presentation_title: 'The build',
      original_kind: 'build',
      graph_nodes: ['step:build'],
      key_files: [{ path: 'evidence/a/receipt.json', label: 'Build receipt · 32b595d1', why: 'Binary sha' }],
    },
  ],
};
const files = [
  { path: 'evidence/a/contract.json', sha256: 'a', integrity: 'verified', size: 1 },
  { path: 'evidence/a/receipt.json', sha256: 'b', integrity: 'verified', size: 1 },
];

test('a curated step shows its presentation title next to the original kind', () => {
  const shown = presentEvent(event(1, 'task', 'objective', { presentation_title: 'The task', step: 1 }));
  assert.deepEqual(shown, { title: 'The task', kind: 'task', curated: true });
});

test('step badges reflect cited checks and keep delivery acceptance distinct from method verification', () => {
  const ref = (id) => ({ table: 'observations', id, source_home: 'home' });
  const observations = [
    { obs_id: 'final', kind: 'node_contract_final' },
    { obs_id: 'check', kind: 'node_check', values: { node_id: 'plan', output: 'plan', refs: { evidence_ids: ['final', 'load'] } } },
    { obs_id: 'acceptance', kind: 'node_check', values: { node_id: 'measure', output: 'report', refs: { evidence_ids: ['load'] } } },
  ];
  const presentation = {
    plan: { checks: { plan: { role: 'Node verifier', verifier_role: 'CC verifier' } } },
    measure: { checks: { report: { role: 'Lab acceptance' } } },
  };
  const selected = (kind, ...records) => ({ ...curated.steps[0], original_kind: kind, node_id: 'measure', records });
  assert.deepEqual(recordedCheckRoles(selected('node_check', ref('check'), ref('final')), observations, presentation), [
    'CC verifier', 'Node verifier',
  ]);
  assert.deepEqual(recordedCheckRoles(selected('node_contract_final', ref('final')), observations, presentation), ['Scheduler']);
  assert.deepEqual(recordedCheckRoles(selected('capped_run', ref('load')), observations, presentation), ['Node verifier', 'Lab agent']);
  const report = selected('r8-final-bench', { table: 'file', id: 'evidence/lab/report.json' });
  assert.deepEqual(recordedCheckRoles(report, observations, presentation), ['Lab agent']);
  assert.deepEqual(recordedCheckRoles({ ...selected('attempt'), stages: ['runtime'] }, observations, presentation), []);
});

test('raw kinds get a readable title and keep the original kind', () => {
  assert.equal(presentEvent(event(1, 'factory_iteration_summary', 's')).title, 'Iteration summary recorded');
  assert.equal(presentEvent(event(1, 'factory_iteration_successors', 's')).title, 'Next iterations proposed');
  assert.equal(presentEvent(event(1, 'replan/build', 's')).title, 'Replan: native build');
  assert.equal(presentEvent(event(1, 'operator_steering', 's')).title, 'Operator steering');
  assert.equal(presentEvent(event(1, 'operator_steering', 's')).kind, 'operator_steering');
});

test('consecutive identical summary events collapse into one entry with a count', () => {
  const groups = collapseEvents([
    event(1, 'factory_iteration_summary', 'same'),
    event(2, 'factory_iteration_summary', 'same'),
    event(3, 'factory_iteration_summary', 'same'),
    event(4, 'build', 'ok'),
    event(5, 'factory_iteration_summary', 'same'),
  ]);
  assert.deepEqual(
    groups.map(({ event, count, first, last }) => [event.kind, count, first, last]),
    [
      ['factory_iteration_summary', 3, 1, 3],
      ['build', 1, 4, 4],
      ['factory_iteration_summary', 1, 5, 5],
    ],
  );
});

test('key files resolve to bundled files for the current step only', () => {
  const step = curatedStepFor(curated, event(1, 'task', 'o', { step: 1 }));
  assert.equal(step.presentation_title, 'The task');
  assert.deepEqual(
    keyFilesFor(step, files).map(({ key, file }) => [key.label, file.path]),
    [['Task contract · star-deepseek-v1.json', 'evidence/a/contract.json']],
  );
  assert.equal(curatedStepFor(curated, event(9, 'x', 'y')), undefined);
  const flags = keyFlags(curated);
  assert.deepEqual(flags.get('evidence/a/receipt.json').map((flag) => flag.step), [2]);
});

const graph = detectGraph({
  schema: 'factory.taskgraph/1',
  task_id: 'do',
  nodes: [
    { node_id: 'inspect', title: 'Inspect', kind: 'inspect', depends_on: [] },
    { node_id: 'integrate', title: 'Integrate', kind: 'integrate', depends_on: ['inspect'] },
    { node_id: 'build', title: 'Build', kind: 'build', depends_on: ['integrate'] },
    { node_id: 'report', title: 'Report', kind: 'report', depends_on: ['build'] },
  ],
}, { contract: { contract_id: 'star-deepseek-v1' }, tasks: [{ task_id: 'do', contract_id: 'star-deepseek-v1' }] });

test('collapsing a node hides its descendants and expanding brings them back', () => {
  const all = visibleGraphNodes(graph, new Set());
  assert.equal(all.size, graph.nodes.length);
  const collapsed = visibleGraphNodes(graph, new Set(['step:integrate']));
  assert.ok(collapsed.has('step:integrate'));
  assert.ok(!collapsed.has('step:build') && !collapsed.has('step:report'));
  assert.equal(hiddenUnder(graph, 'step:integrate', collapsed), 2);
  const none = visibleGraphNodes(graph, collapsibleNodes(graph));
  assert.deepEqual([...none], ['contract:star-deepseek-v1']);
  assert.equal(visibleGraphNodes(graph, new Set()).size, graph.nodes.length);
});

test('curated steps light nodes as the replay advances and highlight the current step', () => {
  const events = [
    event(1, 'task', 'o', { step: 1, graph_nodes: ['contract:star-deepseek-v1', 'step:inspect'] }),
    event(2, 'build', 'b', { step: 2, graph_nodes: ['step:build'] }),
  ];
  const first = graphProgress(graph, { events, position: 1 });
  assert.equal(first.get('step:inspect').phase, 'current');
  assert.equal(first.get('contract:star-deepseek-v1').phase, 'current');
  assert.equal(first.get('step:build').phase, 'upcoming');
  const second = graphProgress(graph, { events, position: 2 });
  assert.equal(second.get('step:inspect').phase, 'seen');
  assert.equal(second.get('step:build').phase, 'current');
  assert.equal(second.get('step:report').phase, 'upcoming');
});

test('the default run list shows only demo replays; scratch homes and older exports need show everything', () => {
  const run = (id, extra) => ({ id, name: id, task_id: id, kind: 'bundle', status: 'replay', updated: 1, ...extra });
  const entries = runListEntries([
    run('replay-2', { demo: true, demo_order: 2 }),
    run('replay-1', { demo: true, demo_order: 1 }),
    run('export', {}),
    run('old-export', { duplicate: true }),
    run('web-home', { kind: 'live', status: 'live', scratch: true }),
  ]);
  const quiet = groupRunEntries(entries);
  assert.deepEqual(quiet.demo.map(({ run }) => run.id), ['replay-1', 'replay-2']);
  assert.deepEqual(quiet.rest.map(({ run }) => run.id), ['export']);
  assert.equal(quiet.hidden, 2);
  assert.deepEqual(groupRunEntries(entries, true).rest.map(({ run }) => run.id), ['export', 'old-export', 'web-home']);
});
