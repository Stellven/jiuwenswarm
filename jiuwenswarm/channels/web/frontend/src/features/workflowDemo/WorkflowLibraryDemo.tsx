import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Button } from '../../components/ui/Button/Button';
import { parseCodeDiff, pretty, statusColor } from './factoryClient';
import type { CodeDiffFile } from './factoryClient';
import { libraryClient, libraryTerminal } from './libraryClient';
import type {
  LibraryArtifact,
  LibraryCheck,
  LibraryCheckSummary,
  LibraryCommand,
  LibraryEvent,
  LibraryGraph,
  LibraryGraphNode,
  LibraryJob,
  LibraryJobKind,
  LibraryNodeState,
  LibraryModelAttempt,
  LibraryPart,
  LibrarySource,
  LibraryWorkflow,
} from './libraryClient';
import { componentOutcome, eventNarrative, recordedReferenceSources } from './libraryNarrative';
import { LibraryImportReplay } from './LibraryImportReplay';
import { LibraryParentSteps } from './LibraryParentSteps';
import './workflow-library.css';

const initialTask = JSON.stringify(
  {
    description:
      'Construct a source-bound STRATA routing implementation, generate original-reference GoogleTest tests and deliver the source project.',
    required_outputs: ['source.cpp', 'verification.report', 'delivery.source_zip'],
    source: { repository: 'https://github.com/niko1221/strata', revision: '13eedf552417a6a791a7d13c6597e24300ee3a09' },
    target_backend: 'ascend',
    validation_backend: 'cpu_reference',
    parameters: { operations: ['routing'] },
    acceptance: { native_compile: true, native_model_inference: true, compare_original: true },
  },
  null,
  2,
);

function rememberJob(kind: 'plan' | 'execution', id: string) {
  const url = new URL(window.location.href);
  url.searchParams.set(kind === 'plan' ? 'libraryPlan' : 'libraryExecution', id);
  if (kind === 'plan') url.searchParams.delete('libraryExecution');
  url.searchParams.delete('libraryCheck');
  url.searchParams.delete('libraryNode');
  url.searchParams.delete('libraryImport');
  window.history.replaceState(null, '', url);
}

type InspectorTab = 'mapping' | 'identity' | 'source' | 'execution' | 'artifacts' | 'diff' | 'results';
type EditorTab = 'task' | 'contract' | 'policy' | 'decisions';
interface ObservedEvent {
  key: string;
  jobId: string;
  event: LibraryEvent;
}

function Dot({ status }: { status: string }) {
  return <span className="wd-status" data-variant={statusColor(status)} role="img" aria-label={status} />;
}
function CommandContent({ command }: { command: LibraryCommand }) {
  return (
    <div className="wl-process-command">
      <code>{command.argv?.map((argument) => JSON.stringify(argument)).join(' ')}</code>
      <dl className="wd-lineage">
        <dt data-testid="workflow-demo-library-command-directory-label">Directory</dt>
        <dd>{command.cwd}</dd>
        {typeof command.pid === 'number' && (
          <>
            <dt data-testid="workflow-demo-library-command-pid-label">Process</dt>
            <dd>{command.pid}</dd>
          </>
        )}
        {typeof command.exit_code === 'number' && (
          <>
            <dt data-testid="workflow-demo-library-command-exit-label">Exit</dt>
            <dd>{command.exit_code}</dd>
          </>
        )}
      </dl>
      {command.stdout && <pre>{command.stdout}</pre>}
      {command.stderr && <pre>{command.stderr}</pre>}
    </div>
  );
}

function EventContent({ event }: { event: LibraryEvent }) {
  const payload = event.payload || {};
  const command = payload.command as LibraryCommand | undefined;
  if (command?.argv) return <CommandContent command={command} />;
  if (typeof payload.text === 'string')
    return (
      <div>
        {typeof payload.stream === 'string' && <code>{payload.stream}</code>}
        {Array.isArray(payload.argv) && <code className="wl-event-job">{payload.argv.map(String).join(' ')}</code>}
        <pre>{payload.text}</pre>
      </div>
    );
  return <pre>{pretty(payload)}</pre>;
}

function parseTask(value: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(value);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function sourceSymbols(value: unknown): { path: string; symbol?: string; line?: number }[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item: unknown) => {
    if (!item || typeof item !== 'object') return [];
    const row = item as { path?: unknown; symbol?: unknown; line?: unknown };
    return typeof row.path === 'string'
      ? [
          {
            path: row.path,
            symbol: typeof row.symbol === 'string' ? row.symbol : undefined,
            line: typeof row.line === 'number' ? row.line : undefined,
          },
        ]
      : [];
  });
}

function filePorts(
  value: Record<string, LibraryArtifact> | LibraryArtifact[] | undefined,
): [string, LibraryArtifact][] {
  return !value
    ? []
    : Array.isArray(value)
      ? value.map((artifact) => [String(artifact.metadata?.output_port || artifact.id), artifact])
      : Object.entries(value);
}

function WorkflowMapping({
  workflow,
  partId,
  execution,
  onPart,
  onSource,
}: {
  workflow: LibraryWorkflow;
  partId: string;
  execution: LibraryJob | null;
  onPart: (part: LibraryPart) => void;
  onSource: (path: string) => void;
}) {
  const parts = partId ? workflow.subworkflows.filter((part) => part.id === partId) : workflow.subworkflows;
  return (
    <section data-testid="workflow-demo-library-readable-mapping">
      <h3>{workflow.name}</h3>
      <p data-testid="workflow-demo-library-wrapper-origin">
        Steps the factory team designed around the original source
      </p>
      <LibraryParentSteps workflow={workflow} selected={partId} onSelect={onPart} />
      {parts.map((part) => {
        const executablePath =
          part.implementation.type === 'agent' ? part.implementation.prompt_path : part.implementation.source_path;
        const instances =
          execution?.graph?.nodes.filter(
            (node) =>
              node.workflow.id === workflow.id &&
              node.workflow.version === workflow.version &&
              node.subworkflow === part.id,
          ) || [];
        return (
          <section
            className="wl-part-mapping"
            key={part.id}
            data-testid="workflow-demo-library-part-mapping"
            data-variant={part.id}
          >
            <h4>{part.name}</h4>
            <dl className="wd-lineage">
              <dt data-testid="workflow-demo-library-mapping-runner-label">Runs as</dt>
              <dd>
                {part.implementation.type === 'agent'
                  ? 'Agent with Markdown instructions'
                  : part.implementation.type === 'python'
                    ? 'Python code'
                    : part.implementation.type}
              </dd>
              <dt data-testid="workflow-demo-library-mapping-entry-label">Entry</dt>
              <dd>
                {typeof executablePath === 'string' && (
                  <button
                    type="button"
                    className="wl-file-open"
                    onClick={() => onSource(executablePath)}
                    data-testid="workflow-demo-library-mapping-open-entry"
                    data-variant={part.id}
                  >
                    {part.implementation.type === 'agent' ? 'Open instructions' : 'Open Python code'}
                  </button>
                )}
              </dd>
            </dl>
            <h4 data-testid="workflow-demo-library-mapping-source-label">Original source</h4>
            <div className="wl-source-links">
              {sourceSymbols(part.source_evidence).map((source) => (
                <button
                  key={`${source.path}:${source.symbol || ''}`}
                  onClick={() => onSource(source.path)}
                  data-testid="workflow-demo-library-mapping-source"
                  data-variant={`${part.id}/${source.path}`}
                >
                  {source.symbol || source.path}
                  {source.symbol ? ` · ${source.path}` : ''}
                  {source.line ? `:${source.line}` : ''}
                </button>
              ))}
            </div>
            <div className="wl-port-mapping">
              <section>
                <h4 data-testid="workflow-demo-library-mapping-input-label">Input ports</h4>
                <ul>
                  {Object.entries(part.inputs).map(([name, port]) => (
                    <li key={name}>
                      {name}: {port.semantic_type}
                    </li>
                  ))}
                </ul>
              </section>
              <section>
                <h4 data-testid="workflow-demo-library-mapping-output-label">Output ports</h4>
                <ul>
                  {Object.entries(part.outputs).map(([name, port]) => (
                    <li key={name}>
                      {name}: {port.semantic_type}
                    </li>
                  ))}
                </ul>
              </section>
            </div>
            {instances.map((instance) => {
              const state = stateOf(execution, instance.id);
              const attempt = state?.attempts?.[state.attempts.length - 1];
              return (
                <section
                  key={instance.id}
                  data-testid="workflow-demo-library-recorded-file-chain"
                  data-variant={instance.id}
                >
                  <h4 data-testid="workflow-demo-library-recorded-files-title">Recorded file handoffs</h4>
                  <dl className="wd-lineage">
                    {filePorts(attempt?.inputs || state?.inputs).map(([port, artifact]) => (
                      <div className="wl-file-handoff" key={`in:${port}`}>
                        <dt>
                          {port} → {part.name}
                        </dt>
                        <dd>
                          <code>{artifact.path}</code>
                        </dd>
                      </div>
                    ))}
                    {filePorts(attempt?.outputs || state?.outputs).map(([port, artifact]) => {
                      const consumers =
                        execution?.graph?.nodes.flatMap((node) =>
                          Object.entries(node.bindings || {})
                            .filter(([, binding]) => binding.node === instance.id && binding.port === port)
                            .map(([input]) => ({ node, input })),
                        ) || [];
                      return (
                        <div className="wl-file-handoff" key={`out:${port}`}>
                          <dt>
                            {part.name} → {port}
                          </dt>
                          <dd>
                            <code>{artifact.path}</code>
                            {consumers.map(({ node, input }) => (
                              <span className="wl-consumer-file" key={`${node.id}:${input}`}>
                                → {node.name || node.subworkflow}.{input}
                              </span>
                            ))}
                          </dd>
                        </div>
                      );
                    })}
                  </dl>
                </section>
              );
            })}
          </section>
        );
      })}
    </section>
  );
}

function stateOf(job: LibraryJob | null, id: string): LibraryNodeState | undefined {
  const nodes = job?.nodes;
  return Array.isArray(nodes) ? nodes.find((node) => node.id === id) : nodes?.[id];
}
function evidencePaths(value: unknown): string[] {
  const paths = new Set<string>();
  const visit = (item: unknown, key = '') => {
    if (
      typeof item === 'string' &&
      /(?:path|file|source)/i.test(key) &&
      /\.(?:cu|cuh|cc|cpp|c|h|hpp|py|md|txt)$/.test(item)
    )
      paths.add(item);
    else if (Array.isArray(item)) item.forEach((child) => visit(child, key));
    else if (item && typeof item === 'object')
      Object.entries(item).forEach(([name, child]) => {
        if (name !== 'absolute_path' || !('path' in item)) visit(child, name);
      });
  };
  visit(value);
  return [...paths];
}
function graphEdges(graph: LibraryGraph) {
  if (graph.edges) return graph.edges.map((edge) => ({ ...edge, label: edge.data || edge.output || edge.input || '' }));
  return graph.nodes.flatMap((node) =>
    Object.entries(node.bindings || {})
      .filter(([, binding]) => binding.node !== '$input')
      .map(([port, binding]) => ({
        from: binding.node,
        to: node.id,
        input: port,
        output: binding.port,
        label: binding.port || port,
      })),
  );
}

function TaskGraph({
  graph,
  execution,
  workflows,
  selected,
  onSelect,
  showStatus = true,
}: {
  graph: LibraryGraph;
  execution: LibraryJob | null;
  workflows: LibraryWorkflow[];
  selected: string;
  onSelect: (node: LibraryGraphNode) => void;
  showStatus?: boolean;
}) {
  const layout = useMemo(() => {
    const edges = graphEdges(graph);
    const rank = new Map(graph.nodes.map((node) => [node.id, 0]));
    for (let index = 0; index < graph.nodes.length; index += 1) {
      let changed = false;
      for (const edge of edges) {
        if (!rank.has(edge.from) || !rank.has(edge.to)) continue;
        const next = Math.min(graph.nodes.length - 1, (rank.get(edge.from) || 0) + 1);
        if (next > (rank.get(edge.to) || 0)) {
          rank.set(edge.to, next);
          changed = true;
        }
      }
      if (!changed) break;
    }
    const columns = new Map<number, number>();
    const positions = new Map(
      graph.nodes.map((node) => {
        const column = rank.get(node.id) || 0;
        const row = columns.get(column) || 0;
        columns.set(column, row + 1);
        return [node.id, { x: 24 + column * 240, y: 28 + row * 116 }];
      }),
    );
    return {
      edges,
      positions,
      width: Math.max(320, (Math.max(0, ...rank.values()) + 1) * 240 + 24),
      height: Math.max(220, Math.max(1, ...columns.values()) * 116 + 36),
    };
  }, [graph]);
  return (
    <div className="wl-graph-scroll" data-testid="workflow-demo-library-graph">
      <svg
        className="wl-graph"
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        style={{ minWidth: layout.width, minHeight: layout.height }}
        aria-label="Composed task graph"
        data-testid="workflow-demo-library-graph-canvas"
      >
        <defs>
          <marker id="workflow-library-arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <path d="M 0 0 L 6 3 L 0 6 Z" fill="currentColor" />
          </marker>
        </defs>
        {layout.edges.map((edge) => {
          const from = layout.positions.get(edge.from),
            to = layout.positions.get(edge.to);
          if (!from || !to) return null;
          const sx = from.x + 184,
            ex = to.x,
            sy = from.y + 29,
            ey = to.y + 29;
          const receipt = execution?.edges?.find(
            (item) => item.from === edge.from && item.to === edge.to && (!item.data || item.data === edge.label),
          );
          const status = receipt?.status || 'pending';
          const targetNode = graph.nodes.find((node) => node.id === edge.to);
          const inputPort =
            edge.input ||
            Object.entries(targetNode?.bindings || {}).find(
              ([, binding]) => binding.node === edge.from && (!edge.output || binding.port === edge.output),
            )?.[0];
          const targetState = stateOf(execution, edge.to);
          const targetAttempt = targetState?.attempts?.[targetState.attempts.length - 1];
          const received = inputPort
            ? targetAttempt?.inputs?.[inputPort] ||
              (!Array.isArray(targetState?.inputs) ? targetState?.inputs?.[inputPort] : undefined)
            : undefined;
          const targetWorkflow = workflows.find(
            (item) => item.id === targetNode?.workflow.id && item.version === targetNode?.workflow.version,
          );
          const targetPart = targetWorkflow?.subworkflows.find((item) => item.id === targetNode?.subworkflow);
          const expected = targetPart?.inspection?.inputs?.find((item) => item.name === inputPort)?.expected_filename;
          const label = received ? received.path.split(/[\\/]/).pop() : expected || edge.output || edge.label;
          return (
            <g
              className="wd-edge"
              key={`${edge.from}:${edge.to}:${edge.label}`}
              data-variant={statusColor(status)}
              data-testid="workflow-demo-library-graph-edge"
              data-from={edge.from}
              data-to={edge.to}
            >
              <path
                d={`M ${sx} ${sy} C ${sx + 28} ${sy}, ${ex - 28} ${ey}, ${ex} ${ey}`}
                fill="none"
                stroke="currentColor"
                strokeWidth="1"
                markerEnd="url(#workflow-library-arrow)"
                strokeDasharray={!showStatus || status === 'verified' || status === 'completed' ? undefined : '4 4'}
              />
              <text x={(sx + ex) / 2} y={Math.min(from.y, to.y) - 8} textAnchor="middle" className="wd-edge-label">
                {label}
              </text>
            </g>
          );
        })}
        {graph.nodes.map((node) => {
          const point = layout.positions.get(node.id)!;
          const workflow = workflows.find(
            (item) => item.id === node.workflow.id && item.version === node.workflow.version,
          );
          const part = workflow?.subworkflows.find((item) => item.id === node.subworkflow);
          return (
            <foreignObject x={point.x} y={point.y} width="184" height="58" key={node.id}>
              <button
                className="wd-node"
                aria-pressed={selected === node.id}
                onClick={() => onSelect(node)}
                data-testid="workflow-demo-library-graph-node"
                data-variant={node.id}
              >
                <span>{part?.name || node.name || node.subworkflow}</span>
                {showStatus && <Dot status={stateOf(execution, node.id)?.status || 'pending'} />}
              </button>
            </foreignObject>
          );
        })}
      </svg>
    </div>
  );
}

export function WorkflowLibraryDemo() {
  const [workflows, setWorkflows] = useState<LibraryWorkflow[]>([]);
  const [repositories, setRepositories] = useState([
    'https://github.com/niko1221/strata',
    'https://github.com/google/googletest',
  ]);
  const [revisions, setRevisions] = useState(['', '']);
  const [imports, setImports] = useState<Record<string, LibraryJob>>({});
  const [importHistory, setImportHistory] = useState<LibraryJob[]>([]);
  const [importTrace, setImportTrace] = useState<LibraryJob | null>(null);
  const [checkSummaries, setCheckSummaries] = useState<LibraryCheckSummary[]>([]);
  const [component, setComponent] = useState<LibraryCheck | null>(null);
  const [modelAttempt, setModelAttempt] = useState<LibraryModelAttempt | null>(null);
  const [pairedDiffs, setPairedDiffs] = useState<CodeDiffFile[]>([]);
  const [checkCache, setCheckCache] = useState<Record<string, LibraryCheck>>({});
  const [poolTab, setPoolTab] = useState<'library' | 'imports' | 'checks'>('library');
  const [importing, setImporting] = useState<number[]>([]);
  const [task, setTask] = useState(initialTask),
    [policy, setPolicy] = useState(''),
    [policyHash, setPolicyHash] = useState('');
  const [planner, setPlanner] = useState<'contract' | 'agent'>('contract');
  const [plan, setPlan] = useState<LibraryJob | null>(null),
    [execution, setExecution] = useState<LibraryJob | null>(null);
  const [submitting, setSubmitting] = useState(false),
    [editor, setEditor] = useState<EditorTab>('task'),
    [inspector, setInspector] = useState<InspectorTab>('mapping');
  const [selectedWorkflow, setSelectedWorkflow] = useState(''),
    [selectedPart, setSelectedPart] = useState(''),
    [selectedNode, setSelectedNode] = useState('');
  const [events, setEvents] = useState<ObservedEvent[]>([]),
    [source, setSource] = useState<LibrarySource | null>(null),
    [sourcePath, setSourcePath] = useState('');
  const [generated, setGenerated] = useState<LibrarySource | null>(null),
    [error, setError] = useState('');
  const [projectSource, setProjectSource] = useState<{
    artifact: LibraryArtifact;
    files: Record<string, string>;
  } | null>(null);
  const inspectorScroll = useRef<HTMLDivElement | null>(null);
  const streams = useRef(new Map<string, AbortController>()),
    seenEvents = useRef(new Set<string>()),
    mounted = useRef(true);
  const sourceRequest = useRef<AbortController | null>(null),
    generatedRequest = useRef<AbortController | null>(null);
  const inspectWorkflows = [
    ...workflows,
    ...(importTrace?.workflow &&
    !workflows.some((item) => item.id === importTrace.workflow?.id && item.version === importTrace.workflow?.version)
      ? [importTrace.workflow]
      : []),
    ...(component?.workflow_definitions || []).filter(
      (entry) => !workflows.some((item) => item.id === entry.id && item.version === entry.version),
    ),
  ];
  const canonicalTask = useMemo(() => parseTask(task), [task]);
  const taskSource =
    canonicalTask?.source && typeof canonicalTask.source === 'object'
      ? (canonicalTask.source as Record<string, unknown>)
      : {};
  const displayExecution = component?.run || execution;
  const workflow = inspectWorkflows.find((item) => `${item.id}@${item.version}` === selectedWorkflow);
  const part = workflow?.subworkflows.find((item) => item.id === selectedPart);
  const graph = component ? component.run.graph : execution?.graph || plan?.graph;
  const node = graph?.nodes.find((item) => item.id === selectedNode),
    nodeState = stateOf(displayExecution, selectedNode);
  const artifacts = (
    displayExecution?.artifacts
      ? Array.isArray(displayExecution.artifacts)
        ? [...displayExecution.artifacts]
        : Object.values(displayExecution.artifacts)
      : []
  ).sort((left, right) => {
    const priority = (kind: string) =>
      ['source.project', 'source.cpp', 'delivery.source_zip'].includes(kind)
        ? ['source.project', 'source.cpp', 'delivery.source_zip'].indexOf(kind)
        : 3;
    return priority(left.kind) - priority(right.kind);
  });
  const comparedSource = component?.verification?.cpp as LibraryArtifact | undefined;
  const checkedCpp =
    comparedSource &&
    artifacts.find(
      (artifact) =>
        artifact.kind === 'source.cpp' &&
        artifact.id === comparedSource.id &&
        artifact.sha256 === comparedSource.sha256,
    );
  const checkedProject =
    checkedCpp &&
    artifacts.find((artifact) => artifact.kind === 'source.project' && artifact.producer === checkedCpp.producer);
  const selectedRefs = new Set(
    (graph?.nodes || []).map((item) => `${item.workflow.id}@${item.workflow.version}/${item.subworkflow}`),
  );

  const loadLibrary = useCallback(async (signal?: AbortSignal) => {
    const result = await libraryClient.list(signal);
    if (!signal?.aborted && mounted.current) setWorkflows(result.workflows);
  }, []);
  const loadHistory = useCallback(async (signal?: AbortSignal) => {
    const value = await libraryClient.imports(signal);
    if (!signal?.aborted && mounted.current) setImportHistory(value.jobs);
  }, []);
  const applyCheck = useCallback((value: LibraryCheck) => {
    sourceRequest.current?.abort();
    generatedRequest.current?.abort();
    setComponent(value);
    setImportTrace(null);
    setSelectedNode('');
    setSelectedPart('');
    setSelectedWorkflow('');
    setGenerated(null);
    setPairedDiffs([]);
    setProjectSource(null);
    setSource(null);
    setInspector('artifacts');
  }, []);
  const updateTask = (fields: Record<string, unknown>) => {
    if (canonicalTask) setTask(JSON.stringify({ ...canonicalTask, ...fields }, null, 2));
  };
  const updateTaskSource = (field: string, value: string) => updateTask({ source: { ...taskSource, [field]: value } });
  const receiveEvents = useCallback((kind: LibraryJobKind, id: string, incoming: LibraryEvent[]) => {
    const added: ObservedEvent[] = [];
    for (const event of incoming) {
      const key = `${kind}:${id}:${event.sequence}`;
      if (!seenEvents.current.has(key)) {
        seenEvents.current.add(key);
        added.push({ key, jobId: id, event });
      }
    }
    if (added.length && mounted.current)
      setEvents((previous) =>
        [...previous, ...added].sort((left, right) => {
          if (left.jobId === right.jobId) return left.event.sequence - right.event.sequence;
          return (left.event.time || left.event.timestamp || '').localeCompare(
            right.event.time || right.event.timestamp || '',
          );
        }),
      );
  }, []);
  const watch = useCallback(
    async (kind: LibraryJobKind, first: LibraryJob, update: (value: LibraryJob) => void) => {
      const key = `${kind}:${first.id}`;
      streams.current.get(key)?.abort();
      const controller = new AbortController();
      streams.current.set(key, controller);
      const accept = (value: LibraryJob) => {
        if (!controller.signal.aborted && mounted.current) {
          update(value);
          receiveEvents(kind, value.id, value.events || []);
        }
      };
      accept(first);
      let refreshing = false,
        refreshAgain = false;
      const refresh = async (): Promise<void> => {
        if (refreshing) {
          refreshAgain = true;
          return;
        }
        refreshing = true;
        try {
          do {
            refreshAgain = false;
            accept(await libraryClient.job(kind, first.id, controller.signal));
          } while (refreshAgain && !controller.signal.aborted);
        } finally {
          refreshing = false;
        }
      };
      try {
        if (!libraryTerminal(first.status)) {
          await libraryClient.stream(
            kind,
            first.id,
            Math.max(0, ...(first.events || []).map((event) => event.sequence)),
            (event) => {
              receiveEvents(kind, first.id, [event]);
              void refresh().catch((reason: unknown) => {
                if (!controller.signal.aborted && mounted.current) setError(String(reason));
              });
            },
            controller.signal,
          );
          await refresh();
        }
        if (kind === 'imports') await Promise.all([loadLibrary(controller.signal), loadHistory(controller.signal)]);
      } catch (reason) {
        if (!controller.signal.aborted && mounted.current) setError(String(reason));
      } finally {
        if (streams.current.get(key) === controller) streams.current.delete(key);
      }
    },
    [loadLibrary, loadHistory, receiveEvents],
  );

  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    let restoredPolicy = false;
    void Promise.all([
      loadLibrary(controller.signal),
      loadHistory(controller.signal),
      libraryClient.modelConnection(controller.signal).then((value) => {
        if (!controller.signal.aborted) setModelAttempt(value.attempt);
      }),
      libraryClient.checks(controller.signal).then(async (value) => {
        if (controller.signal.aborted) return;
        setCheckSummaries(value.checks);
        const details = await Promise.all(
          value.checks.map((entry) => libraryClient.check(entry.id, controller.signal)),
        );
        if (!controller.signal.aborted) setCheckCache(Object.fromEntries(details.map((entry) => [entry.id, entry])));
      }),
      libraryClient.policy(controller.signal).then((value) => {
        if (!controller.signal.aborted && !restoredPolicy) {
          setPolicy(value.content);
          setPolicyHash(value.sha256);
        }
      }),
      (async () => {
        const query = new URLSearchParams(window.location.search);
        const executionId = query.get('libraryExecution');
        let planId = query.get('libraryPlan');
        if (executionId) {
          const value = await libraryClient.job('executions', executionId, controller.signal);
          if (controller.signal.aborted) return;
          setExecution(value);
          receiveEvents('executions', value.id, value.events || []);
          const request = value.request as { plan_id?: string } | undefined;
          planId = planId || request?.plan_id || null;
          setInspector('execution');
          if (!libraryTerminal(value.status)) void watch('executions', value, setExecution);
        }
        if (planId) {
          const value = await libraryClient.job('plans', planId, controller.signal);
          if (controller.signal.aborted) return;
          setPlan(value);
          receiveEvents('plans', value.id, value.events || []);
          const request = value.request as { task?: Record<string, unknown>; policy?: string } | undefined;
          if (request?.task) setTask(JSON.stringify(request.task, null, 2));
          if (request?.policy) {
            restoredPolicy = true;
            setPolicy(request.policy);
            setPolicyHash(value.graph?.policy_ref?.sha256 || '');
          }
          setEditor('decisions');
          if (!libraryTerminal(value.status)) void watch('plans', value, setPlan);
        }
        const checkId = query.get('libraryCheck');
        if (checkId) {
          const value = await libraryClient.check(checkId, controller.signal);
          if (!controller.signal.aborted) {
            applyCheck(value);
            const selected = value.run.graph?.nodes.find((node) => node.id === query.get('libraryNode'));
            if (selected) {
              setSelectedNode(selected.id);
              setSelectedWorkflow(`${selected.workflow.id}@${selected.workflow.version}`);
              setSelectedPart(selected.subworkflow);
              setInspector('execution');
            }
          }
        }
        const importId = query.get('libraryImport');
        if (importId) {
          const value = await libraryClient.job('imports', importId, controller.signal);
          if (!controller.signal.aborted) {
            setImportTrace(value);
            setInspector('execution');
            setPoolTab('imports');
          }
        }
      })(),
    ]).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(String(reason));
    });
    return () => {
      mounted.current = false;
      controller.abort();
      streams.current.forEach((stream) => stream.abort());
      streams.current.clear();
      sourceRequest.current?.abort();
      generatedRequest.current?.abort();
    };
  }, [loadLibrary, loadHistory, receiveEvents, watch, applyCheck]);

  const importProject = async (index: number) => {
    setError('');
    setImporting((previous) => [...previous, index]);
    setInspector('execution');
    setImportTrace(null);
    try {
      const result = await libraryClient.import(repositories[index], revisions[index]);
      await watch('imports', result, (value) => setImports((previous) => ({ ...previous, [String(index)]: value })));
    } catch (reason) {
      if (mounted.current) setError(String(reason));
    } finally {
      if (mounted.current) setImporting((previous) => previous.filter((item) => item !== index));
    }
  };
  const createPlan = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    setInspector('execution');
    try {
      const parsed: unknown = JSON.parse(task);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed))
        throw new Error('Task Contract must be an object.');
      const result = await libraryClient.plan(parsed as Record<string, unknown>, policy, execution?.id, planner);
      rememberJob('plan', result.id);
      setComponent(null);
      setImportTrace(null);
      generatedRequest.current?.abort();
      setGenerated(null);
      setPairedDiffs([]);
      setProjectSource(null);
      setExecution(null);
      setSelectedNode('');
      await watch('plans', result, setPlan);
      if (mounted.current) setEditor('decisions');
    } catch (reason) {
      if (mounted.current) setError(String(reason));
    } finally {
      if (mounted.current) setSubmitting(false);
    }
  };
  const execute = async () => {
    if (!plan) return;
    setError('');
    setSubmitting(true);
    setInspector('execution');
    try {
      const result = await libraryClient.execute(plan.id);
      rememberJob('execution', result.id);
      await watch('executions', result, setExecution);
    } catch (reason) {
      if (mounted.current) setError(String(reason));
    } finally {
      if (mounted.current) setSubmitting(false);
    }
  };
  const selectPart = (parent: LibraryWorkflow, child?: LibraryPart, preserveContext = false) => {
    sourceRequest.current?.abort();
    setSelectedWorkflow(`${parent.id}@${parent.version}`);
    setSelectedPart(child?.id || '');
    setSelectedNode('');
    setSource(null);
    if (!preserveContext) {
      setImportTrace(null);
      setComponent(null);
      const url = new URL(window.location.href);
      url.searchParams.delete('libraryImport');
      url.searchParams.delete('libraryCheck');
      url.searchParams.delete('libraryNode');
      window.history.replaceState(null, '', url);
    }
    setInspector('mapping');
  };
  const selectNode = (item: LibraryGraphNode) => {
    setSelectedNode(item.id);
    setImportTrace(null);
    setSelectedWorkflow(`${item.workflow.id}@${item.workflow.version}`);
    setSelectedPart(item.subworkflow);
    setInspector('execution');
  };
  const openSource = async (path: string, from = workflow) => {
    if (!from) return;
    sourceRequest.current?.abort();
    const controller = new AbortController();
    sourceRequest.current = controller;
    setError('');
    setSourcePath(path);
    setSource(null);
    setInspector('source');
    try {
      const result = await libraryClient.source(from, path, controller.signal);
      if (!controller.signal.aborted) setSource(result);
    } catch (reason) {
      if (!controller.signal.aborted) setError(String(reason));
    }
  };
  const readProjectFiles = (content: string): Record<string, string> => {
    const manifest: unknown = JSON.parse(content);
    const files = manifest && typeof manifest === 'object' ? (manifest as { files?: unknown }).files : null;
    if (
      !files ||
      typeof files !== 'object' ||
      Array.isArray(files) ||
      !Object.keys(files).length ||
      !Object.entries(files).every(([path, sha]) => path && typeof sha === 'string' && /^[a-f0-9]{64}$/.test(sha))
    )
      throw new Error('Source project manifest has no valid file map.');
    return files as Record<string, string>;
  };
  const loadSourceMapping = async (
    project: { artifact: LibraryArtifact; files: Record<string, string> },
    path: string,
    content: string,
    controller: AbortController,
  ) => {
    setPairedDiffs([]);
    if (!project.files['code_diff.json']) return;
    const response = component
      ? await libraryClient.checkProjectFile(component.id, project.artifact.id, 'code_diff.json', controller.signal)
      : await libraryClient.projectFile(execution!.id, project.artifact.id, 'code_diff.json', controller.signal);
    const mapping = parseCodeDiff(await response.text());
    const normalized = path.replaceAll('\\', '/');
    const matches = mapping.files.filter(
      (entry) => entry.generated_path.replaceAll('\\', '/') === normalized && content.includes(entry.generated_code),
    );
    if (!controller.signal.aborted) setPairedDiffs(matches);
  };
  const openArtifact = async (artifact: LibraryArtifact, download: boolean) => {
    if (!displayExecution) return;
    setError('');
    generatedRequest.current?.abort();
    const controller = new AbortController();
    generatedRequest.current = controller;
    try {
      const response = component
        ? await libraryClient.checkArtifact(component.id, artifact.id, controller.signal)
        : await libraryClient.artifact(execution!.id, artifact.id, controller.signal);
      if (download || /\.(?:zip|gz|tar|so|a|bin)$/i.test(artifact.path)) {
        const url = URL.createObjectURL(await response.blob()),
          link = document.createElement('a');
        link.href = url;
        link.download = artifact.path.split(/[\\/]/).pop() || artifact.id;
        link.click();
        URL.revokeObjectURL(url);
      } else {
        const content = await response.text();
        if (!controller.signal.aborted) {
          if (artifact.kind === 'source.project') {
            setProjectSource({ artifact, files: readProjectFiles(content) });
            setGenerated(null);
            setPairedDiffs([]);
          } else {
            setProjectSource(null);
            setPairedDiffs([]);
            setGenerated({ path: artifact.path, sha256: artifact.sha256, content });
            if (artifact.kind === 'source.cpp') {
              const owner = artifacts.find(
                (entry) => entry.kind === 'source.project' && entry.producer === artifact.producer,
              );
              if (owner) {
                const manifestResponse = component
                  ? await libraryClient.checkArtifact(component.id, owner.id, controller.signal)
                  : await libraryClient.artifact(execution!.id, owner.id, controller.signal);
                const files = readProjectFiles(await manifestResponse.text());
                const member = Object.keys(files).find(
                  (path) =>
                    files[path] === artifact.sha256 && path.split(/[\\/]/).pop() === artifact.path.split(/[\\/]/).pop(),
                );
                if (member && !controller.signal.aborted) {
                  const project = { artifact: owner, files };
                  setProjectSource(project);
                  setGenerated({ path: member, sha256: artifact.sha256, content });
                  await loadSourceMapping(project, member, content, controller);
                }
              }
            }
          }
          setInspector('artifacts');
          inspectorScroll.current?.scrollTo({ top: 0 });
        }
      }
    } catch (reason) {
      if (!controller.signal.aborted) setError(String(reason));
    }
  };
  const openProjectFile = async (path: string, project = projectSource) => {
    if (!displayExecution || !project?.files[path]) return;
    setError('');
    generatedRequest.current?.abort();
    const controller = new AbortController();
    generatedRequest.current = controller;
    setGenerated(null);
    setPairedDiffs([]);
    try {
      const response = component
        ? await libraryClient.checkProjectFile(component.id, project.artifact.id, path, controller.signal)
        : await libraryClient.projectFile(execution!.id, project.artifact.id, path, controller.signal);
      const content = await response.text();
      if (!controller.signal.aborted) {
        setGenerated({ path, sha256: project.files[path], content });
        if (/\.(?:cpp|cc|cxx)$/i.test(path)) await loadSourceMapping(project, path, content, controller);
        setInspector('artifacts');
        inspectorScroll.current?.scrollTo({ top: 0 });
      }
    } catch (reason) {
      if (!controller.signal.aborted) setError(String(reason));
    }
  };
  const openRecordedNumericalTest = async () => {
    if (!component || !checkedProject) return;
    generatedRequest.current?.abort();
    const controller = new AbortController();
    generatedRequest.current = controller;
    setError('');
    try {
      const response = await libraryClient.checkArtifact(component.id, checkedProject.id, controller.signal);
      const project = { artifact: checkedProject, files: readProjectFiles(await response.text()) };
      if (controller.signal.aborted) return;
      const path = 'tests/numerical.cpp';
      if (!project.files[path]) throw new Error('The saved source project has no numerical test file.');
      setProjectSource(project);
      await openProjectFile(path, project);
    } catch (reason) {
      if (!controller.signal.aborted) setError(String(reason));
    }
  };
  const openImport = async (id: string) => {
    setError('');
    setSelectedNode('');
    try {
      const value = await libraryClient.job('imports', id);
      if (!mounted.current) return;
      setImportTrace(value);
      setComponent(null);
      setGenerated(null);
      setPairedDiffs([]);
      setProjectSource(null);
      setInspector('execution');
      const url = new URL(window.location.href);
      url.searchParams.set('libraryImport', id);
      url.searchParams.delete('libraryCheck');
      url.searchParams.delete('libraryNode');
      window.history.replaceState(null, '', url);
    } catch (reason) {
      if (mounted.current) setError(String(reason));
    }
  };
  const openImportMaterial = async (id: string) => {
    if (!importTrace) return;
    sourceRequest.current?.abort();
    const controller = new AbortController();
    sourceRequest.current = controller;
    setSource(null);
    setError('');
    setInspector('source');
    try {
      const value = await libraryClient.importMaterial(importTrace.id, id, controller.signal);
      if (!controller.signal.aborted) {
        setSource(value);
        setSourcePath(value.path);
      }
    } catch (reason) {
      if (!controller.signal.aborted) setError(String(reason));
    }
  };
  const openCheck = async (id: string) => {
    setError('');
    try {
      const value = await libraryClient.check(id);
      if (!mounted.current) return;
      applyCheck(value);
      const url = new URL(window.location.href);
      url.searchParams.set('libraryCheck', id);
      url.searchParams.delete('libraryImport');
      ['recording', 'factoryRecording', 'replay', 'factoryRun'].forEach((key) => url.searchParams.delete(key));
      window.history.replaceState(null, '', url);
    } catch (reason) {
      if (mounted.current) setError(String(reason));
    }
  };
  const returnToPlanner = () => {
    setComponent(null);
    setImportTrace(null);
    setSelectedNode('');
    setGenerated(null);
    setPairedDiffs([]);
    setProjectSource(null);
    setInspector('execution');
    const url = new URL(window.location.href);
    url.searchParams.delete('libraryCheck');
    url.searchParams.delete('libraryNode');
    url.searchParams.delete('libraryImport');
    window.history.replaceState(null, '', url);
  };
  const shownEvents: ObservedEvent[] = importTrace
    ? (importTrace.events || []).map((event) => ({
        key: `imports:${importTrace.id}:${event.sequence}`,
        jobId: importTrace.id,
        event,
      }))
    : component
      ? component.events.map((event) => ({
          key: `checks:${component.id}:${event.sequence}`,
          jobId: component.id,
          event,
        }))
      : events;
  const relevantEvents = selectedNode
    ? shownEvents.filter(
        ({ event }) =>
          event.node_id === selectedNode ||
          event.payload?.node_id === selectedNode ||
          event.payload?.node === selectedNode,
      )
    : shownEvents;
  const paths = evidencePaths(part?.source_evidence || workflow?.source_evidence || workflow?.source);
  const unmet = execution?.unmet_requirements || plan?.unmet_requirements;
  const recordedExample = (parent: LibraryWorkflow, child: LibraryPart) => {
    for (const check of Object.values(checkCache)) {
      for (const candidate of check.run.graph?.nodes || []) {
        if (candidate.workflow.id !== parent.id || candidate.subworkflow !== child.id) continue;
        const exact = candidate.workflow.version === parent.version;
        const original = check.workflow_definitions?.find(
          (entry) => entry.id === candidate.workflow.id && entry.version === candidate.workflow.version,
        );
        const sameSource =
          original?.source.repository === parent.source.repository &&
          original?.source.revision === parent.source.revision;
        if (exact || sameSource) return { check, node: candidate, exact };
      }
    }
    return null;
  };
  const openRecordedExample = (example: NonNullable<ReturnType<typeof recordedExample>>) => {
    applyCheck(example.check);
    setSelectedNode(example.node.id);
    setSelectedWorkflow(`${example.node.workflow.id}@${example.node.workflow.version}`);
    setSelectedPart(example.node.subworkflow);
    setInspector('execution');
    const url = new URL(window.location.href);
    url.searchParams.set('libraryCheck', example.check.id);
    url.searchParams.set('libraryNode', example.node.id);
    url.searchParams.delete('libraryImport');
    ['recording', 'factoryRecording', 'replay', 'factoryRun'].forEach((key) => url.searchParams.delete(key));
    window.history.replaceState(null, '', url);
  };
  const unconsumedFramework =
    component &&
    node &&
    artifacts.some((artifact) => artifact.kind === 'test.framework' && artifact.producer === node.id) &&
    !(graph && graphEdges(graph).some((edge) => edge.from === node.id));

  return (
    <div className="wd-app wl-app" data-testid="workflow-demo-library-view">
      <header className="wd-header">
        <h1 data-testid="workflow-demo-library-title">AI4Research Software Factory</h1>
        <p data-testid="workflow-demo-library-narrative">
          Import projects, compose workflow parts, and execute a task graph that produces source code.
        </p>
      </header>
      {error && (
        <pre className="wd-error wl-error" role="alert" data-testid="workflow-demo-library-error">
          {error}
        </pre>
      )}
      <div className="wl-layout" data-inspector={inspector}>
        <aside className="wd-panel wl-pane" data-testid="workflow-demo-library-pool">
          <div className="wl-pane-heading">
            <h2 data-testid="workflow-demo-library-pool-title">Workflow Library</h2>
          </div>
          <div
            className="wl-tabs"
            role="tablist"
            aria-label="Library records"
            data-testid="workflow-demo-library-record-tabs"
          >
            {(['library', 'imports', 'checks'] as const).map((tab) => (
              <button
                type="button"
                role="tab"
                key={tab}
                aria-selected={poolTab === tab}
                onClick={() => setPoolTab(tab)}
                data-testid="workflow-demo-library-record-tab"
                data-variant={tab}
              >
                {tab === 'library' ? 'Projects & Steps' : tab === 'imports' ? 'Import History' : 'Component Checks'}
              </button>
            ))}
          </div>
          <div className="wl-scroll">
            {poolTab === 'library' && (
              <>
                <section className="wl-section" data-testid="workflow-demo-library-sources">
                  <h3 data-testid="workflow-demo-library-sources-title">Source Projects</h3>
                  {repositories.map((url, index) => (
                    <form
                      key={index}
                      className="wl-import-form"
                      data-testid="workflow-demo-library-import-form"
                      data-variant={index}
                      onSubmit={(event) => {
                        event.preventDefault();
                        void importProject(index);
                      }}
                    >
                      <label
                        htmlFor={`workflow-library-repository-${index}`}
                        data-testid="workflow-demo-library-repository-label"
                        data-variant={index}
                      >
                        Project {index + 1}
                      </label>
                      <input
                        id={`workflow-library-repository-${index}`}
                        type="url"
                        value={url}
                        required
                        onChange={(event) =>
                          setRepositories((previous) =>
                            previous.map((value, item) => (item === index ? event.target.value : value)),
                          )
                        }
                        data-testid="workflow-demo-library-repository"
                        data-variant={index}
                      />
                      <label
                        htmlFor={`workflow-library-revision-${index}`}
                        data-testid="workflow-demo-library-revision-label"
                        data-variant={index}
                      >
                        Revision
                      </label>
                      <input
                        id={`workflow-library-revision-${index}`}
                        value={revisions[index]}
                        onChange={(event) =>
                          setRevisions((previous) =>
                            previous.map((value, item) => (item === index ? event.target.value : value)),
                          )
                        }
                        data-testid="workflow-demo-library-revision"
                        data-variant={index}
                      />
                      <div className="wl-actions">
                        <Button
                          size="sm"
                          type="submit"
                          disabled={importing.includes(index)}
                          data-testid="workflow-demo-library-import"
                          data-variant={index}
                        >
                          Import & register
                        </Button>
                        {imports[String(index)] && <Dot status={imports[String(index)].status} />}
                      </div>
                    </form>
                  ))}
                </section>
                <section className="wl-section" data-testid="workflow-demo-library-workflows">
                  {workflows.map((item) => (
                    <section
                      className="wl-workflow"
                      key={`${item.id}@${item.version}`}
                      data-testid="workflow-demo-library-workflow"
                      data-variant={item.id}
                    >
                      <button
                        className="wl-workflow-name"
                        onClick={() => selectPart(item)}
                        aria-pressed={selectedWorkflow === `${item.id}@${item.version}` && !selectedPart}
                        data-testid="workflow-demo-library-workflow-select"
                        data-variant={item.id}
                      >
                        {item.name}
                      </button>
                      <div className="wl-parts">
                        {item.subworkflows.map((child) => {
                          const example = recordedExample(item, child);
                          return (
                            <div className="wl-pool-step" key={child.id}>
                              <button
                                className="wd-pool-card"
                                key={child.id}
                                onClick={() => selectPart(item, child)}
                                aria-pressed={
                                  selectedWorkflow === `${item.id}@${item.version}` && selectedPart === child.id
                                }
                                data-selection={
                                  selectedRefs.has(`${item.id}@${item.version}/${child.id}`) ? 'selected' : 'idle'
                                }
                                data-testid="workflow-demo-library-part"
                                data-variant={`${item.id}/${child.id}`}
                              >
                                {child.name}
                              </button>

                              {example && (
                                <button
                                  type="button"
                                  className="wl-record-example"
                                  onClick={() => openRecordedExample(example)}
                                  data-testid="workflow-demo-library-open-recorded-example"
                                  data-variant={`${item.id}/${child.id}`}
                                >
                                  {example.exact
                                    ? 'Open recorded example'
                                    : 'Open earlier definition’s recorded example'}
                                </button>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </section>
                  ))}
                </section>
              </>
            )}
            {poolTab === 'imports' && (
              <section data-testid="workflow-demo-library-import-history">
                <h3 data-testid="workflow-demo-library-import-history-title">Saved Source Registrations</h3>
                {importHistory.map((job) => (
                  <button
                    type="button"
                    className="wl-history-record"
                    key={job.id}
                    onClick={() => void openImport(job.id)}
                    aria-pressed={importTrace?.id === job.id}
                    data-testid="workflow-demo-library-import-record"
                    data-variant={job.id}
                  >
                    <strong>{job.workflow?.name || String(job.request?.repository_url || job.id)}</strong>
                    <span>{job.workflow?.source.revision || job.created_at}</span>
                    <Dot status={job.status} />
                  </button>
                ))}
              </section>
            )}
            {poolTab === 'checks' && (
              <section data-testid="workflow-demo-library-component-checks">
                <h3 data-testid="workflow-demo-library-component-checks-title">Component Verification</h3>
                {checkSummaries.map((check) => (
                  <button
                    type="button"
                    className="wl-history-record"
                    key={check.id}
                    onClick={() => void openCheck(check.id)}
                    aria-pressed={component?.id === check.id}
                    data-testid="workflow-demo-library-component-check"
                    data-variant={check.id}
                  >
                    <strong data-testid="workflow-demo-library-check-origin">Manually assembled check</strong>
                    <span>{check.id}</span>
                    <Dot status={check.status} />
                  </button>
                ))}
              </section>
            )}
          </div>
        </aside>
        <main className="wd-panel wl-pane" data-testid="workflow-demo-library-composer">
          {!component && !importTrace && (
            <form
              className="wl-composer"
              onSubmit={(event) => void createPlan(event)}
              data-testid="workflow-demo-library-plan-form"
            >
              <div className="wl-pane-heading">
                <h2 data-testid="workflow-demo-library-composer-title">Planner</h2>
                {plan && <Dot status={plan.status} />}
                <select
                  aria-label="Planning method"
                  value={planner}
                  onChange={(event) => setPlanner(event.target.value === 'agent' ? 'agent' : 'contract')}
                  data-testid="workflow-demo-library-planning-method"
                >
                  <option value="contract">Match required outputs</option>
                  <option value="agent">Agent planning</option>
                </select>
                <Button
                  size="sm"
                  variant="primary"
                  type="submit"
                  disabled={submitting || (planner === 'agent' && !policy) || !workflows.length || !canonicalTask}
                  data-testid="workflow-demo-library-plan"
                >
                  Choose steps
                </Button>
                <Button
                  size="sm"
                  disabled={submitting || !plan?.graph || !['completed', 'verified'].includes(plan.status)}
                  onClick={() => void execute()}
                  data-testid="workflow-demo-library-execute"
                >
                  Execute
                </Button>
              </div>
              {planner === 'agent' && modelAttempt && modelAttempt.outcome === 'failed' && (
                <section className="wl-model-attempt" data-testid="workflow-demo-library-last-model-attempt">
                  <strong data-testid="workflow-demo-library-last-model-attempt-title">
                    Last recorded model connection attempt failed
                  </strong>
                  <span>
                    {modelAttempt.reason_code === 'authentication_failed'
                      ? 'Authentication failed'
                      : modelAttempt.reason_code.replaceAll('_', ' ')}{' '}
                    · {modelAttempt.observed_http_statuses.join(', ')} · {modelAttempt.recorded_at}
                  </span>
                </section>
              )}
              <div
                className="wl-tabs"
                role="tablist"
                aria-label="Planner inputs and decisions"
                data-testid="workflow-demo-library-editor-tabs"
              >
                {(['task', 'contract', 'policy', 'decisions'] as const).map((tab) => (
                  <button
                    type="button"
                    role="tab"
                    key={tab}
                    aria-selected={editor === tab}
                    onClick={() => setEditor(tab)}
                    data-testid="workflow-demo-library-editor-tab"
                    data-variant={tab}
                  >
                    {tab === 'task'
                      ? 'Request'
                      : tab === 'contract'
                        ? 'Task Contract'
                        : tab === 'policy'
                          ? 'Composer Policy'
                          : 'Selection Decisions'}
                  </button>
                ))}
              </div>
              {editor === 'task' && (
                <section className="wl-human-task" data-testid="workflow-demo-library-request">
                  <label htmlFor="workflow-library-request" data-testid="workflow-demo-library-request-label">
                    What should the factory produce?
                  </label>
                  <textarea
                    id="workflow-library-request"
                    value={String(canonicalTask?.description || '')}
                    disabled={!canonicalTask}
                    onChange={(event) => updateTask({ description: event.target.value })}
                    className="wl-request-input"
                    data-testid="workflow-demo-library-request-input"
                  />
                  <div className="wl-human-source">
                    <label htmlFor="workflow-library-task-source" data-testid="workflow-demo-library-task-source-label">
                      Build from this source
                    </label>
                    <input
                      id="workflow-library-task-source"
                      value={String(taskSource.repository || '')}
                      disabled={!canonicalTask}
                      onChange={(event) => updateTaskSource('repository', event.target.value)}
                      data-testid="workflow-demo-library-task-source"
                    />
                    <label
                      htmlFor="workflow-library-task-revision"
                      data-testid="workflow-demo-library-task-revision-label"
                    >
                      Fixed source version
                    </label>
                    <input
                      id="workflow-library-task-revision"
                      value={String(taskSource.revision || '')}
                      disabled={!canonicalTask}
                      onChange={(event) => updateTaskSource('revision', event.target.value)}
                      data-testid="workflow-demo-library-task-revision"
                    />
                  </div>
                  <dl className="wd-lineage">
                    <dt data-testid="workflow-demo-library-task-target-label">Target</dt>
                    <dd data-testid="workflow-demo-library-task-target">
                      {canonicalTask?.target_backend === 'ascend'
                        ? 'Huawei Ascend Native'
                        : String(canonicalTask?.target_backend || '')}
                    </dd>
                    <dt data-testid="workflow-demo-library-task-deliverables-label">Requested outputs</dt>
                    <dd data-testid="workflow-demo-library-task-deliverables">
                      {Array.isArray(canonicalTask?.required_outputs) &&
                        canonicalTask.required_outputs
                          .map(
                            (value) =>
                              ({
                                'source.cpp': 'C++ source files under src/',
                                'verification.report': 'Numerical comparison results',
                                'delivery.source_zip': 'Buildable source ZIP',
                              })[String(value)] || String(value),
                          )
                          .join(' · ')}
                    </dd>
                    <dt data-testid="workflow-demo-library-task-acceptance-label">Must verify</dt>
                    <dd data-testid="workflow-demo-library-task-acceptance">
                      {canonicalTask?.acceptance && typeof canonicalTask.acceptance === 'object'
                        ? Object.entries(canonicalTask.acceptance).map(([key, value]) => (
                            <span className="wl-task-requirement" key={key}>
                              {{
                                'native_compile': 'Native compilation',
                                'native_model_inference': 'Model inference',
                                'compare_original': 'Comparison with original',
                              }[key] || key}
                              : {value === true ? 'required' : value === false ? 'not requested' : String(value)}
                            </span>
                          ))
                        : ''}
                    </dd>
                  </dl>
                </section>
              )}
              {editor === 'contract' && (
                <textarea
                  aria-label="Task Contract"
                  value={task}
                  onChange={(event) => setTask(event.target.value)}
                  spellCheck={false}
                  className="wl-editor"
                  data-testid="workflow-demo-library-task-contract"
                />
              )}
              {editor === 'policy' && (
                <div className="wl-policy" data-testid="workflow-demo-library-policy">
                  <textarea
                    aria-label="Composer Policy"
                    value={
                      planner === 'contract'
                        ? plan?.policy || 'Match each requested output to a registered provider and resolve its inputs.'
                        : policy
                    }
                    readOnly={planner === 'contract'}
                    onChange={(event) => {
                      setPolicy(event.target.value);
                      setPolicyHash('');
                    }}
                    spellCheck={false}
                    className="wl-editor"
                    data-testid="workflow-demo-library-policy-content"
                  />
                  {planner === 'agent' && policyHash && (
                    <code data-testid="workflow-demo-library-policy-hash">{policyHash}</code>
                  )}
                </div>
              )}
              {editor === 'decisions' && (
                <div className="wl-decisions">
                  {graph && (
                    <section data-testid="workflow-demo-library-selected-parts">
                      <h3 data-testid="workflow-demo-library-selected-title">Selected Workflow Parts</h3>
                      <ol className="wl-selection-path">
                        {graph.nodes.map((item) => {
                          const parent = workflows.find(
                            (entry) => entry.id === item.workflow.id && entry.version === item.workflow.version,
                          );
                          const child = parent?.subworkflows.find((entry) => entry.id === item.subworkflow);
                          return (
                            <li key={item.id}>
                              <button
                                type="button"
                                onClick={() => selectNode(item)}
                                data-testid="workflow-demo-library-selected-part"
                                data-variant={item.id}
                              >
                                {parent?.name || item.workflow.id} / {child?.name || item.subworkflow}
                              </button>
                            </li>
                          );
                        })}
                      </ol>
                    </section>
                  )}
                  <div data-testid="workflow-demo-library-decisions">
                    {plan?.decisions?.map((decision) => {
                      const parent = workflows.find((item) => item.id === decision.workflow_id);
                      const skipped =
                        parent?.subworkflows.filter((item) => !decision.selected_parts.includes(item.id)) || [];
                      return (
                        <section
                          className="wl-decision"
                          key={decision.workflow_id}
                          data-testid="workflow-demo-library-workflow-decision"
                          data-variant={decision.workflow_id}
                        >
                          <h3>{parent?.name || decision.workflow_id}</h3>
                          <p>{decision.reason}</p>
                          <h4 data-testid="workflow-demo-library-decision-selected-title">Selected</h4>
                          <ul>
                            {decision.selected_parts.map((id) => (
                              <li key={id}>{parent?.subworkflows.find((item) => item.id === id)?.name || id}</li>
                            ))}
                          </ul>
                          {skipped.length > 0 && (
                            <>
                              <h4 data-testid="workflow-demo-library-decision-skipped-title">Not selected</h4>
                              <ul>
                                {skipped.map((item) => (
                                  <li key={item.id}>{item.name}</li>
                                ))}
                              </ul>
                            </>
                          )}
                        </section>
                      );
                    })}
                    {plan?.error !== undefined && <pre>{pretty(plan.error)}</pre>}
                  </div>
                  {unmet && (
                    <section>
                      <h3 data-testid="workflow-demo-library-unmet-title">Unmet Requirements</h3>
                      <pre data-testid="workflow-demo-library-unmet">{pretty(unmet)}</pre>
                    </section>
                  )}
                </div>
              )}
            </form>
          )}
          {component && !importTrace && (
            <section className="wl-component-summary" data-testid="workflow-demo-library-component-summary">
              <div className="wl-pane-heading">
                <h2 data-testid="workflow-demo-library-component-title">Component verification</h2>
                <Button size="sm" onClick={returnToPlanner} data-testid="workflow-demo-library-back-to-planner">
                  Back to Planner
                </Button>
              </div>
              <h3 data-testid="workflow-demo-library-component-selection">Manually assembled check</h3>
              <dl className="wd-lineage">
                <dt data-testid="workflow-demo-library-selected-by-label">Selected by</dt>
                <dd data-testid="workflow-demo-library-selected-by">Developer</dd>
                <dt data-testid="workflow-demo-library-executed-by-label">Executed by</dt>
                <dd data-testid="workflow-demo-library-executed-by">Local processes</dd>
                <dt data-testid="workflow-demo-library-recorded-check-label">Original run</dt>
                <dd>{component.run.id}</dd>
              </dl>
              <div className="wl-actions">
                <Button
                  size="sm"
                  onClick={() => setInspector('artifacts')}
                  data-testid="workflow-demo-library-open-produced-files"
                >
                  Open produced files
                </Button>
                <Button
                  size="sm"
                  onClick={() => setInspector('results')}
                  data-testid="workflow-demo-library-open-check-results"
                >
                  Open verification results
                </Button>
              </div>
            </section>
          )}
          {importTrace && (
            <section className="wl-saved-import" data-testid="workflow-demo-library-saved-import">
              <div className="wl-pane-heading">
                <h2 data-testid="workflow-demo-library-saved-import-title">
                  Saved {importTrace.workflow?.name || 'source'} import
                </h2>
                <Button size="sm" onClick={returnToPlanner} data-testid="workflow-demo-library-import-back-to-request">
                  Back to request
                </Button>
              </div>
              <div className="wl-scroll">
                <LibraryImportReplay
                  key={importTrace.id}
                  trace={importTrace}
                  onPart={(item) => {
                    if (importTrace.workflow) selectPart(importTrace.workflow, item, true);
                  }}
                  onSource={(path) => void openSource(path, importTrace.workflow)}
                  onMaterial={(id) => void openImportMaterial(id)}
                  onProcess={() => setInspector('execution')}
                />
              </div>
            </section>
          )}
          {!importTrace && (
            <>
              <div className="wl-pane-heading wl-graph-heading">
                <h2 data-testid="workflow-demo-library-graph-title">
                  {component ? 'Recorded component task graph' : 'Task Graph'}
                </h2>
                {displayExecution && (
                  <span className="wl-run-status" data-testid="workflow-demo-library-run-status">
                    <Dot status={displayExecution.status} />
                    {displayExecution.status === 'verified' ? 'Steps completed' : displayExecution.status}
                  </span>
                )}
              </div>
              {(component?.verification?.full_inference_validated === false ||
                (!component && execution?.acceptance_status === 'incomplete')) && (
                <div className="wl-delivery-status" data-testid="workflow-demo-library-delivery-status">
                  {component ? 'Full model on Ascend remains unverified' : 'Some requested checks remain incomplete'}
                </div>
              )}
              {!component && plan?.status === 'blocked' && (
                <section className="wl-planner-blocked" data-testid="workflow-demo-library-planner-blocked">
                  <h3 data-testid="workflow-demo-library-planner-blocked-title">Planner could not choose steps</h3>
                  <pre>{pretty(plan.error)}</pre>
                  <Button
                    size="sm"
                    onClick={() => {
                      setImportTrace(null);
                      setSelectedNode('');
                      setInspector('execution');
                    }}
                    data-testid="workflow-demo-library-open-planner-attempt"
                  >
                    Open Planner attempt
                  </Button>
                </section>
              )}
              {graph && (
                <TaskGraph
                  graph={graph}
                  execution={displayExecution}
                  workflows={inspectWorkflows}
                  selected={selectedNode}
                  onSelect={selectNode}
                />
              )}
            </>
          )}
        </main>
        <aside className="wd-panel wl-pane" data-testid="workflow-demo-library-details">
          <div className="wl-pane-heading">
            <h2 data-testid="workflow-demo-library-details-title">Execution Details</h2>
            {nodeState && <Dot status={nodeState.status} />}
          </div>
          <div
            className="wl-tabs"
            role="tablist"
            aria-label="Execution inspector"
            data-testid="workflow-demo-library-inspector-tabs"
          >
            {(
              [
                'mapping',
                'source',
                'execution',
                'artifacts',
                'diff',
                ...(component ? ['results' as const] : []),
                'identity',
              ] as const
            ).map((tab) => (
              <button
                type="button"
                role="tab"
                key={tab}
                aria-selected={inspector === tab}
                disabled={tab === 'diff' && pairedDiffs.length === 0}
                onClick={() => setInspector(tab)}
                data-testid="workflow-demo-library-inspector-tab"
                data-variant={tab}
              >
                {tab === 'mapping'
                  ? 'Workflow Parts'
                  : tab === 'identity'
                    ? 'Raw Records'
                    : tab === 'source'
                      ? 'Source / Prompt'
                      : tab === 'execution'
                        ? 'Process'
                        : tab === 'artifacts'
                          ? 'Produced Files'
                          : tab === 'results'
                            ? 'Results'
                            : 'Code Diff'}
              </button>
            ))}
          </div>
          <div className="wl-scroll wl-inspector" ref={inspectorScroll}>
            {inspector === 'mapping' && workflow && (
              <WorkflowMapping
                workflow={workflow}
                partId={selectedPart}
                execution={displayExecution}
                onPart={(child) => selectPart(workflow, child, Boolean(importTrace || component))}
                onSource={(path) => void openSource(path)}
              />
            )}
            {inspector === 'results' && component && (
              <section data-testid="workflow-demo-library-check-results">
                <h3 data-testid="workflow-demo-library-independent-results-title">Checked on CPU after this run</h3>
                {checkedCpp && (
                  <section data-testid="workflow-demo-library-tested-source">
                    <h4>What was compared</h4>
                    <Button
                      size="sm"
                      onClick={() => void openArtifact(checkedCpp, false)}
                      data-testid="workflow-demo-library-open-tested-cpp"
                    >
                      Open tested CPU file {checkedCpp.path.split(/[\\/]/).pop()}
                    </Button>
                    {recordedReferenceSources(component).map((sourceId) => (
                      <p key={sourceId} data-testid="workflow-demo-library-tested-reference" data-variant={sourceId}>
                        Reference derived from <code>{sourceId}</code>
                      </p>
                    ))}
                    {checkedProject &&
                      component.command_records.some((command) =>
                        /(?:^|[/\\])strata_core_test(?:\.exe)?$/.test(command.argv?.[0] || ''),
                      ) && (
                        <Button
                          size="sm"
                          onClick={() => void openRecordedNumericalTest()}
                          data-testid="workflow-demo-library-open-numerical-test"
                        >
                          Open reference and test code
                        </Button>
                      )}
                  </section>
                )}
                <dl className="wl-outcome-summary" data-testid="workflow-demo-library-outcome-summary">
                  {componentOutcome(component).map((row) => (
                    <div key={row.label}>
                      <dt>{row.label}</dt>
                      <dd>{row.value}</dd>
                    </div>
                  ))}
                </dl>
                <h4 data-testid="workflow-demo-library-verification-commands-title">Commands that ran on CPU</h4>
                {component.command_records.map((command, index) => (
                  <section
                    className="wl-event"
                    key={index}
                    data-testid="workflow-demo-library-independent-command"
                    data-variant={index}
                  >
                    <CommandContent command={command} />
                  </section>
                ))}
                <h4 data-testid="workflow-demo-library-verification-record-title">Full verification record</h4>
                <pre data-testid="workflow-demo-library-check-verification">{pretty(component.verification)}</pre>
                <h4 data-testid="workflow-demo-library-check-provenance-title">Original evidence provenance</h4>
                <pre data-testid="workflow-demo-library-check-provenance">{pretty(component.recording_provenance)}</pre>
              </section>
            )}
            {inspector === 'identity' && workflow && (
              <section data-testid="workflow-demo-library-identity">
                <h3>{part?.name || workflow.name}</h3>
                <dl className="wd-lineage">
                  <dt data-testid="workflow-demo-library-origin-label">Repository</dt>
                  <dd>{workflow.source.repository || workflow.source.repository_url}</dd>
                  <dt data-testid="workflow-demo-library-commit-label">Commit</dt>
                  <dd>
                    <code>{workflow.source.revision || workflow.source.commit}</code>
                  </dd>
                  <dt data-testid="workflow-demo-library-version-label">Library version</dt>
                  <dd>
                    <code>{workflow.version}</code>
                  </dd>
                </dl>
                {part && (
                  <>
                    <h4 data-testid="workflow-demo-library-implementation-title">Execution Entry</h4>
                    <pre>{pretty(part.implementation)}</pre>
                    <h4 data-testid="workflow-demo-library-inputs-title">Input Contract</h4>
                    <pre>{pretty(part.inputs)}</pre>
                    <h4 data-testid="workflow-demo-library-outputs-title">Output Contract</h4>
                    <pre>{pretty(part.outputs)}</pre>
                    <h4 data-testid="workflow-demo-library-verification-title">Verification</h4>
                    <pre>{pretty(part.verification || part.requirements)}</pre>
                  </>
                )}
                {paths.length > 0 && <h4 data-testid="workflow-demo-library-evidence-title">Source Evidence</h4>}
                <div className="wl-source-links">
                  {paths.map((path) => (
                    <button
                      type="button"
                      key={path}
                      onClick={() => void openSource(path)}
                      data-testid="workflow-demo-library-source-link"
                      data-variant={path}
                    >
                      {path}
                    </button>
                  ))}
                </div>
                {typeof part?.implementation.source_path === 'string' && (
                  <Button
                    size="sm"
                    onClick={() => void openSource(String(part.implementation.source_path))}
                    data-testid="workflow-demo-library-open-python"
                  >
                    Read Python implementation
                  </Button>
                )}
                {typeof workflow.source.decomposition_path === 'string' && (
                  <Button
                    size="sm"
                    onClick={() => void openSource(String(workflow.source.decomposition_path))}
                    data-testid="workflow-demo-library-open-decomposition"
                  >
                    Read source decomposition
                  </Button>
                )}
                {part?.implementation.prompt_path && (
                  <Button
                    size="sm"
                    onClick={() => void openSource(part.implementation.prompt_path!)}
                    data-testid="workflow-demo-library-open-prompt"
                  >
                    Read Agent prompt
                  </Button>
                )}
                <pre data-testid="workflow-demo-library-card-content">{pretty(part || workflow)}</pre>
              </section>
            )}
            {inspector === 'identity' && (
              <section data-testid="workflow-demo-library-raw-evidence">
                <h3 data-testid="workflow-demo-library-raw-evidence-title">Original Records</h3>
                <pre>{pretty(nodeState || importTrace || component || plan)}</pre>
              </section>
            )}
            {inspector === 'source' && (
              <section data-testid="workflow-demo-library-source">
                <form
                  className="wl-source-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void openSource(sourcePath);
                  }}
                >
                  <input
                    aria-label="Source or prompt path"
                    value={sourcePath}
                    onChange={(event) => setSourcePath(event.target.value)}
                    data-testid="workflow-demo-library-source-path"
                  />
                  <Button
                    size="sm"
                    type="submit"
                    disabled={!workflow || !sourcePath}
                    data-testid="workflow-demo-library-read-source"
                  >
                    Read
                  </Button>
                </form>
                {source && (
                  <>
                    <code data-testid="workflow-demo-library-source-filename">{source.path}</code>
                    <pre
                      className="wl-code"
                      data-language={/\.md$/i.test(source.path) ? 'markdown' : 'code'}
                      data-testid="workflow-demo-library-source-code"
                    >
                      {source.content}
                    </pre>
                  </>
                )}
              </section>
            )}
            {inspector === 'execution' && (
              <section data-testid="workflow-demo-library-execution-log">
                {importTrace && (
                  <section className="wl-import-trace" data-testid="workflow-demo-library-import-trace">
                    <h3 data-testid="workflow-demo-library-import-trace-title">Source registration</h3>
                    <dl className="wd-lineage">
                      <dt data-testid="workflow-demo-library-import-repo-label">Existing project</dt>
                      <dd>
                        {String(importTrace.request?.repository_url || importTrace.workflow?.source.repository || '')}
                      </dd>
                      <dt data-testid="workflow-demo-library-import-fixed-label">Recorded source version</dt>
                      <dd>{importTrace.workflow?.source.revision}</dd>
                    </dl>
                    <h4 data-testid="workflow-demo-library-import-materials-title">
                      Source analysis and created wrappers
                    </h4>
                    <div className="wl-source-links">
                      {importTrace.materials?.map((material) => (
                        <button
                          type="button"
                          key={material.id}
                          onClick={() => void openImportMaterial(material.id)}
                          data-testid="workflow-demo-library-import-material"
                          data-variant={material.id}
                        >
                          {material.name}
                        </button>
                      ))}
                    </div>
                  </section>
                )}
                {node && (
                  <>
                    <h3>{part?.name || node.subworkflow}</h3>
                    <dl className="wd-lineage" data-testid="workflow-demo-library-node-bindings">
                      <dt data-testid="workflow-demo-library-node-parent-label">Original workflow</dt>
                      <dd>{workflow?.name || node.workflow.id}</dd>
                      <dt data-testid="workflow-demo-library-node-part-label">Selected part</dt>
                      <dd>{node.name || part?.name || node.subworkflow}</dd>
                      <dt data-testid="workflow-demo-library-node-selector-label">Selection source</dt>
                      <dd>
                        {component
                          ? 'Developer — manually assembled check'
                          : plan?.id
                            ? `Planner record ${plan.id}`
                            : 'No selection record available'}
                      </dd>
                    </dl>
                    {unconsumedFramework && (
                      <section data-testid="workflow-demo-library-unconsumed-framework">
                        <h4 data-testid="workflow-demo-library-built-framework-title">Built framework</h4>
                        <p data-testid="workflow-demo-library-no-framework-consumer">
                          No downstream test consumed this output.
                        </p>
                      </section>
                    )}
                    {nodeState?.attempts?.map((attempt) => (
                      <section
                        className="wl-event"
                        key={attempt.number}
                        data-testid="workflow-demo-library-node-attempt"
                        data-variant={attempt.number}
                      >
                        <h4>Attempt {attempt.number}</h4>
                        <dl className="wd-lineage">
                          {filePorts(attempt.inputs).map(([port, artifact]) => (
                            <div className="wl-file-handoff" key={`in:${port}`}>
                              <dt>Opened: {port}</dt>
                              <dd>
                                <button
                                  type="button"
                                  className="wl-file-open"
                                  onClick={() => void openArtifact(artifact, false)}
                                  data-testid="workflow-demo-library-open-handoff"
                                  data-variant={`${attempt.number}/${port}/${artifact.id}`}
                                >
                                  {artifact.path.split(/[\\/]/).pop()}
                                </button>
                                <code className="wl-file-provenance">{artifact.path}</code>
                              </dd>
                            </div>
                          ))}
                          {filePorts(attempt.outputs).map(([port, artifact]) => (
                            <div className="wl-file-handoff" key={`out:${port}`}>
                              <dt>Produced: {port}</dt>
                              <dd>
                                <button
                                  type="button"
                                  className="wl-file-open"
                                  onClick={() => void openArtifact(artifact, false)}
                                  data-testid="workflow-demo-library-open-handoff"
                                  data-variant={`${attempt.number}/${port}/${artifact.id}`}
                                >
                                  {artifact.path.split(/[\\/]/).pop()}
                                </button>
                                <code className="wl-file-provenance">{artifact.path}</code>
                              </dd>
                            </div>
                          ))}
                        </dl>
                        {attempt.commands?.map((command, index) => (
                          <CommandContent command={command} key={index} />
                        ))}
                      </section>
                    ))}
                  </>
                )}
                {selectedNode && (
                  <Button size="sm" onClick={() => setSelectedNode('')} data-testid="workflow-demo-library-all-events">
                    All process events
                  </Button>
                )}
                {relevantEvents.map(({ key, jobId, event }) => (
                  <article
                    key={key}
                    className="wl-event"
                    data-testid="workflow-demo-library-process-event"
                    data-variant={key}
                  >
                    <div className="wl-event-heading">
                      <code>
                        {event.sequence} · {event.type}
                      </code>
                      <time>{event.time || event.timestamp}</time>
                    </div>
                    <code className="wl-event-job">{jobId}</code>
                    {eventNarrative(event, graph?.nodes) && (
                      <p className="wl-event-narrative" data-testid="workflow-demo-library-event-narrative">
                        {eventNarrative(event, graph?.nodes)}
                      </p>
                    )}
                    <EventContent event={event} />
                  </article>
                ))}
                {!component && !importTrace && plan?.invocations !== undefined && (
                  <section className="wl-section">
                    <h4 data-testid="workflow-demo-library-model-invocations-title">Planner Model Invocations</h4>
                    <pre data-testid="workflow-demo-library-model-invocations">{pretty(plan.invocations)}</pre>
                  </section>
                )}
                {!component && !importTrace && plan?.tool_calls !== undefined && (
                  <section className="wl-section">
                    <h4 data-testid="workflow-demo-library-tool-calls-title">Planner Library Queries</h4>
                    <pre data-testid="workflow-demo-library-tool-calls">{pretty(plan.tool_calls)}</pre>
                  </section>
                )}
              </section>
            )}
            {inspector === 'artifacts' && (
              <section data-testid="workflow-demo-library-output-list">
                {projectSource && (
                  <section className="wl-project-source" data-testid="workflow-demo-library-project-files">
                    <h3 data-testid="workflow-demo-library-project-files-title">Project Source Files</h3>
                    <div className="wl-source-members">
                      {Object.keys(projectSource.files)
                        .sort()
                        .map((path) => (
                          <button
                            type="button"
                            key={path}
                            aria-pressed={generated?.path === path}
                            onClick={() => void openProjectFile(path)}
                            data-testid="workflow-demo-library-project-file"
                            data-variant={path}
                          >
                            {path}
                          </button>
                        ))}
                    </div>
                  </section>
                )}
                {generated && (
                  <>
                    <h3>{generated.path}</h3>
                    {pairedDiffs.length > 0 && (
                      <Button
                        size="sm"
                        onClick={() => setInspector('diff')}
                        data-testid="workflow-demo-library-compare-original"
                      >
                        Compare with original
                      </Button>
                    )}
                    <pre className="wl-code wl-generated-code" data-testid="workflow-demo-library-generated-code">
                      {generated.content}
                    </pre>
                  </>
                )}

                {artifacts.map((artifact) => (
                  <article
                    className="wl-artifact"
                    key={artifact.id}
                    data-testid="workflow-demo-library-output"
                    data-variant={artifact.id}
                  >
                    <button
                      type="button"
                      onClick={() => void openArtifact(artifact, false)}
                      data-testid="workflow-demo-library-output-preview"
                      data-variant={artifact.id}
                    >
                      {artifact.kind === 'source.project'
                        ? 'Open source project files'
                        : artifact.kind === 'source.cpp'
                          ? `Generated C++: ${artifact.path.split(/[\\/]/).pop()}`
                          : artifact.path.split(/[\\/]/).pop()}
                    </button>
                    <Button
                      size="sm"
                      onClick={() => void openArtifact(artifact, true)}
                      data-testid="workflow-demo-library-output-download"
                      data-variant={artifact.id}
                    >
                      Download
                    </Button>
                    <code>{artifact.sha256}</code>
                  </article>
                ))}
              </section>
            )}
            {inspector === 'diff' && pairedDiffs.length > 0 && (
              <section className="wl-code-diff" data-testid="workflow-demo-library-code-diff">
                {pairedDiffs.some((entry) => entry.target === 'ASCEND') && (
                  <div className="wl-actions" data-testid="workflow-demo-library-ascend-comparison-scope">
                    <strong>Ascend source comparison</strong>
                    {component?.verification?.native_compilation === 'NOT_RUN' && (
                      <span>Ascend build was not run.</span>
                    )}
                    {checkedCpp && (
                      <Button
                        size="sm"
                        onClick={() => setInspector('results')}
                        data-testid="workflow-demo-library-open-cpu-check-from-diff"
                      >
                        View separate CPU check
                      </Button>
                    )}
                  </div>
                )}
                {pairedDiffs.map((entry, index) => (
                  <article
                    className="wl-code-diff-pair"
                    key={`${entry.generated_path}:${entry.source_path}:${index}`}
                    data-testid="workflow-demo-library-diff-pair"
                    data-variant={`${entry.generated_path}/${index}`}
                  >
                    <div>
                      <h3 data-testid="workflow-demo-library-original-code-title">Original STRATA source</h3>
                      <code>{entry.source_path}</code>
                      <pre className="wl-code" data-testid="workflow-demo-library-diff-original">
                        {entry.source_code}
                      </pre>
                    </div>
                    <div>
                      <h3 data-testid="workflow-demo-library-produced-code-title">
                        {entry.target === 'ASCEND' ? 'Generated Ascend C++' : 'Generated C++'}
                      </h3>
                      <code>{entry.generated_path}</code>
                      <pre className="wl-code" data-testid="workflow-demo-library-diff-generated">
                        {entry.generated_code}
                      </pre>
                    </div>
                  </article>
                ))}
              </section>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
