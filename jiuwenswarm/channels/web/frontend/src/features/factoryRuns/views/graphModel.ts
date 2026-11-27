import type { EvidenceFile, NodeCapsuleActivity, RunState, StoryEvent } from '../api';
import type { CuratedReplay, ReplayNodePresentation } from './storyModel.ts';
import { atlasTitle } from '../cc/atlasNames.ts';
import type { NodeCheckIndex, NodeOperator } from './checkModel.ts';
import { indexTaskGraphChecks, legacyTimelineActivity } from './taskGraphVerifierModel.ts';
import { capsuleFactsAt, nodeVerifierAt, reopenBoundary, type NodeExecutionFacts } from './ccActivityModel.ts';

export type { TimelineVerifierResult } from './ccActivityModel.ts';

type Fields = Record<string, unknown>;
type NodeKind = 'contract' | 'task' | 'step' | 'capsule' | 'entity' | 'group';
type LinkKind = 'dependency' | 'superseded' | 'contract' | 'step' | 'capsule' | 'relation' | 'member';

export type GraphNode = {
  id: string;
  label: string;
  kind: NodeKind;
  details: Fields;
  state?: string;
  planId?: string;
  boundCCs?: string[];
};
export type GraphLink = {
  source: string;
  target: string;
  kind: LinkKind;
  label?: string;
};
export type GraphModel = {
  kind: 'taskgraph' | 'ontology' | 'contract';
  nodes: GraphNode[];
  links: GraphLink[];
  history: Fields[];
  taskId?: string;
  taskChecks?: ReturnType<typeof indexTaskGraphChecks>;
  defaultChecks?: Fields;
};
type GraphContext = {
  contract?: unknown;
  tasks?: readonly unknown[];
  observations?: readonly unknown[];
  nodePresentation?: Record<string, ReplayNodePresentation>;
};
export type GraphReplay = {
  events: readonly StoryEvent[];
  position: number;
  files?: readonly EvidenceFile[];
  curated?: CuratedReplay | null;
  runState?: RunState;
  liveDemo?: boolean;
  onOpenFile?: (path: string) => void;
  onOpenNode?: (nodeId: string) => void;
  replayByNode?: Map<string, unknown[]>;
  /** Live and exported runs: per plan node checking records (GET /runs/{id} node_checks). */
  checks?: NodeCheckIndex;
  ccActivity?: Readonly<Record<string, NodeCapsuleActivity>>;
  /** Live homes only: hold, release and reopen. */
  operator?: NodeOperator;
};
type NodeProgress = { phase: 'upcoming' | 'seen' | 'current'; details?: Fields };
export type TaskGraphTimelineNode = GraphNode & NodeExecutionFacts & {
  replayState: 'done' | 'current' | 'not-reached' | 'stopped';
  boundCCs: string[];
};

function record(value: unknown): Fields | undefined {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Fields) : undefined;
}

function string(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function rows(value: unknown): Fields[] {
  return list(value)
    .map(record)
    .filter((row) => row !== undefined);
}

function idOf(kind: NodeKind, value: string) {
  return `${kind}:${value}`;
}

function builder(kind: GraphModel['kind']) {
  const nodes = new Map<string, GraphNode>();
  const links = new Map<string, GraphLink>();
  return {
    node(type: NodeKind, key: string, details: Fields, title = key, planId?: string, boundCCs?: string[]) {
      const id = idOf(type, key);
      if (!nodes.has(id))
        nodes.set(id, { id, label: title, kind: type, details, state: string(details.state), planId, boundCCs });
      return id;
    },
    link(source: string, target: string, kind: LinkKind, label?: string) {
      if (nodes.has(source) && nodes.has(target)) {
        links.set(JSON.stringify([source, target, kind, label]), { source, target, kind, label });
      }
    },
    model(history: Fields[] = [], taskId?: string): GraphModel {
      return { kind, nodes: [...nodes.values()], links: [...links.values()], history, taskId };
    },
  };
}

type GraphBuilder = ReturnType<typeof builder>;

function capsuleKey(value: string) {
  return value.split('@', 1)[0];
}

function addCapsules(graph: GraphBuilder, source: string, values: unknown[], declarations: Map<string, Fields>) {
  for (const value of values) {
    const reference = string(value);
    if (!reference) continue;
    const key = capsuleKey(reference);
    const details = { ...declarations.get(key), reference };
    graph.link(source, graph.node('capsule', key, details, atlasTitle(key) ?? key), 'capsule');
  }
}

function addRunContext(graph: GraphBuilder, contract: Fields | undefined, tasks: Fields[], primaryTaskId?: string) {
  const contractId = string(contract?.contract_id);
  const root = contract && contractId ? graph.node('contract', contractId, contract) : undefined;
  const declarations = new Map<string, Fields>();
  for (const declaration of rows(record(contract?.ontology)?.capsule_slices)) {
    const capsule = string(declaration.capsule);
    if (capsule) declarations.set(capsuleKey(capsule), declaration);
  }
  for (const task of tasks) {
    const taskId = string(task.task_id);
    if (!taskId) continue;
    const taskNode = graph.node('task', taskId, task, string(record(task.operator_labels)?.display_name) ?? taskId);
    const taskContract = string(task.contract_id);
    if (root && (!taskContract || taskContract === contractId || taskId === primaryTaskId)) {
      graph.link(root, taskNode, 'contract');
    } else if (taskContract) {
      graph.link(graph.node('contract', taskContract, { contract_id: taskContract }), taskNode, 'contract');
    }
    addCapsules(
      graph,
      taskNode,
      [...list(record(task.resources)?.capsules), task.component_cc, task.capability_cc],
      declarations,
    );
  }
  if (root && tasks.length === 0) {
    addCapsules(graph, root, [...declarations.keys()], declarations);
  }
  return declarations;
}

function taskGraph(value: Fields, context: GraphContext): GraphModel | null {
  const rawNodes = rows(value.nodes);
  if (
    value.schema !== 'factory.taskgraph/1' &&
    !rawNodes.some((node) => string(node.node_id) && Array.isArray(node.depends_on))
  ) {
    return null;
  }
  const graph = builder('taskgraph');
  const tasks = rows(context.tasks).filter((task) => string(task.task_id));
  const taskId = string(value.task_id);
  const declarations = addRunContext(graph, record(context.contract), tasks, taskId);
  const bindings = new Map<string, string[]>();
  for (const observation of rows(context.observations)) {
    if (observation.kind !== 'node_contract_final' || (observation.task_id && observation.task_id !== taskId)) continue;
    const final = record(observation.values);
    const id = string(final?.node_id);
    const digest = string(final?.digest);
    if (!id || !digest) continue;
    const capsules = list(record(record(final?.final)?.work)?.bound_ccs).map(string);
    bindings.set(JSON.stringify([id, digest]), [...new Set(capsules.filter((item) => item !== undefined))]);
  }
  for (const node of rawNodes) {
    const id = string(node.node_id);
    if (!id) continue;
    const boundCCs = bindings.get(JSON.stringify([id, node.final_contract]));
    graph.node('step', id, node, context.nodePresentation?.[id]?.title ?? string(node.title) ?? id, id, boundCCs);
  }
  for (const node of rawNodes) {
    const id = string(node.node_id);
    if (!id) continue;
    const target = idOf('step', id);
    const dependencies = list(node.depends_on)
      .map(string)
      .filter((name) => name !== undefined);
    for (const dependency of dependencies) graph.link(idOf('step', dependency), target, 'dependency');
    if (!dependencies.length && taskId) graph.link(idOf('task', taskId), target, 'step');
    const replacement = string(node.superseded_by);
    if (replacement) graph.link(target, idOf('step', replacement), 'superseded');
    addCapsules(graph, target, [node.capability], declarations);
  }
  const task = tasks.find((item) => item.task_id === taskId);
  return {
    ...graph.model(rows(value.history), taskId),
    taskChecks: indexTaskGraphChecks(context.observations ?? [], taskId),
    defaultChecks: record(record(task?.constraints)?.node_checks),
  };
}

function ontologyGraph(value: Fields): GraphModel | null {
  const relationMap = record(value.relations);
  if (!relationMap && !Array.isArray(value.relations)) return null;
  const graph = builder('ontology');
  const entities = record(value.entities);
  function entity(id: string) {
    const definition = entities && Object.prototype.hasOwnProperty.call(entities, id) ? entities[id] : undefined;
    return graph.node('entity', id, record(definition) ?? { entity: id, description: definition });
  }
  function relation(source: string | undefined, target: string | undefined, label?: string) {
    if (source && target) graph.link(entity(source), entity(target), 'relation', label);
  }
  for (const [name, definition] of Object.entries(relationMap ?? {})) {
    const [source, target] =
      string(definition)
        ?.split(/(?:->|→)/, 2)
        .map(string) ?? [];
    const structured = record(definition);
    relation(source ?? string(structured?.source), target ?? string(structured?.target), name);
  }
  for (const edge of rows(value.relations)) {
    relation(string(edge.source ?? edge.from), string(edge.target ?? edge.to), string(edge.relation ?? edge.type));
  }
  const model = graph.model();
  return model.links.length ? model : null;
}

function mermaidBlocks(source: string): GraphModel | null {
  const lines = source
    .replace(/%%\{[\s\S]*?\}%%/g, '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('%%'));
  if (lines[0] !== 'block-beta') return null;
  const graph = builder('ontology');
  const groups: { id: string; label: string; members: string[] }[] = [];
  for (const line of lines.slice(1)) {
    const group = /^block:([\w.-]+)(?:\["([^"]*)"\])?$/.exec(line);
    if (group) {
      groups.push({ id: group[1], label: group[2]?.trim() || group[1], members: [] });
      continue;
    }
    if (line === 'end') {
      const current = groups.pop();
      if (!current) continue;
      const groupId = graph.node('group', current.id, { block: current.id, title: current.label }, current.label);
      for (const member of current.members) graph.link(groupId, member, 'member');
      groups[groups.length - 1]?.members.push(groupId);
      continue;
    }
    const member = /^([\w.-]+)\["([^"]+)"\]$/.exec(line);
    if (!member) continue;
    const [, id, label] = member;
    const current = groups[groups.length - 1];
    if (current && current.label === current.id && id === `h_${current.id.replace(/^g_/, '')}`) {
      current.label = label;
      continue;
    }
    const node = graph.node('entity', id, { block: current?.id, title: label }, label);
    current?.members.push(node);
  }
  if (groups.length) return null;
  const model = graph.model();
  return model.nodes.length ? model : null;
}

export function detectGraph(value: unknown, context: GraphContext = {}): GraphModel | null {
  if (typeof value === 'string') return mermaidBlocks(value);
  const object = record(value);
  if (!object) return null;
  const native = taskGraph(object, context);
  if (native) return native;
  const ontology = ontologyGraph(object);
  if (ontology) return ontology;
  const contract = record(context.contract) ?? record(object.contract) ?? object;
  const tasks = rows(context.tasks ?? object.tasks).filter((task) => string(task.task_id));
  if (!string(contract.contract_id)) return null;
  const graph = builder('contract');
  addRunContext(graph, contract, tasks);
  const model = graph.model([], string(tasks[0]?.task_id));
  return model.links.length ? model : null;
}

function nodeEvent(node: Fields, event: StoryEvent) {
  return [...list(node.evidence_ids), ...list(node.attempt_ids)].some(
    (id) => typeof id === 'string' && (event.id === id || event.id.startsWith(`${id}:`)),
  );
}

function applyHistory(
  snapshots: Map<string, Fields>,
  patch: Fields,
  decisionRev: unknown,
  touched?: Set<string>,
  onRestart?: (id: string) => void,
) {
  for (const operation of ['add', 'update', 'cancel', 'supersede']) {
    for (const change of rows(patch[operation])) {
      const id = string(change.node_id);
      if (!id) continue;
      touched?.add(id);
      const prior = snapshots.get(id);
      if (operation === 'add') {
        snapshots.set(id, {
          capability: null,
          inputs: [],
          depends_on: [],
          state: 'proposed',
          attempt_ids: [],
          evidence_ids: [],
          reason: '',
          ...change,
          created_by_decision_rev: decisionRev,
        });
      } else if (prior && operation === 'update') {
        snapshots.set(id, {
          ...prior,
          ...change,
          attempt_ids: [...new Set([...list(prior.attempt_ids), ...list(change.attempt_ids)])],
          evidence_ids: [...new Set([...list(prior.evidence_ids), ...list(change.evidence_ids)])],
        });
      } else if (prior) {
        const state = operation === 'cancel' ? 'cancelled' : 'superseded';
        snapshots.set(id, { ...prior, state, reason: change.reason, superseded_by: change.by });
      }
    }
  }
  for (const change of rows(patch.revise)) {
    const id = string(change.node_id);
    if (!id) continue;
    const node = snapshots.get(id);
    touched?.add(id);
    if (change.action === 'add' && record(change.node)) {
      snapshots.set(id, { state: 'proposed', depends_on: [], ...record(change.node) });
    } else if (node && change.action === 'cancel') {
      const { hold: _hold, ...fields } = node;
      snapshots.set(id, { ...fields, state: 'cancelled', reason: change.reason });
    } else if (node && change.action === 'update') {
      const changed = Object.fromEntries(
        ['title', 'kind', 'capability', 'check', 'resources', 'state', 'depends_on']
          .filter((field) => field in change)
          .map((field) => [field, change[field]]),
      );
      const next = { ...node, ...changed };
      if (change.unfinalize) delete next.final_contract;
      snapshots.set(id, next);
    }
  }
  for (const change of rows(patch.finalize)) {
    const id = string(change.node_id);
    if (!id) continue;
    const node = snapshots.get(id);
    if (node) snapshots.set(id, { ...node, final_contract: change.digest, check: change.check });
  }
  for (const change of rows(patch.retire)) {
    const id = string(change.node_id);
    if (!id) continue;
    const node = snapshots.get(id);
    if (!node) continue;
    touched?.add(id);
    snapshots.set(id, { ...node, state: 'cancelled' });
    for (const [otherId, other] of snapshots) {
      if (list(other.depends_on).includes(id)) {
        snapshots.set(otherId, { ...other, depends_on: list(other.depends_on).filter((dependency) => dependency !== id) });
      }
    }
  }
  for (const change of rows(patch.reopen)) {
    const id = string(change.node_id);
    if (!id || !snapshots.has(id)) continue;
    const pending = new Set([id]);
    for (const reopened of pending) {
      const node = snapshots.get(reopened);
      if (!node) continue;
      if (reopened === id || !['cancelled', 'superseded', 'proposed'].includes(String(node.state))) {
        const { final_contract: _final, hold: _hold, ...fields } = node;
        touched?.add(reopened);
        onRestart?.(reopened);
        snapshots.set(reopened, { ...fields, state: 'proposed', evidence_ids: [], reason: change.reason });
      }
      for (const [otherId, other] of snapshots) {
        if (list(other.depends_on).includes(reopened)) pending.add(otherId);
      }
    }
  }
}

function graphNodesOf(event: StoryEvent | undefined) {
  return Array.isArray(event?.graph_nodes) ? event.graph_nodes.filter((id): id is string => typeof id === 'string') : [];
}

function nodeMatches(node: GraphNode, ids: readonly string[]) {
  return ids.some((id) => id === node.id || (node.planId !== undefined && id === node.planId));
}

/**
 * Curated replays name the graph nodes each step touches. A node lights up
 * once a visible step names it; the current step's nodes are highlighted.
 */
function curatedProgress(graph: GraphModel, replay: GraphReplay) {
  const visible = replay.events.slice(0, Math.max(0, replay.position));
  const current = graphNodesOf(visible[visible.length - 1]);
  const seen = new Set(visible.flatMap(graphNodesOf));
  const result = new Map<string, NodeProgress>();
  for (const node of graph.nodes) {
    if (nodeMatches(node, current)) result.set(node.id, { phase: 'current' });
    else if (nodeMatches(node, [...seen])) result.set(node.id, { phase: 'seen' });
    else if (node.kind === 'step' || node.kind === 'task') result.set(node.id, { phase: 'upcoming' });
  }
  return result;
}

export function graphProgress(graph: GraphModel, replay: GraphReplay): Map<string, NodeProgress> {
  if (replay.curated || replay.events.some((event) => typeof event.step === 'number' && graphNodesOf(event).length)) {
    return curatedProgress(graph, replay);
  }
  const visible = replay.events.slice(0, Math.max(0, replay.position));
  const current = visible[visible.length - 1];
  const snapshots = new Map<string, Fields>();
  const touched = new Set<string>();
  for (const entry of [...graph.history].sort((a, b) => Number(a.rev) - Number(b.rev))) {
    const patch = record(entry.patch);
    const created = entry.created;
    if (!current || !patch || typeof created !== 'number' || created > current.created) continue;
    const eventId = `${graph.taskId}:plan:${entry.rev}`;
    const matches = current.id === eventId;
    if (created === current.created && !matches && !visible.some((event) => event.id === eventId)) continue;
    applyHistory(snapshots, patch, entry.decision_rev, matches ? touched : undefined);
  }
  const activeStep = (node: GraphNode) => {
    if (!node.planId || !current) return false;
    const details = graph.history.length ? snapshots.get(node.planId) : node.details;
    return touched.has(node.planId) || nodeMatches(node, graphNodesOf(current)) || Boolean(details && nodeEvent(details, current));
  };
  const hasActiveStep = graph.nodes.some(activeStep);
  const result = new Map<string, NodeProgress>();
  for (const node of graph.nodes) {
    if (node.planId && graph.history.length) {
      const details = snapshots.get(node.planId);
      result.set(node.id, { phase: activeStep(node) ? 'current' : details ? 'seen' : 'upcoming', details });
    } else if (node.planId) {
      const seen = visible.some((event) => nodeEvent(node.details, event));
      if (seen) result.set(node.id, { phase: activeStep(node) ? 'current' : 'seen' });
    } else if (node.kind === 'task' && string(node.details.task_id) === graph.taskId) {
      result.set(node.id, { phase: !current ? 'upcoming' : hasActiveStep ? 'seen' : 'current' });
    } else if (node.kind === 'capsule') {
      const capsule = string(node.details.reference);
      const matches = (event: StoryEvent) =>
        [event.capability, event.component, event.cc].some((value) => {
          const id = string(value);
          return id && capsuleKey(id) === capsuleKey(capsule ?? '');
        });
      if (visible.some(matches)) result.set(node.id, { phase: current && matches(current) ? 'current' : 'seen' });
    }
  }
  return result;
}

/** Replay the committed task graph up to this story position. */
export function taskGraphTimeline(graph: GraphModel, replay?: GraphReplay): TaskGraphTimelineNode[] {
  if (graph.kind !== 'taskgraph') return [];
  const nodes = graph.nodes.filter((node) => node.planId !== undefined);
  const visible = replay?.events.slice(0, replay.position) ?? [];
  const isLatest = !replay || replay.position >= replay.events.length;
  // A curated scheduler overview can cite contracts from across the run.
  // Its date does not advance the execution cursor.
  const executionEvents = visible.filter(
    (event) => !replay?.curated || !['node_contract_final', 'node_contract_refusal'].includes(event.kind),
  );
  const last = executionEvents[executionEvents.length - 1];
  const cutoff = last?.created ?? -Infinity;
  const eventIds = new Set(executionEvents.map((event) => event.id));
  const history = [...graph.history].sort((a, b) => Number(a.rev) - Number(b.rev));
  const completionOrder = new Map<string, number>();
  let revision = 0;
  for (const [index, entry] of history.entries()) {
    const patch = record(entry.patch);
    if (!patch) continue;
    // A decision and the graph patch it committed have separate timestamps.
    const matchingRecord =
      eventIds.has(`${graph.taskId}:plan:${entry.rev}`) ||
      (entry.origin === 'decision' && eventIds.has(`${graph.taskId}:decision:${entry.decision_rev}`));
    if (matchingRecord || (typeof entry.created === 'number' && entry.created < cutoff)) revision = index + 1;
    for (const node of [...rows(patch.add), ...rows(patch.update)]) {
      const id = string(node.node_id);
      if (!id) continue;
      if (node.state === 'done' && !completionOrder.has(id)) completionOrder.set(id, index);
    }
  }
  const orderOf = (node: GraphNode) => completionOrder.get(node.planId ?? '') ?? history.length;
  if (!replay?.liveDemo) nodes.sort((a, b) => orderOf(a) - orderOf(b));
  const states = new Map<string, Fields>();
  const reopenedAt = new Map<string, number>();
  for (const entry of replay ? history.slice(0, revision) : history) {
    const patch = record(entry.patch);
    if (!patch) continue;
    const created = entry.created;
    applyHistory(states, patch, entry.decision_rev, undefined, (id) => {
      if (typeof created === 'number') reopenedAt.set(id, created);
    });
  }

  const detailsOf = (node: GraphNode) =>
    !replay || (isLatest && (!history.length || replay.liveDemo)) ? node.details : states.get(node.planId ?? '');
  const stateOf = (node: GraphNode) => detailsOf(node)?.state;
  const unresolved = (node: GraphNode) => !['done', 'cancelled', 'superseded'].includes(String(stateOf(node)));
  const runState = replay?.runState;
  const since = typeof runState?.since === 'string' ? Date.parse(runState.since) / 1000 : runState?.since;
  const terminalReached =
    (replay?.liveDemo && isLatest) || (runState?.source && eventIds.has(runState.source)) ||
    (typeof since === 'number' && Number.isFinite(since) ? cutoff >= since : isLatest);
  const stopped = runState?.state === 'stopped' && terminalReached;
  const finished = runState?.state === 'finished' && terminalReached;
  const active = replay?.liveDemo && isLatest ? nodes.find((node) => node.planId === runState?.node_id && unresolved(node)) : undefined;
  const current = stopped || finished ? undefined : active ?? nodes.find(unresolved);
  const recordsPath = replay?.files?.find((file) => file.path === 'records/observations.json')?.path;
  const activityCutoff = replay && !(replay.liveDemo && isLatest) ? cutoff : Infinity;
  return nodes.map((node) => {
    let replayState: TaskGraphTimelineNode['replayState'] = 'not-reached';
    if (stateOf(node) === 'done') replayState = 'done';
    else if (node === current) replayState = 'current';
    else if (stopped && unresolved(node)) replayState = 'stopped';
    const planId = node.planId ?? '';
    const activity = replay?.ccActivity?.[planId] ??
      legacyTimelineActivity(graph.taskChecks?.get(planId) ?? [], node.boundCCs ?? [], recordsPath);
    const boundary = reopenBoundary(activity, activityCutoff, reopenedAt.get(planId));
    const capsuleFacts = capsuleFactsAt(activity, activityCutoff, boundary);
    const boundCCs = capsuleFacts.map(({ id }) => id);
    const nodeVerifier = nodeVerifierAt(activity, activityCutoff, boundary, replayState === 'done');
    return { ...node, replayState, boundCCs, capsuleFacts, nodeVerifier };
  });
}

/** Direct children: targets of a node's outgoing links. */
export function graphChildren(graph: GraphModel) {
  const children = new Map<string, string[]>();
  for (const link of graph.links) {
    if (link.source === link.target) continue;
    const list = children.get(link.source) ?? [];
    if (!list.includes(link.target)) list.push(link.target);
    children.set(link.source, list);
  }
  return children;
}

function reach(graph: GraphModel, collapsed: ReadonlySet<string>) {
  const children = graphChildren(graph);
  const incoming = new Set(graph.links.filter((link) => link.source !== link.target).map((link) => link.target));
  const roots = graph.nodes.filter((node) => !incoming.has(node.id)).map((node) => node.id);
  const seen = new Set<string>();
  const queue = [...roots];
  while (queue.length) {
    const id = queue.shift() as string;
    if (seen.has(id)) continue;
    seen.add(id);
    if (collapsed.has(id)) continue;
    for (const child of children.get(id) ?? []) if (!seen.has(child)) queue.push(child);
  }
  return seen;
}

/**
 * Nodes left visible when the given nodes are collapsed. A node stays visible
 * while any expanded path from a root reaches it; nodes that no root reaches
 * (cycles) are always shown.
 */
export function visibleGraphNodes(graph: GraphModel, collapsed: ReadonlySet<string>) {
  const full = reach(graph, new Set());
  const partial = reach(graph, collapsed);
  return new Set(graph.nodes.filter((node) => partial.has(node.id) || !full.has(node.id)).map((node) => node.id));
}

/** Count of descendants hidden under a collapsed node. */
export function hiddenUnder(graph: GraphModel, id: string, visible: ReadonlySet<string>) {
  const children = graphChildren(graph);
  const seen = new Set<string>();
  const queue = [...(children.get(id) ?? [])];
  while (queue.length) {
    const next = queue.shift() as string;
    if (seen.has(next) || visible.has(next)) continue;
    seen.add(next);
    queue.push(...(children.get(next) ?? []));
  }
  return seen.size;
}

/** Nodes that have children; "collapse all" collapses each of them. */
export function collapsibleNodes(graph: GraphModel) {
  return new Set(graphChildren(graph).keys());
}
