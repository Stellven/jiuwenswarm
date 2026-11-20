import { useEffect, useMemo, useRef, useState } from 'react';
import { MarkerType, Position, ReactFlow, type Edge, type Node } from '@xyflow/react';
import dagre from '@dagrejs/dagre';
import { Button } from '../../components/ui/Button/Button';
import { factoryClient } from './factoryClient';
import { mountGuidedReplay } from './guidedReplay/mountGuidedReplay';
import { libraryClient, libraryTerminal, type LibraryEvent, type LibraryGraph, type LibraryJob } from './libraryClient';
import { readSchedulerAssignment, readSchedulerDispatch, schedulerNarrative } from './libraryNarrative';
import './live-factory-workflow.css';

type Task = Record<string, unknown>;
type Preset = 'routing' | 'full' | 'custom';
type LiveGraph = Pick<LibraryGraph, 'edges'> & { nodes: { id: string; name?: string }[] };

const presets: { id: Preset; label: string }[] = [
  { id: 'routing', label: 'Expert routing only' },
  { id: 'full', label: 'Expert routing, activation and combination' },
  { id: 'custom', label: 'Custom task JSON' },
];

function object(value: unknown): Task | undefined {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Task) : undefined;
}

function errorText(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  const record = object(error);
  return typeof record?.message === 'string' ? record.message : JSON.stringify(error) || 'Unknown error';
}

function taskJSON(task: Task, preset: Preset) {
  if (preset !== 'routing') return JSON.stringify(task, null, 2);
  const required = new Set(['strata.source', 'strata.binary', 'strata.result.routing']);
  return JSON.stringify(
    {
      ...task,
      description: 'Build the Ascend C++ expert router and run it with the CPU executable.',
      required_outputs: (task.required_outputs as string[]).filter((kind) => required.has(kind)),
      inputs: { routing: object(task.inputs)?.routing },
    },
    null,
    2,
  );
}

function label(status: string) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function updateHistory(jobs: LibraryJob[], job: LibraryJob): LibraryJob[] {
  const summary = { id: job.id, status: job.status, created_at: job.created_at, request: job.request };
  return [summary, ...jobs.filter((item) => item.id !== job.id)].sort((left, right) =>
    (right.created_at ?? '').localeCompare(left.created_at ?? ''),
  );
}

function eventNode(event: LibraryEvent) {
  const id = event.node_id ?? event.payload.node_id;
  return typeof id === 'string' ? id : undefined;
}

function BuildGraph({ graph, statuses }: { graph: LiveGraph; statuses: Map<string, string> }) {
  const { nodes, edges } = useMemo(() => {
    const dag = new dagre.graphlib.Graph();
    dag.setGraph({ rankdir: 'LR', nodesep: 22, ranksep: 55 });
    dag.setDefaultEdgeLabel(() => ({}));
    for (const node of graph.nodes) dag.setNode(node.id, { width: 186, height: 58 });
    const bindings = graph.edges ?? [];
    for (const edge of bindings) dag.setEdge(edge.from, edge.to);
    dagre.layout(dag);
    const nodes: Node[] = graph.nodes.map((node) => {
      const { x, y } = dag.node(node.id);
      const status = statuses.get(node.id) ?? 'pending';
      return {
        id: node.id,
        className: 'live-factory-graph-node is-' + status,
        position: { x: x - 93, y: y - 29 },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        data: {
          label: (
            <div data-testid="workflow-demo-live-graph-node" data-variant={node.id}>
              <strong>{node.name ?? node.id}</strong>
              <span className="live-factory-node-status">{label(status)}</span>
            </div>
          ),
        },
      };
    });
    const edges: Edge[] = bindings.map((edge, index) => ({
      id: `${edge.from}:${edge.to}:${edge.input ?? index}`,
      source: edge.from,
      target: edge.to,
      markerEnd: { type: MarkerType.ArrowClosed },
    }));
    return { nodes, edges };
  }, [graph, statuses]);
  const names = new Map(graph.nodes.map((node) => [node.id, node.name ?? node.id]));
  return (
    <>
      <div className="live-factory-graph" data-testid="workflow-demo-live-graph">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.16 }}
          minZoom={0.15}
          nodesDraggable={false}
          nodesConnectable={false}
          nodesFocusable={false}
          edgesFocusable={false}
          elementsSelectable={false}
          zoomOnScroll={false}
          proOptions={{ hideAttribution: true }}
        />
      </div>
      {!!graph.edges?.length && (
        <details data-testid="workflow-demo-live-data-handoffs">
          <summary>Data handoffs</summary>
          <ul>
            {graph.edges.map((edge, index) => (
              <li key={`${edge.from}:${edge.to}:${edge.input ?? index}`}>
                {names.get(edge.from) ?? edge.from} → {edge.data ?? edge.output ?? 'Output'} →{' '}
                {names.get(edge.to) ?? edge.to}
              </li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}

function describeEvent(event: LibraryEvent, names: Map<string, string>): string | undefined {
  const payload = event.payload;
  const id = eventNode(event);
  const name = id ? (names.get(id) ?? id) : undefined;
  if (event.type === 'job.started') return 'Build run started';
  if (event.type === 'source.started') return 'Preparing source for ' + String(payload.name ?? payload.id);
  if (event.type === 'source.ready')
    return `${payload.name ?? payload.id} · ${String(payload.revision ?? '').slice(0, 12)}`;
  if (event.type === 'catalog.started') return 'Extracting the Workflow Library';
  if (event.type === 'catalog.ready') return 'Workflow Library ready';
  if (event.type === 'planner.graph_created') return 'Task Graph created';
  if (event.type === 'planner.decision') {
    if (payload.type === 'select')
      return `${payload.origin === 'build_action' ? 'Schedule' : 'Select'} ${payload.name}`;
    if (payload.type === 'bind')
      return `${names.get(String(payload.from)) ?? payload.from} → ${names.get(String(payload.to)) ?? payload.to}`;
  }
  if (event.type.startsWith('scheduler.')) return schedulerNarrative(event, name);
  if (event.type.startsWith('node.') && name) return `${name} · ${label(event.type.slice(5))}`;
  if (event.type === 'command.started') {
    const argv = object(payload.command)?.argv;
    return Array.isArray(argv) ? '$ ' + argv.map(String).join(' ') : undefined;
  }
  if (event.type === 'operation.result' && name) return `${name} · result recorded`;
  if (event.type === 'job.finished') return `Build run ${String(payload.status ?? 'finished')}`;
  if (event.type === 'job.failed' || event.type === 'job.blocked') return `Build run ${event.type.slice(4)}`;
  return undefined;
}

function BuildEvent({ event, title }: { event: LibraryEvent; title: string }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <details
      className="live-factory-event"
      data-testid="workflow-demo-live-event"
      data-variant={String(event.sequence)}
      onToggle={(e) => setExpanded(e.currentTarget.open)}
    >
      <summary>{title}</summary>
      {expanded && <pre>{JSON.stringify(event.payload, null, 2)}</pre>}
    </details>
  );
}

function SchedulerDispatch({ events, names }: { events: LibraryEvent[]; names: Map<string, string> }) {
  const started = events.find((event) => event.type === 'scheduler.started');
  const planned = events.find((event) => event.type === 'scheduler.assignments_ready')?.payload.assignments;
  const finished = events.find((event) => event.type === 'scheduler.finished');
  const assignments = Array.isArray(planned)
    ? planned.map(readSchedulerAssignment).filter(Boolean)
    : events.map(readSchedulerDispatch).filter(Boolean);
  if (!started && !finished && !assignments.length) return null;
  const outcome = typeof finished?.payload.status === 'string' ? finished.payload.status : undefined;
  const filename = object(started?.payload.graph_input)?.filename;
  return (
    <section className="live-factory-scheduler" data-testid="workflow-demo-live-scheduler">
      <div className="live-factory-panel-title">
        <h4>Scheduling</h4>
        {outcome && <strong data-testid="workflow-demo-live-scheduler-outcome">{label(outcome)}</strong>}
      </div>
      {started && <p>Scheduler received {typeof filename === 'string' ? <code>{filename}</code> : 'the Task Graph'}.</p>}
      {!!assignments.length && (
        <ul aria-label="Builder assignments">
          {assignments.map((assignment) => assignment && (
            <li
              key={assignment.nodeId}
              data-testid="workflow-demo-live-builder-assignment"
              data-variant={assignment.nodeId}
              data-worker-type={assignment.workerType}
            >
              <span>{names.get(assignment.nodeId) ?? assignment.nodeId}</span>
              <span aria-hidden="true">→</span>
              <strong>{assignment.builder}</strong>
              {assignment.reason && <span className="live-factory-assignment-reason">{assignment.reason}</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function BuildProgress({
  job,
  events,
  error,
  onReconnect,
  onOpenProduct,
}: {
  job: LibraryJob | null;
  events: LibraryEvent[];
  error: string;
  onReconnect: () => void;
  onOpenProduct: () => void;
}) {
  const statuses = new Map<string, string>();
  if (job?.nodes) {
    for (const [key, node] of Object.entries(job.nodes)) {
      const id = node.id ?? key;
      statuses.set(id, node.status);
    }
  }
  let graph: LiveGraph | undefined = job?.graph;
  let outcome = job?.status ?? 'pending';
  let failure = job?.error;
  const has = (type: string) => events.some((event) => event.type === type);
  for (const event of events) {
    if (event.type === 'planner.graph_created') graph = event.payload.graph as LiveGraph;
    else if (event.type === 'graph.validated' && !graph) graph = event.payload.graph as LiveGraph;
    const id = eventNode(event);
    if (id && (event.type === 'node.started' || /^node\.(verified|failed|blocked)$/.test(event.type)))
      statuses.set(id, event.type === 'node.started' ? 'running' : event.type.slice(5));
    if (event.type === 'job.started' && outcome === 'pending') outcome = 'running';
    if (event.type === 'job.finished' && typeof event.payload.status === 'string') outcome = event.payload.status;
    if (event.type === 'job.failed' || event.type === 'job.blocked') {
      outcome = event.type.slice(4);
      failure = event.payload.error ?? failure;
    }
  }
  const names = new Map((graph?.nodes ?? []).map((node) => [node.id, node.name ?? node.id]));
  const sources = events.filter((event) => event.type === 'source.ready');
  const phases = [
    {
      id: 'intake',
      name: 'Source intake',
      state: has('catalog.started') ? 'ready' : has('source.started') ? 'running' : 'pending',
    },
    {
      id: 'library',
      name: 'Workflow Library',
      state: has('catalog.ready') ? 'ready' : has('catalog.started') ? 'running' : 'pending',
    },
    { id: 'plan', name: 'Compose', state: graph ? 'ready' : has('planner.decision') ? 'running' : 'pending' },
    {
      id: 'scheduling',
      name: 'Scheduling',
      state: has('scheduler.assignments_ready') || has('scheduler.finished') ? 'ready'
        : has('scheduler.started') ? 'running' : 'pending',
    },
    {
      id: 'build',
      name: 'Construction',
      state: has('node.started') ? outcome : 'pending',
    },
  ].map((phase) =>
    phase.state === 'running' && (outcome === 'failed' || outcome === 'blocked') ? { ...phase, state: outcome } : phase,
  );
  const visible = events.flatMap((event) => {
    const title = describeEvent(event, names);
    return title ? [{ event, title }] : [];
  });
  const terminal = events
    .filter((event) => event.type === 'command.output' && typeof event.payload.text === 'string')
    .map((event) => String(event.payload.text))
    .join('');
  return (
    <section className="live-factory-panel" data-testid="workflow-demo-live-run">
      <header className="live-factory-panel-title">
        <h3>Build run</h3>
        <strong data-testid="workflow-demo-live-status" data-variant={outcome}>
          {label(outcome)}
        </strong>
      </header>
      {job && (
        <code className="live-factory-run-id" data-testid="workflow-demo-live-job-id">
          {job.id}
        </code>
      )}
      <ol className="live-factory-phases" aria-label="Build phases">
        {phases.map((phase) => (
          <li key={phase.id} data-testid="workflow-demo-live-phase" data-variant={phase.id} data-state={phase.state}>
            {phase.name}
            <span>{label(phase.state)}</span>
          </li>
        ))}
      </ol>
      {!!sources.length && (
        <ul className="live-factory-sources">
          {sources.map((event) => (
            <li key={event.sequence}>
              {String(event.payload.name ?? event.payload.id)}{' '}
              <code>{String(event.payload.revision ?? '').slice(0, 12)}</code>
            </li>
          ))}
        </ul>
      )}
      {failure !== undefined && failure !== null && (
        <p role="alert" className="live-factory-error" data-testid="workflow-demo-live-build-error">
          {errorText(failure)}
        </p>
      )}
      {error && (
        <div role="alert" className="live-factory-error">
          <p>{error}</p>
          <Button size="sm" onClick={onReconnect} data-testid="workflow-demo-live-reconnect">
            Reconnect
          </Button>
        </div>
      )}
      {graph?.nodes.length ? <BuildGraph graph={graph} statuses={statuses} /> : null}
      <SchedulerDispatch events={events} names={names} />
      {job?.status === 'verified' && job.product_ready === true && (
        <Button size="sm" variant="primary" data-testid="workflow-demo-live-open-product" onClick={onOpenProduct}>
          Open Product
        </Button>
      )}
      {!!visible.length && (
        <section
          className="live-factory-events"
          data-testid="workflow-demo-live-events"
          aria-label="Build event timeline"
        >
          <h4>Build events</h4>
          {visible.map(({ event, title }) => (
            <BuildEvent key={event.sequence} event={event} title={title} />
          ))}
        </section>
      )}
      {terminal && (
        <details data-testid="workflow-demo-live-terminal">
          <summary>Terminal output</summary>
          <pre>{terminal}</pre>
        </details>
      )}
    </section>
  );
}

function LiveProduct({ id, close }: { id: string; close: () => void }) {
  const target = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [error, setError] = useState('');
  useEffect(() => {
    const element = target.current;
    if (!element) return;
    const controller = new AbortController();
    let dispose: (() => void) | undefined;
    void libraryClient
      .buildProduct(id, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        dispose = mountGuidedReplay(element, data, 'product');
        setStatus('ready');
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(errorText(reason));
          setStatus('error');
        }
      });
    return () => {
      controller.abort();
      dispose?.();
    };
  }, [id]);
  return (
    <section className="live-factory-product" data-testid="workflow-demo-live-product">
      <div className="live-factory-product-back">
        <Button size="sm" onClick={close} data-testid="workflow-demo-live-return-to-build">
          Back to build
        </Button>
      </div>
      {status === 'loading' && (
        <p role="status" className="p-shell">
          Opening Product.
        </p>
      )}
      {status === 'error' && (
        <p role="alert" className="live-factory-error p-shell">
          {error}
        </p>
      )}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden" ref={target} />
    </section>
  );
}

export function LiveFactoryWorkflow() {
  const [preset, setPreset] = useState<Preset>('routing');
  const [template, setTemplate] = useState<Task>();
  const [task, setTask] = useState('');
  const [inputError, setInputError] = useState('');
  const [starting, setStarting] = useState(false);
  const startRequest = useRef<AbortController>();
  const [jobs, setJobs] = useState<LibraryJob[]>([]);
  const [historyError, setHistoryError] = useState('');
  const [id, setId] = useState(() => new URLSearchParams(window.location.search).get('workflowBuild') ?? '');
  const [job, setJob] = useState<LibraryJob | null>(null);
  const [events, setEvents] = useState<LibraryEvent[]>([]);
  const [streamError, setStreamError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [product, setProduct] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void factoryClient
      .guidedReplay(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        const original = object(object(object(data)?.composition)?.task);
        if (!original || !Array.isArray(original.required_outputs) || !object(original.inputs)?.routing)
          throw new Error('The recorded task template is unavailable.');
        setTemplate(original);
        setTask((current) => current || taskJSON(original, 'routing'));
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setPreset('custom');
          setInputError('The task examples are unavailable. Enter a custom task JSON.');
        }
      });
    void libraryClient
      .builds(controller.signal)
      .then(({ jobs }) => {
        if (!controller.signal.aborted) setJobs(jobs);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setHistoryError(errorText(reason));
      });
    return () => {
      controller.abort();
      startRequest.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    setStreamError('');
    setEvents([]);
    setJob(null);
    let cursor = 0;
    function receive(event: LibraryEvent) {
      if (controller.signal.aborted || event.sequence <= cursor) return;
      cursor = event.sequence;
      setEvents((previous) => [...previous, event]);
    }
    function adopt(snapshot: LibraryJob) {
      if (controller.signal.aborted) return;
      for (const event of snapshot.events ?? []) receive(event);
      setJob(snapshot);
      setJobs((previous) => updateHistory(previous, snapshot));
    }
    void (async () => {
      const initial = await libraryClient.build(id, controller.signal);
      adopt(initial);
      if (controller.signal.aborted || libraryTerminal(initial.status)) return;
      await libraryClient.buildStream(id, cursor, receive, controller.signal);
      if (controller.signal.aborted) return;
      const latest = await libraryClient.build(id, controller.signal);
      adopt(latest);
      if (!libraryTerminal(latest.status)) setStreamError('The event stream closed before the run finished.');
    })().catch((reason: unknown) => {
      if (!controller.signal.aborted) setStreamError(errorText(reason));
    });
    return () => controller.abort();
  }, [id, attempt]);

  function selectBuild(next: string) {
    const url = new URL(window.location.href);
    url.searchParams.set('view', 'workflow');
    url.searchParams.set('workflowBuild', next);
    url.searchParams.delete('workflowMode');
    window.history.replaceState(window.history.state, '', url);
    if (next !== id) {
      setJob(null);
      setEvents([]);
      setStreamError('');
    }
    setId(next);
    setProduct(false);
  }

  async function start() {
    setInputError('');
    let values: Task | undefined;
    try {
      values = object(JSON.parse(task));
    } catch {
      setInputError('Task JSON must be a valid JSON object.');
      return;
    }
    if (!values) {
      setInputError('Task JSON must be a valid JSON object.');
      return;
    }
    const controller = new AbortController();
    startRequest.current = controller;
    setStarting(true);
    try {
      const created = await libraryClient.startBuild(values, controller.signal);
      if (controller.signal.aborted) return;
      setJobs((previous) => updateHistory(previous, created));
      selectBuild(created.id);
    } catch (reason) {
      if (!controller.signal.aborted) setInputError(errorText(reason));
    } finally {
      if (!controller.signal.aborted) setStarting(false);
    }
  }

  if (product && id) return <LiveProduct id={id} close={() => setProduct(false)} />;

  return (
    <section className="live-factory-workspace" data-testid="workflow-demo-live-factory">
      <div className="live-factory-launch">
        <section className="live-factory-panel" aria-label="Build STRATA">
          <h2>Build STRATA</h2>
          <label className="live-factory-label">
            Task
            <select
              value={preset}
              onChange={(event) => {
                const next = event.currentTarget.value as Preset;
                setPreset(next);
                if (next !== 'custom' && template) setTask(taskJSON(template, next));
              }}
              data-testid="workflow-demo-live-task-preset"
            >
              {presets.map((item) => (
                <option key={item.id} value={item.id} disabled={item.id !== 'custom' && !template}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <details open={preset === 'custom' || undefined} data-testid="workflow-demo-live-task-editor">
            <summary>Task JSON</summary>
            <textarea
              aria-label="Task JSON"
              spellCheck={false}
              rows={9}
              value={task}
              onChange={(event) => {
                setTask(event.currentTarget.value);
                setPreset('custom');
              }}
              data-testid="workflow-demo-live-task-json"
            />
          </details>
          {inputError && (
            <p role="alert" className="live-factory-error">
              {inputError}
            </p>
          )}
          <Button
            size="sm"
            variant="primary"
            loading={starting}
            disabled={!task.trim()}
            onClick={() => void start()}
            data-testid="workflow-demo-live-build"
          >
            Run build
          </Button>
        </section>
        <section className="live-factory-panel" aria-label="Build history">
          <h3>Build history</h3>
          {historyError && (
            <p role="alert" className="live-factory-error">
              {historyError}
            </p>
          )}
          {!historyError && jobs.length === 0 && <p>No saved runs.</p>}
          {!!jobs.length && (
            <ul className="live-factory-history">
              {jobs.map((entry) => {
                const description = object(entry.request?.task)?.description;
                return (
                  <li key={entry.id}>
                    <button
                      type="button"
                      onClick={() => selectBuild(entry.id)}
                      aria-pressed={id === entry.id}
                      data-testid="workflow-demo-live-history-item"
                      data-variant={entry.id}
                    >
                      <strong>{typeof description === 'string' ? description : 'STRATA build'}</strong>
                      <span>
                        {label(entry.status)} ·{' '}
                        {entry.created_at ? new Date(entry.created_at).toLocaleString() : entry.id}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
      {id && (
        <BuildProgress
          job={job}
          events={events}
          error={streamError}
          onReconnect={() => setAttempt((value) => value + 1)}
          onOpenProduct={() => setProduct(true)}
        />
      )}
    </section>
  );
}
