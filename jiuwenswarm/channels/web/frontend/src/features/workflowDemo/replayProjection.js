/** Read-only projection of recorded factory facts. No I/O, clock or execution. */
const copy = (value) => (value === undefined ? undefined : JSON.parse(JSON.stringify(value)));
const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

function stamp(value) {
  const milliseconds = typeof value === 'string' ? Date.parse(value) : NaN;
  if (!Number.isFinite(milliseconds)) return NaN;
  // Preserve the recorder's microseconds when gating lifecycle-bound receipts.
  const fraction = /\.(\d+)/.exec(value)?.[1] ?? '';
  return milliseconds * 1000 + Number(fraction.padEnd(6, '0').slice(3, 6));
}

export function normalizeReplayEvents(events) {
  if (!Array.isArray(events)) throw new Error('Replay events must be an array');
  events.forEach((event, index) => {
    if (
      !object(event) ||
      event.sequence !== index + 1 ||
      typeof event.type !== 'string' ||
      !event.type ||
      !Number.isFinite(stamp(event.time)) ||
      !object(event.payload)
    )
      throw new Error(`Invalid or incomplete recorded event at position ${index + 1}`);
  });
  return events.slice();
}

function offsets(events) {
  if (!events.length) return [];
  const start = stamp(events[0].time);
  let previous = 0;
  return events.map((event) => {
    // Sequence remains authoritative if the recording clock moved backwards.
    previous = Math.max(previous, (stamp(event.time) - start) / 1000);
    return previous;
  });
}

function replayInputMatchesPublication(input, publication, edge) {
  if (!object(input) || !object(publication)) return false;
  return (
    typeof input.id === 'string' &&
    input.id.length > 0 &&
    typeof input.path === 'string' &&
    input.path.length > 0 &&
    typeof input.sha256 === 'string' &&
    /^[a-f0-9]{64}$/i.test(input.sha256) &&
    typeof input.kind === 'string' &&
    input.kind.length > 0 &&
    typeof input.producer === 'string' &&
    input.producer.length > 0 &&
    Number.isInteger(input.size) &&
    input.size >= 0 &&
    input.kind === edge.data &&
    input.producer === edge.from &&
    input.id === publication.id &&
    input.kind === publication.kind &&
    input.producer === publication.producer &&
    input.path === publication.path &&
    input.sha256 === publication.sha256 &&
    input.size === publication.size
  );
}

/** Dependency state is supported by a downstream receipt, never source color. */
export function replayEdgeStatus(edge, run) {
  const nodes = run?.nodes;
  const publications = run?.artifacts;
  if (!Array.isArray(nodes) || !Array.isArray(publications) || !nodes.some((node) => node.id === edge.from))
    return 'pending';
  const target = nodes.find((node) => node.id === edge.to);
  if (!target || !Array.isArray(target.attempts) || !target.attempts.length) return 'pending';
  const attempt = target.attempts[target.attempts.length - 1];
  if (
    !attempt ||
    !Array.isArray(attempt.inputs) ||
    !attempt.inputs.some((input) =>
      publications.some((publication) => replayInputMatchesPublication(input, publication, edge)),
    )
  )
    return 'pending';
  if (target.status === 'verified' && attempt.status === 'verified') return 'verified';
  if (target.status === 'running' && attempt.status === 'running') return 'running';
  if (target.status === 'failed' && attempt.status === 'failed') return 'failed';
  return 'pending';
}

export function eventOffset(events, index) {
  const normalized = normalizeReplayEvents(events);
  if (!normalized.length) return 0;
  if (!Number.isInteger(index) || index < 0 || index >= normalized.length)
    throw new Error('Replay event index is outside the recording');
  return offsets(normalized)[index];
}

export function replayDuration(events) {
  const normalized = normalizeReplayEvents(events);
  const values = offsets(normalized);
  return values.length ? values[values.length - 1] : 0;
}

/**
 * cursor is an event COUNT: zero is before the recording, N includes event N.
 * Matching sealed attempt receipts are available only after their recorded
 * lifecycle end. They supplement missing input/verification fields in older
 * JSONL event schemas, never reveal a later attempt or future output.
 */
export function projectReplay(run, events, cursor = events.length) {
  const recorded = normalizeReplayEvents(events);
  if (!object(run) || typeof run.id !== 'string') throw new Error('Replay requires its recorded run');
  if (!Number.isInteger(cursor) || cursor < 0 || cursor > recorded.length)
    throw new Error('Replay cursor is outside the recording');
  const clock = offsets(recorded);
  const state = {
    id: run.id,
    request: copy(run.request),
    created_at: run.created_at,
    updated_at: run.created_at,
    status: 'created',
    nodes: [],
    edges: [],
    artifacts: [],
    graph_revisions: [],
    goal_results: {},
    error: null,
    sequence: 0,
  };
  for (const key of ['executor', 'recipe', 'recipe_digest']) if (run[key] !== undefined) state[key] = copy(run[key]);
  const artifacts = new Map();
  const streams = new Map();
  const sealedNodes = new Map((Array.isArray(run.nodes) ? run.nodes : []).map((node) => [node.id, node]));

  function publish(artifact) {
    if (!object(artifact) || typeof artifact.id !== 'string')
      throw new Error('Recorded publication has no artifact identity');
    const previous = artifacts.get(artifact.id);
    if (previous && JSON.stringify(previous) !== JSON.stringify(artifact))
      throw new Error(`Recorded artifact identity changed: ${artifact.id}`);
    artifacts.set(artifact.id, copy(artifact));
  }

  function nodeFor(id, declaration) {
    if (typeof id !== 'string' || !id) throw new Error('Recorded stage event has no node identity');
    let node = state.nodes.find((value) => value.id === id);
    if (!node) {
      node = {
        id,
        stage_id: declaration?.id ?? '',
        name: declaration?.name ?? id,
        workflow_id: declaration?.workflow_id ?? '',
        subworkflow_id: declaration?.subworkflow_id ?? '',
        status: 'pending',
        attempts: [],
      };
      state.nodes.push(node);
    }
    return node;
  }

  function attemptFor(node, number, time) {
    if (!Number.isInteger(number) || number < 1) throw new Error('Recorded attempt has no valid number');
    let attempt = node.attempts.find((value) => value.number === number);
    if (!attempt) {
      attempt = {
        number,
        status: 'running',
        started_at: time,
        finished_at: null,
        commands: [],
        inputs: [],
        outputs: [],
        error: null,
        verification: null,
      };
      node.attempts.push(attempt);
    }
    return attempt;
  }

  function currentAttempt(node) {
    const attempt = node.attempts[node.attempts.length - 1];
    if (!attempt) throw new Error(`Recorded command has no started attempt: ${node.id}`);
    return attempt;
  }

  function streamKey(node, attempt, index) {
    return `${node.id}/${attempt.number}/${index}`;
  }

  function applyStreams(node, attempt) {
    attempt.commands.forEach((command, index) => {
      const buffered = streams.get(streamKey(node, attempt, index + 1));
      if (buffered)
        for (const stream of ['stdout', 'stderr']) if (buffered.seen[stream]) command[stream] = buffered[stream];
    });
  }

  function recordedEnd(node, attempt, status, event) {
    const finalAttempt = sealedNodes.get(node.id)?.attempts?.find((value) => value.number === attempt.number);
    if (
      finalAttempt?.status === status &&
      Number.isFinite(stamp(finalAttempt.finished_at)) &&
      stamp(finalAttempt.finished_at) <= stamp(event.time)
    ) {
      // Only this ended attempt's observations, not final node state or bindings.
      for (const key of ['started_at', 'finished_at', 'inputs', 'verification'])
        if (finalAttempt[key] !== undefined) attempt[key] = copy(finalAttempt[key]);
    }
  }

  for (const event of recorded.slice(0, cursor)) {
    const payload = event.payload;
    state.sequence = event.sequence;
    state.updated_at = event.time;

    if (event.type === 'graph.updated') {
      if (!Array.isArray(payload.nodes) || !Array.isArray(payload.edges))
        throw new Error('Recorded graph revision is incomplete');
      state.nodes = copy(payload.nodes).map((value) => {
        if (typeof value === 'string')
          return {
            id: value,
            stage_id: '',
            name: value,
            workflow_id: '',
            subworkflow_id: '',
            status: 'pending',
            attempts: [],
          };
        return value;
      });
      state.edges = copy(payload.edges);
      state.graph_revisions.push(copy(payload));
      for (const node of state.nodes) {
        if (!Array.isArray(node.attempts)) node.attempts = [];
        for (const attempt of node.attempts) {
          if (!Array.isArray(attempt.commands)) attempt.commands = [];
          applyStreams(node, attempt);
          if (attempt.status === 'verified') for (const artifact of attempt.outputs ?? []) publish(artifact);
        }
      }
      continue;
    }

    if (event.type === 'run.planning') state.status = 'planning';
    else if (event.type === 'run.started') state.status = 'running';
    else if (['run.completed', 'run.failed', 'run.blocked', 'run.cancelled'].includes(event.type)) {
      state.status = event.type.slice(4);
      state.error = copy(payload.error ?? null);
      if (object(payload.error?.details?.goals)) state.goal_results = copy(payload.error.details.goals);
    } else if (event.type === 'service.recovery_required') {
      state.status = 'blocked';
      state.error = copy(payload.error);
      for (const node of state.nodes) {
        if (node.status !== 'running') continue;
        node.status = 'blocked';
        const attempt = node.attempts[node.attempts.length - 1];
        if (attempt?.status === 'running') {
          attempt.status = 'blocked';
          attempt.error = copy(payload.error);
        }
      }
    } else if (['goal.verified', 'goal.failed', 'goal.blocked'].includes(event.type)) {
      if (typeof payload.goal !== 'string') throw new Error('Recorded goal event has no goal');
      state.goal_results = {
        ...state.goal_results,
        [payload.goal]: {
          status: event.type.slice(5),
          ...(event.node_id ? { node_id: event.node_id } : {}),
          ...(payload.error ? { error: copy(payload.error) } : {}),
        },
      };
    } else if (event.type === 'stage.started') {
      const node = nodeFor(event.node_id, payload.stage);
      const attempt = attemptFor(node, payload.attempt, event.time);
      node.status = 'running';
      attempt.status = 'running';
      delete node.blocked_by;
      delete node.dependency_error;
    } else if (['stage.verified', 'stage.failed', 'stage.blocked'].includes(event.type)) {
      const node = nodeFor(event.node_id);
      const status = event.type.slice(6);
      node.status = status;
      if (payload.executed === false || (!payload.attempt && status === 'blocked')) {
        if (payload.blocked_by !== undefined) node.blocked_by = copy(payload.blocked_by);
        if (payload.error !== undefined) node.dependency_error = copy(payload.error);
      } else {
        const attempt = attemptFor(node, payload.attempt, event.time);
        attempt.status = status;
        attempt.finished_at = event.time;
        attempt.error = copy(payload.error ?? null);
        attempt.verification = { outcome: status === 'verified' ? 'pass' : status === 'failed' ? 'fail' : 'blocked' };
        recordedEnd(node, attempt, status, event);
        if (status === 'verified') {
          attempt.outputs = copy(payload.outputs ?? []);
          for (const artifact of attempt.outputs) publish(artifact);
        }
      }
    } else if (event.type === 'command.started') {
      const node = nodeFor(event.node_id);
      const attempt = currentAttempt(node);
      if (!object(payload.command)) throw new Error('Recorded command start is incomplete');
      attempt.commands.push(copy(payload.command));
      applyStreams(node, attempt);
    } else if (event.type === 'command.output') {
      const node = nodeFor(event.node_id);
      const attempt = currentAttempt(node);
      const index = payload.command_index;
      if (!Number.isInteger(index) || index < 1 || !attempt.commands[index - 1])
        throw new Error('Recorded output has no preceding command');
      if (!['stdout', 'stderr'].includes(payload.stream) || typeof payload.text !== 'string')
        throw new Error('Recorded output stream is invalid');
      const key = streamKey(node, attempt, index);
      let buffer = streams.get(key);
      if (!buffer) {
        buffer = { stdout: '', stderr: '', seen: { stdout: false, stderr: false } };
        streams.set(key, buffer);
      }
      buffer[payload.stream] += payload.text;
      buffer.seen[payload.stream] = true;
      applyStreams(node, attempt);
    } else if (event.type === 'command.finished') {
      const node = nodeFor(event.node_id);
      const attempt = currentAttempt(node);
      const command = payload.command;
      if (!object(command)) throw new Error('Recorded command finish is incomplete');
      const index = attempt.commands.findIndex((value) => value.started_at === command.started_at);
      if (index < 0) throw new Error('Recorded command finish has no preceding start');
      attempt.commands[index] = copy(command);
      applyStreams(node, attempt);
      for (const artifact of run.artifacts ?? []) {
        if (artifact.producer !== node.id) continue;
        if (
          (artifact.kind === 'process.stdout' && artifact.path === command.stdout_path) ||
          (artifact.kind === 'process.stderr' && artifact.path === command.stderr_path)
        )
          publish(artifact);
      }
    } else if (event.type === 'artifact.consumed') {
      const node = nodeFor(event.node_id);
      const attempt = attemptFor(node, payload.attempt, event.time);
      if (!object(payload.artifact) || typeof payload.artifact.id !== 'string')
        throw new Error('Recorded consumption has no artifact identity');
      if (!attempt.inputs.some((value) => value.id === payload.artifact.id))
        attempt.inputs.push(copy(payload.artifact));
      const edge = { from: payload.artifact.producer, to: node.id, data: payload.artifact.kind };
      if (!state.edges.some((value) => value.from === edge.from && value.to === edge.to && value.data === edge.data))
        state.edges.push(edge);
    }
  }
  state.artifacts = [...artifacts.values()];
  state.replay = {
    cursor,
    event_count: recorded.length,
    time: cursor ? recorded[cursor - 1].time : null,
    elapsed_ms: cursor ? clock[cursor - 1] : 0,
    duration_ms: clock.length ? clock[clock.length - 1] : 0,
    recorded_status: run.status,
  };
  return state;
}
