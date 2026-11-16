/** Read-only regression checks against immutable, already executed recordings. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import {
  eventOffset,
  normalizeReplayEvents,
  projectReplay,
  replayEdgeStatus,
  replayDuration,
} from '../src/features/workflowDemo/replayProjection.js';

const root = process.env.FACTORY_REPLAY_RUN_ROOT ?? '/workspace/factory-runs';
const ids = {
  core: '6db7a2b968c8434eaa9a508a6d16a7cf',
  normalization: '02446be989844a3fb7e43dc9bd6a8e0a',
  mixed: 'b152d434c8e14b01adc8c4aa40ad83f2',
  native: 'baf3d77a8301423180ccda45fb11c66b',
  parent: '9e4d7d2016844066b504d87bc712b06c',
  missing: '68c1f757248741c6b14d0bcf7a3fc978',
  wrong: '0121a742659c402eb9efc66265502573',
  internal: 'cab4cb9235184b8d9b45c1ef40825589',
};

function recording(name = 'core') {
  const directory = path.join(root, ids[name]);
  return {
    run: JSON.parse(fs.readFileSync(path.join(directory, 'run.json'), 'utf8')),
    events: fs
      .readFileSync(path.join(directory, 'events.jsonl'), 'utf8')
      .trim()
      .split('\n')
      .map((line) => JSON.parse(line)),
  };
}

const core = recording();
const node = (state, id) => state.nodes.find((item) => item.id === id);
const finished = (value) => ['verified', 'failed', 'blocked'].includes(value.status);

test('zero cursor exposes no final execution graph, artifact, error or outcome', () => {
  const state = projectReplay(core.run, core.events, 0);
  assert.equal(state.status, 'created');
  assert.equal(state.sequence, 0);
  assert.deepEqual(state.nodes, []);
  assert.deepEqual(state.edges, []);
  assert.deepEqual(state.artifacts, []);
  assert.deepEqual(state.graph_revisions, []);
  assert.deepEqual(state.goal_results, {});
  assert.equal(state.error, null);
  assert.equal(state.replay.time, null);
  assert.equal(state.replay.recorded_status, core.run.status);
  assert.equal(state.recipe_digest, core.run.recipe_digest);
});

test('planning graph and dynamically selected lowerers appear only at recorded revisions', () => {
  const first = core.events.findIndex((event) => event.type === 'graph.updated');
  assert.equal(projectReplay(core.run, core.events, first).nodes.length, 0);
  const initial = projectReplay(core.run, core.events, first + 1);
  assert.equal(initial.nodes.length, core.events[first].payload.nodes.length);
  assert.ok(initial.nodes.every((value) => value.status === 'pending' && value.attempts.length === 0));
  const inserted = core.events.findIndex(
    (event) => event.type === 'graph.updated' && event.payload.nodes.some((value) => value.stage_id === 'lower.scalar'),
  );
  assert.ok(inserted > first);
  assert.equal(
    projectReplay(core.run, core.events, inserted).nodes.some((value) => value.stage_id === 'lower.scalar'),
    false,
  );
  assert.equal(
    projectReplay(core.run, core.events, inserted + 1).nodes.some((value) => value.stage_id === 'lower.scalar'),
    true,
  );
});

test('generated source and Code Diff stay hidden until actual publication', () => {
  const index = core.events.findIndex(
    (event) =>
      event.type === 'stage.verified' && event.payload.outputs.some((artifact) => artifact.kind === 'construction.cpp'),
  );
  assert.ok(index > 0);
  for (const kind of ['construction.cpp', 'construction.header', 'construction.code_diff']) {
    assert.equal(
      projectReplay(core.run, core.events, index).artifacts.some((value) => value.kind === kind),
      false,
    );
    assert.equal(
      projectReplay(core.run, core.events, index + 1).artifacts.some((value) => value.kind === kind),
      true,
    );
  }
});

test('actual failed build, running retry and verified retry remain distinct', () => {
  const failedIndex = core.events.findIndex((event) => event.type === 'stage.failed');
  const failed = core.events[failedIndex];
  const state = projectReplay(core.run, core.events, failedIndex + 1);
  assert.equal(node(state, failed.node_id).status, 'failed');
  assert.equal(node(state, failed.node_id).attempts[0].error.code, 'missing_toolchain');
  const retryIndex = core.events.findIndex(
    (event) => event.type === 'stage.started' && event.node_id === failed.node_id && event.payload.attempt === 2,
  );
  const retry = node(projectReplay(core.run, core.events, retryIndex + 1), failed.node_id);
  assert.equal(retry.status, 'running');
  assert.deepEqual(
    retry.attempts.map((value) => value.status),
    ['failed', 'running'],
  );
  assert.deepEqual(retry.attempts[1].outputs, []);
  const verifiedIndex = core.events.findIndex(
    (event) => event.type === 'stage.verified' && event.node_id === failed.node_id && event.payload.attempt === 2,
  );
  const verified = node(projectReplay(core.run, core.events, verifiedIndex + 1), failed.node_id);
  assert.deepEqual(
    verified.attempts.map((value) => value.status),
    ['failed', 'verified'],
  );
});

test('dynamic child input receipts follow the actual consumption event', () => {
  const index = core.events.findIndex((event) => event.type === 'artifact.consumed');
  const event = core.events[index];
  const before = node(projectReplay(core.run, core.events, index), event.node_id);
  assert.equal(
    before.attempts.at(-1).inputs.some((value) => value.id === event.payload.artifact.id),
    false,
  );
  const after = node(projectReplay(core.run, core.events, index + 1), event.node_id);
  assert.ok(after.attempts.at(-1).inputs.some((value) => value.id === event.payload.artifact.id));
});

test('static sealed receipts are lifecycle gated, with no future attempt enrichment', () => {
  const startedIndex = core.events.findIndex(
    (event) => event.type === 'stage.started' && event.payload.stage.id === 'source.cuda_ast',
  );
  const id = core.events[startedIndex].node_id;
  assert.deepEqual(node(projectReplay(core.run, core.events, startedIndex + 1), id).attempts[0].inputs, []);
  const endIndex = core.events.findIndex((event) => event.type === 'stage.verified' && event.node_id === id);
  assert.equal(node(projectReplay(core.run, core.events, endIndex + 1), id).attempts[0].inputs.length, 1);
  const future = structuredClone(core.run);
  node(future, id).attempts[0].finished_at = '2099-01-01T00:00:00+00:00';
  node(future, id).attempts[0].inputs = [{ id: 'future-input' }];
  assert.deepEqual(node(projectReplay(future, core.events, endIndex + 1), id).attempts[0].inputs, []);
});

test('stdout and stderr chunks are not duplicated by command.finished or snapshots', () => {
  const output = core.events.find((event) => event.type === 'command.output' && event.payload.stream === 'stderr');
  const endIndex = core.events.findIndex(
    (event) =>
      event.type === 'command.finished' &&
      event.node_id === output.node_id &&
      event.payload.command.stderr_path.endsWith('command-1.stderr'),
  );
  const atFinish = node(projectReplay(core.run, core.events, endIndex + 1), output.node_id).attempts[0].commands[0];
  assert.equal(atFinish.stderr, output.payload.text);
  const final = node(projectReplay(core.run, core.events), output.node_id).attempts[0].commands[0];
  assert.equal(final.stderr, output.payload.text);
  assert.equal(final.exit_code, 0);
});

test('all eight completed recordings retain actual statuses, attempts and publication identities', () => {
  for (const name of Object.keys(ids)) {
    const { run, events } = recording(name);
    const state = projectReplay(run, events);
    assert.equal(state.status, run.status, name);
    assert.equal(state.sequence, run.sequence, name);
    assert.deepEqual(
      state.nodes.map((value) => [value.id, value.status]),
      run.nodes.map((value) => [value.id, value.status]),
      name,
    );
    assert.deepEqual(
      new Set(state.artifacts.map((value) => value.id)),
      new Set(run.artifacts.map((value) => value.id)),
      name,
    );
    for (const original of run.nodes) {
      assert.deepEqual(
        node(state, original.id).attempts.map((value) => [value.number, value.status]),
        original.attempts.map((value) => [value.number, value.status]),
        `${name}/${original.id}`,
      );
      if (original.status === 'blocked' && original.attempts.length === 0)
        assert.deepEqual(node(state, original.id).attempts, []);
    }
    assert.equal(
      state.nodes.filter((value) => value.attempts.some(finished)).length,
      run.nodes.filter((value) => value.attempts.some(finished)).length,
    );
    assert.equal(projectReplay(run, events, events.length - 1).status, 'running', `${name} no premature run end`);
  }
});

test('every visible artifact is backed by a publication observed within the prefix', () => {
  const publication = new Map();
  core.events.forEach((event, index) => {
    const observe = (artifact) => {
      if (!publication.has(artifact.id)) publication.set(artifact.id, index + 1);
    };
    if (event.type === 'stage.verified') event.payload.outputs.forEach(observe);
    if (event.type === 'graph.updated')
      event.payload.nodes.forEach((value) =>
        value.attempts.forEach((attempt) => {
          if (attempt.status === 'verified') attempt.outputs.forEach(observe);
        }),
      );
    if (event.type === 'command.finished')
      core.run.artifacts
        .filter(
          (value) =>
            value.producer === event.node_id &&
            [event.payload.command.stdout_path, event.payload.command.stderr_path].includes(value.path),
        )
        .forEach(observe);
  });
  for (let cursor = 0; cursor <= core.events.length; cursor += 1)
    for (const artifact of projectReplay(core.run, core.events, cursor).artifacts)
      assert.ok(publication.get(artifact.id) <= cursor, `${artifact.id} leaked at ${cursor}`);
});

test('seeking backwards removes later code, artifacts and terminal outcomes deterministically', () => {
  const index = core.events.findIndex(
    (event) => event.type === 'stage.started' && event.payload.stage.id === 'construction.codegen',
  );
  const early = projectReplay(core.run, core.events, index + 1);
  projectReplay(core.run, core.events);
  assert.deepEqual(projectReplay(core.run, core.events, index + 1), early);
  assert.ok(!early.artifacts.some((value) => value.kind === 'construction.cpp'));
  assert.equal(early.status, 'running');
  assert.equal(early.error, null);
});

test('recorded objects remain unchanged and a final-only fake artifact never enters playback', () => {
  const before = JSON.stringify(core);
  projectReplay(core.run, core.events, 10);
  projectReplay(core.run, core.events);
  assert.equal(JSON.stringify(core), before);
  const altered = structuredClone(core.run);
  altered.artifacts.push({ id: 'unpublished', kind: 'construction.cpp', producer: 'n7', path: 'unpublished.cpp' });
  assert.equal(
    projectReplay(altered, core.events).artifacts.some((value) => value.id === 'unpublished'),
    false,
  );
});

test('timing uses original order/timestamps and malformed or incomplete logs fail closed', () => {
  assert.ok(replayDuration(core.events) > 0);
  assert.equal(eventOffset(core.events, 0), 0);
  assert.equal(eventOffset(core.events, core.events.length - 1), replayDuration(core.events));
  assert.deepEqual(normalizeReplayEvents(core.events), core.events);
  assert.throws(() => normalizeReplayEvents(core.events.slice(1)), /incomplete/);
  assert.throws(() => normalizeReplayEvents([core.events[0], core.events[0]]), /incomplete/);
  assert.throws(() => projectReplay(core.run, core.events, -1), /cursor/);
  assert.throws(() => projectReplay(core.run, core.events, core.events.length + 1), /cursor/);
  assert.throws(() => eventOffset(core.events, -1), /index/);
});

function verifiedEdgeFixture() {
  const state = projectReplay(core.run, core.events);
  const edge = state.edges.find((value) => replayEdgeStatus(value, state) === 'verified');
  assert.ok(edge, 'Actual recording must contain a verified downstream artifact receipt');
  return { state, edge, target: node(state, edge.to) };
}

test('edge state never derives blue, red or green from the source node alone', () => {
  const { run, events } = recording('native');
  const state = projectReplay(run, events);
  const blockedEdges = state.edges.filter((edge) => node(state, edge.to).status === 'blocked');
  assert.ok(blockedEdges.length > 0);
  for (const edge of blockedEdges) assert.equal(replayEdgeStatus(edge, state), 'pending');
  const fixture = verifiedEdgeFixture();
  fixture.target.attempts.at(-1).inputs = [];
  fixture.target.status = 'running';
  fixture.target.attempts.at(-1).status = 'running';
  node(fixture.state, fixture.edge.from).status = 'running';
  assert.equal(replayEdgeStatus(fixture.edge, fixture.state), 'pending');
});

test('verified edge requires the exact immutable publication and actual target receipt', () => {
  const { state, edge } = verifiedEdgeFixture();
  assert.equal(replayEdgeStatus(edge, state), 'verified');
  assert.equal(replayEdgeStatus(edge, { nodes: state.nodes }), 'pending');
  assert.equal(replayEdgeStatus(edge, { artifacts: state.artifacts }), 'pending');
  assert.equal(
    replayEdgeStatus(edge, { ...state, nodes: state.nodes.filter((value) => value.id !== edge.from) }),
    'pending',
  );
});

test('each artifact identity field mismatch fails closed instead of coloring the edge', () => {
  const { state, edge } = verifiedEdgeFixture();
  const input = node(state, edge.to)
    .attempts.at(-1)
    .inputs.find((value) => value.producer === edge.from && value.kind === edge.data);
  assert.ok(input);
  for (const [field, value] of Object.entries({
    id: 'other-id',
    kind: 'other-kind',
    path: '/other-path',
    producer: 'other-producer',
    sha256: '0'.repeat(64),
    size: input.size + 1,
  })) {
    const changed = structuredClone(state);
    node(changed, edge.to).attempts.at(-1).inputs = [{ ...input, [field]: value }];
    assert.equal(replayEdgeStatus(edge, changed), 'pending', field);
  }
});

test('latest matching attempt determines running and failed colors; blocked stays pending', () => {
  const { state, edge, target } = verifiedEdgeFixture();
  const receipt = structuredClone(target.attempts.at(-1).inputs);
  const number = target.attempts.at(-1).number + 1;
  target.attempts.push({ number, status: 'running', inputs: [] });
  target.status = 'running';
  assert.equal(replayEdgeStatus(edge, state), 'pending', 'Earlier verified receipt cannot color a new attempt');
  target.attempts.at(-1).inputs = receipt;
  assert.equal(replayEdgeStatus(edge, state), 'running');
  target.status = 'failed';
  target.attempts.at(-1).status = 'failed';
  assert.equal(replayEdgeStatus(edge, state), 'failed');
  target.status = 'blocked';
  target.attempts.at(-1).status = 'blocked';
  assert.equal(replayEdgeStatus(edge, state), 'pending');
  target.status = 'verified';
  assert.equal(replayEdgeStatus(edge, state), 'pending', 'Attempt and node status must agree');
});
