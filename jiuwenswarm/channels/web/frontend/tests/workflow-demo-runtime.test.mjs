import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  factoryClient,
  isTerminal,
  statusColor,
  pretty,
  readEventStream,
  parseEngineeringTask,
} from '../node_modules/.cache/factory-ui/factoryClient.js';
import { layoutGraph, edgePath, edgeDeliveryStatus } from '../node_modules/.cache/factory-ui/graphLayout.js';
import { userGoalSelection } from '../node_modules/.cache/factory-ui/copy.en.js';

// Transport substitution is confined to this unit test; production always uses the API.
test('client sends engineering goals and preserves actual backend blocked states', async () => {
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (path, options) => {
    calls.push({ path, options });
    return new Response(
      JSON.stringify({ id: 'real-run-id', status: 'blocked', nodes: [], error: { code: 'sdk_missing' } }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    );
  };
  try {
    const body = {
      goals: ['build.binary', 'inference.result'],
      repository_url: 'https://github.com/niko1221/strata',
      target_backend: 'ascend',
      model_path: '/models/weights',
    };
    const result = await factoryClient.start(body);
    assert.equal(calls[0].path, '/api/v1/factory/runs');
    assert.equal(calls[0].options.method, 'POST');
    assert.deepEqual(JSON.parse(calls[0].options.body), body);
    assert.equal(result.status, 'blocked');
    assert.deepEqual(result.nodes, []);
    assert.equal(result.error.code, 'sdk_missing');
    await factoryClient.events('run/id', 42);
    assert.equal(calls[1].path, '/api/v1/factory/runs/run%2Fid/events?after=42');
  } finally {
    globalThis.fetch = original;
  }
});

test('API failure propagates instead of replacing execution with a demo', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response('Factory unavailable', { status: 503 });
  try {
    await assert.rejects(factoryClient.catalog(), /Factory API 503: Factory unavailable/);
  } finally {
    globalThis.fetch = original;
  }
});

test('terminal and status color mapping never converts blocked into successful', () => {
  for (const status of ['completed', 'blocked', 'failed']) assert.ok(isTerminal(status));
  for (const status of ['created', 'planning', 'running', 'pending']) assert.ok(!isTerminal(status));
  assert.equal(statusColor('blocked'), 'blocked');
  assert.equal(statusColor('failed'), 'failed');
  assert.equal(statusColor('created'), 'pending');
  assert.equal(statusColor('completed'), 'verified');
  assert.equal(pretty({ exit_code: 1 }), '{\n  "exit_code": 1\n}');
});

test('graph positions derive only from backend node/dependency sets, including recovery cycles', () => {
  const node = (id) => ({
    id,
    name: id,
    stage_id: id,
    workflow_id: 'engineering',
    subworkflow_id: 'build',
    status: 'pending',
    attempts: [],
  });
  const nodes = ['analyze', 'acquire', 'build'].map(node);
  const edges = [
    { from: 'acquire', to: 'analyze', data: 'source.checkout' },
    { from: 'analyze', to: 'build', data: 'source.analysis' },
  ];
  const result = layoutGraph(nodes, edges);
  assert.deepEqual(Object.keys(result.positions), ['acquire', 'analyze', 'build']);
  assert.equal(Object.keys(result.positions).length, nodes.length);
  assert.ok(edgePath(result.positions.acquire, result.positions.analyze).d.includes('H'));
  const recovery = layoutGraph(
    [...nodes, node('repair')],
    [...edges, { from: 'build', to: 'repair', data: 'failure' }, { from: 'repair', to: 'build', data: 'toolchain' }],
  );
  assert.equal(Object.keys(recovery.positions).length, 4);
  assert.ok(Number.isFinite(recovery.height));
});

test('production component has no source demo data, fixture, or timed execution imports', async () => {
  const code = await readFile(new URL('../src/features/workflowDemo/WorkflowDemo.tsx', import.meta.url), 'utf8');
  assert.doesNotMatch(code, /from ['"]\.\/(?:runtime|fixtures|data\/)/);
  assert.doesNotMatch(code, /eventsFor|applyEvent|matched_subworkflows|failed_then_retried/);
  assert.match(code, /factoryClient\.start/);
  assert.match(code, /factoryClient\.events/);
  assert.match(code, /factoryClient\.artifact/);
});

test('SSE frames preserve actual backend event payloads across chunk boundaries', async () => {
  const encoder = new TextEncoder();
  const frames = [];
  const parts = [
    'event: snapshot\r',
    '\ndata: {"id":"r1","status":"running"}\r\n\r\n',
    'event: factory\nid: 7\ndata: {"sequence":7,"type":"command.output","payload":{"text":"compiling"}}\n\n',
  ];
  const body = new ReadableStream({
    start(controller) {
      for (const part of parts) controller.enqueue(encoder.encode(part));
      controller.close();
    },
  });
  await readEventStream(new Response(body, { headers: { 'Content-Type': 'text/event-stream' } }), (frame) =>
    frames.push(frame),
  );
  assert.equal(frames.length, 2);
  assert.deepEqual(frames[0], { event: 'snapshot', data: { id: 'r1', status: 'running' } });
  assert.equal(frames[1].data.sequence, 7);
  assert.equal(frames[1].data.payload.text, 'compiling');
});

test('execution updates consume SSE and have no polling or playback timer', async () => {
  const code = await readFile(new URL('../src/features/workflowDemo/WorkflowDemo.tsx', import.meta.url), 'utf8');
  assert.match(code, /factoryClient\.stream/);
  assert.doesNotMatch(code, /setTimeout|setInterval|eventsFor|applyEvent/);
});

const receipt = {
  id: 'artifact-real-input',
  kind: 'environment.report',
  producer: 'environment',
  path: '/factory/published/environment.json',
  sha256: 'a'.repeat(64),
  size: 128,
};
const deliveryEdge = { from: 'environment', to: 'inference', data: 'environment.report' };
const sourceNode = {
  id: 'environment',
  name: 'Inspect environment',
  stage_id: 'environment.inspect',
  workflow_id: 'environment',
  subworkflow_id: 'inspect',
  status: 'verified',
  attempts: [],
};
function consumer(status, attemptStatus = status, inputs = [receipt]) {
  return {
    id: 'inference',
    name: 'Model inference',
    stage_id: 'strata.inference',
    workflow_id: 'inference',
    subworkflow_id: 'run',
    status,
    attempts: [
      { number: 1, status: attemptStatus, started_at: '2026-11-14T00:00:00Z', commands: [], inputs, outputs: [] },
    ],
  };
}

test('verified source never makes a blocked or unexecuted consumer edge green', () => {
  for (const status of ['blocked', 'pending', 'running', 'verified']) {
    const target = { ...consumer(status), attempts: [] };
    assert.equal(edgeDeliveryStatus(deliveryEdge, [sourceNode, target], [receipt]), 'pending');
  }
  assert.equal(edgeDeliveryStatus(deliveryEdge, [sourceNode, consumer('blocked')], [receipt]), 'pending');
});

test('green requires matching published receipt and a verified downstream attempt and stage', () => {
  assert.equal(edgeDeliveryStatus(deliveryEdge, [sourceNode, consumer('verified')], [receipt]), 'verified');
  assert.equal(edgeDeliveryStatus(deliveryEdge, [sourceNode, consumer('verified', 'running')], [receipt]), 'pending');
  assert.equal(edgeDeliveryStatus(deliveryEdge, [sourceNode, consumer('pending', 'verified')], [receipt]), 'pending');
  assert.equal(
    edgeDeliveryStatus(deliveryEdge, [sourceNode, consumer('verified', 'verified', [])], [receipt]),
    'pending',
  );
});

test('missing publication evidence and every mismatched artifact identity field fail closed', () => {
  const nodes = [sourceNode, consumer('verified')];
  for (const missing of [undefined, [], null])
    assert.equal(edgeDeliveryStatus(deliveryEdge, nodes, missing), 'pending');
  for (const [field, value] of [
    ['id', 'different'],
    ['kind', 'source.checkout'],
    ['producer', 'other-node'],
    ['path', '/different.json'],
    ['sha256', 'b'.repeat(64)],
    ['size', 129],
  ]) {
    assert.equal(edgeDeliveryStatus(deliveryEdge, nodes, [{ ...receipt, [field]: value }]), 'pending', field);
  }
  assert.equal(
    edgeDeliveryStatus(
      deliveryEdge,
      [sourceNode, consumer('verified', 'verified', [{ ...receipt, sha256: '' }])],
      [{ ...receipt, sha256: '' }],
    ),
    'pending',
  );
});

test('running and failed edges require actual matching input binding in the current attempt', () => {
  assert.equal(edgeDeliveryStatus(deliveryEdge, [sourceNode, consumer('running')], [receipt]), 'running');
  assert.equal(
    edgeDeliveryStatus(deliveryEdge, [sourceNode, consumer('running', 'running', [])], [receipt]),
    'pending',
  );
  assert.equal(edgeDeliveryStatus(deliveryEdge, [sourceNode, consumer('failed')], [receipt]), 'failed');
  assert.equal(edgeDeliveryStatus(deliveryEdge, [sourceNode, consumer('failed', 'failed', [])], [receipt]), 'pending');
});

test('failed historical snapshot stays red while a later real verified attempt is green', () => {
  const historical = consumer('failed');
  const current = {
    ...consumer('verified'),
    attempts: [...historical.attempts, { ...consumer('verified').attempts[0], number: 2 }],
  };
  assert.equal(edgeDeliveryStatus(deliveryEdge, [sourceNode, historical], [receipt]), 'failed');
  assert.equal(edgeDeliveryStatus(deliveryEdge, [sourceNode, current], [receipt]), 'verified');
  const noReceiptRetry = {
    ...current,
    attempts: [...historical.attempts, { ...current.attempts[1], status: 'running', inputs: [] }],
    status: 'running',
  };
  assert.equal(edgeDeliveryStatus(deliveryEdge, [sourceNode, noReceiptRetry], [receipt]), 'pending');
});

const engineeringTask = {
  description: 'Construct the supported STRATA core source from the selected production modules.',
  source_scope: ['src/kernels/cuda/*.cu'],
  capabilities: ['routing', 'activation', 'aggregation'],
  acceptance: {
    source_project: true,
    cpu_validation: true,
    full_model_inference: false,
    native_execution: false,
    compare_original: false,
  },
};

test('formal engineering task preserves source scope, capabilities, and explicit acceptance flags', () => {
  assert.deepEqual(parseEngineeringTask(JSON.stringify(engineeringTask)), engineeringTask);
  const sparse = { ...engineeringTask, acceptance: { source_project: true, cpu_validation: true } };
  assert.deepEqual(parseEngineeringTask(JSON.stringify(sparse)), sparse);
  const contrastingText = {
    ...engineeringTask,
    description: 'Description mentions inference but acceptance stays explicit.',
  };
  assert.equal(parseEngineeringTask(JSON.stringify(contrastingText)).acceptance.full_model_inference, false);
  for (const invalid of [
    null,
    [],
    {},
    { ...engineeringTask, description: '' },
    { ...engineeringTask, source_scope: 'src/*.cu' },
    { ...engineeringTask, capabilities: [42] },
    { ...engineeringTask, acceptance: { ...engineeringTask.acceptance, native_execution: 'true' } },
    { ...engineeringTask, acceptance: {} },
    { ...engineeringTask, shell_command: 'echo unsupported' },
  ]) {
    assert.throws(() => parseEngineeringTask(JSON.stringify(invalid)));
  }
  assert.throws(() => parseEngineeringTask('invalid JSON'));
});

test('task-only submission carries the engineering task without client-implied goals', async () => {
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (path, options) => {
    calls.push({ path, options });
    return new Response(JSON.stringify({ id: 'task-run', status: 'planning', nodes: [] }), { status: 202 });
  };
  try {
    await factoryClient.start({
      repository_url: 'https://github.com/niko1221/strata',
      target_backend: 'ascend',
      goals: [],
      task: parseEngineeringTask(JSON.stringify(engineeringTask)),
    });
    const body = JSON.parse(calls[0].options.body);
    assert.deepEqual(body.goals, []);
    assert.deepEqual(body.task, engineeringTask);
    await factoryClient.start({
      repository_url: 'https://github.com/niko1221/strata',
      target_backend: 'ascend',
      goals: ['inference.result'],
      task: engineeringTask,
    });
    const explicit = JSON.parse(calls[1].options.body);
    assert.deepEqual(explicit.goals, ['inference.result']);
    assert.equal(explicit.task.acceptance.full_model_inference, false);
  } finally {
    globalThis.fetch = original;
  }
});

test('editing hydrated acceptance cannot resend invisible compiled goals', async () => {
  const storedGoals = ['value.report', 'construction.package', 'construction.portability'];
  const selected = userGoalSelection(storedGoals);
  assert.deepEqual(selected, ['value.report', 'construction.package']);
  const editedTask = { ...engineeringTask, acceptance: { source_project: false, cpu_validation: false } };
  const original = globalThis.fetch;
  let sent;
  globalThis.fetch = async (_path, options) => {
    sent = JSON.parse(options.body);
    return new Response(JSON.stringify({ id: 'task-edited', status: 'planning', nodes: [] }), { status: 202 });
  };
  try {
    await factoryClient.start({
      repository_url: 'https://github.com/niko1221/strata',
      target_backend: 'cpu',
      goals: selected.filter(() => false),
      task: editedTask,
    });
    assert.deepEqual(sent.goals, []);
    assert.deepEqual(sent.task.acceptance, { source_project: false, cpu_validation: false });
    assert.deepEqual(storedGoals, ['value.report', 'construction.package', 'construction.portability']);
  } finally {
    globalThis.fetch = original;
  }
});

test('independent oracle cases preserve numeric input text and literal expected arrays', async () => {
  const oracle = {
    cases: [
      {
        input: '2 3\n1 2 3\n4 5 6\n',
        operation: 'normalize',
        expected: {
          values: [
            [1, 2.5, -3],
            [0, 4, 6],
          ],
        },
        atol: 0,
        rtol: 1e-6,
      },
      { input: '1 2 3\n', expected: { values: [1, 2, 3], indices: [2, 1, 0] } },
    ],
  };
  const task = { ...engineeringTask, oracle };
  const parsed = parseEngineeringTask(JSON.stringify(task));
  assert.deepEqual(parsed.oracle, oracle);
  const original = globalThis.fetch;
  let sent;
  globalThis.fetch = async (_path, options) => {
    sent = JSON.parse(options.body);
    return new Response(JSON.stringify({ id: 'oracle-task', status: 'planning', nodes: [] }), { status: 202 });
  };
  try {
    await factoryClient.start({
      repository_url: 'https://github.com/niko1221/strata',
      target_backend: 'cpu',
      goals: [],
      task: parsed,
    });
    assert.deepEqual(sent.task.oracle, oracle);
  } finally {
    globalThis.fetch = original;
  }
});

test('oracle structure rejects executable extensions and bounds case count', () => {
  const entry = { input: '1 2\n', expected: { values: [1, 2] } };
  assert.equal(
    parseEngineeringTask(JSON.stringify({ ...engineeringTask, oracle: { cases: Array(16).fill(entry) } })).oracle.cases
      .length,
    16,
  );
  for (const oracle of [
    null,
    [],
    {},
    { cases: [] },
    { cases: Array(17).fill(entry) },
    { cases: [entry], script: 'unsupported' },
    { cases: [{ ...entry, executable: 'unsupported' }] },
    { cases: [{ ...entry, command: ['unsupported'] }] },
    { cases: [null] },
    { cases: [{ ...entry, input: '' }] },
    { cases: [{ ...entry, operation: 42 }] },
    { cases: [{ ...entry, expected: [] }] },
    { cases: [{ ...entry, expected: null }] },
  ]) {
    assert.throws(() => parseEngineeringTask(JSON.stringify({ ...engineeringTask, oracle })));
  }
  assert.throws(() =>
    parseEngineeringTask(JSON.stringify({ ...engineeringTask, oracle: { cases: [entry] }, script: 'unsupported' })),
  );
});

test('oracle tolerances must be finite nonnegative numbers', () => {
  for (const field of ['atol', 'rtol']) {
    for (const tolerance of [-0.001, null, '0.1']) {
      const task = {
        ...engineeringTask,
        oracle: { cases: [{ input: '1\n', expected: { values: [1] }, [field]: tolerance }] },
      };
      assert.throws(() => parseEngineeringTask(JSON.stringify(task)), /finite and nonnegative/);
    }
    const text = JSON.stringify({
      ...engineeringTask,
      oracle: { cases: [{ input: '1\n', expected: { values: [1] }, [field]: 0 }] },
    });
    assert.throws(
      () => parseEngineeringTask(text.replace(`"${field}":0`, `"${field}":1e999`)),
      /finite and nonnegative/,
    );
    assert.throws(
      () => parseEngineeringTask(text.replace(`"${field}":0`, `"${field}":-1e999`)),
      /finite and nonnegative/,
    );
  }
});
