import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Button } from '../../components/ui/Button/Button';
import { copy, userGoalSelection } from './copy.en';
import { factoryClient, isTerminal, parseCodeDiff, parseEngineeringTask, pretty, statusColor } from './factoryClient';
import type {
  Artifact,
  CodeDiffArtifact,
  FactoryCatalog,
  FactoryEdge,
  FactoryEvent,
  FactoryNode,
  FactoryRun,
  StageDeclaration,
} from './factoryClient';
import { edgeDeliveryStatus, edgePath, layoutGraph } from './graphLayout';
import { ReplayControls } from './ReplayControls';
import { normalizeReplayEvents, projectReplay } from './replayProjection.js';
import './workflow-demo.css';

const repository = 'https://github.com/niko1221/strata';
const runStorageKey = 'ai4research.factory.last-run';
const initialTask = JSON.stringify(
  {
    description: 'Construct the supported STRATA core source from the selected production modules.',
    capabilities: ['routing', 'activation', 'aggregation'],
    acceptance: {
      source_project: true,
      cpu_validation: true,
      full_model_inference: false,
      native_execution: false,
      compare_original: false,
    },
  },
  null,
  2,
);

function storedRunId(): string {
  try {
    const requested = new URLSearchParams(window.location.search).get('factoryRun');
    if (requested) return requested;
    return localStorage.getItem(runStorageKey) ?? '';
  } catch {
    return '';
  }
}

function requestedReplay(): boolean {
  try {
    return new URLSearchParams(window.location.search).get('replay') === '1';
  } catch {
    return false;
  }
}

function StatusDot({ status }: { status: string }) {
  return <span className="wd-status" data-variant={statusColor(status)} role="img" aria-label={status} />;
}

function ArtifactList({ runId, artifacts }: { runId: string; artifacts: Artifact[] }) {
  const [error, setError] = useState('');
  const objectUrls = useRef(new Set<string>());
  useEffect(() => {
    const activeUrls = objectUrls.current;
    return () => {
      activeUrls.forEach((url) => URL.revokeObjectURL(url));
      activeUrls.clear();
    };
  }, []);
  const download = async (artifact: Artifact) => {
    try {
      setError('');
      const response = await factoryClient.artifact(runId, artifact.id);
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = artifact.path.split(/[\\/]/).pop() || artifact.id;
      document.body.appendChild(link);
      link.click();
      link.remove();
      objectUrls.current.add(url);
    } catch (failure) {
      setError(String(failure));
    }
  };
  return (
    <div>
      <ul className="wd-artifact-list" data-testid="workflow-demo-artifact-list">
        {artifacts.map((artifact) => (
          <li key={artifact.id} data-testid="workflow-demo-artifact" data-variant={artifact.id}>
            <a
              href={factoryClient.artifactUrl(runId, artifact.id)}
              onClick={(event) => {
                event.preventDefault();
                void download(artifact);
              }}
            >
              {/\.zip$/i.test(artifact.path) ? artifact.path.split(/[\\/]/).pop() : artifact.kind}
            </a>
            <code>{artifact.path}</code>
            <code>{artifact.sha256}</code>
          </li>
        ))}
      </ul>
      {error && (
        <p role="alert" className="wd-error">
          {error}
        </p>
      )}
    </div>
  );
}

function CodeDiffPanel({ runId, artifact }: { runId: string; artifact: Artifact }) {
  const [result, setResult] = useState<{ identity: string; data?: CodeDiffArtifact; error?: string } | null>(null);
  const identity = `${runId}/${artifact.id}/${artifact.sha256}`;
  useEffect(() => {
    const controller = new AbortController();
    void factoryClient
      .artifactText(runId, artifact.id, controller.signal)
      .then((text) => {
        const data = parseCodeDiff(text);
        if (!controller.signal.aborted) setResult({ identity, data });
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setResult({ identity, error: String(failure) });
      });
    return () => controller.abort();
  }, [runId, artifact.id, identity]);

  const current = result?.identity === identity ? result : null;
  return (
    <section className="wd-code-diff" data-testid="workflow-demo-code-diff" data-artifact={artifact.id}>
      <h3>Code Diff</h3>
      {current?.error && (
        <p className="wd-error" role="alert" data-testid="workflow-demo-code-diff-error">
          {current.error}
        </p>
      )}
      {current?.data?.files.map((file, index) => (
        <div
          className="wd-code-diff-grid"
          key={`${identity}/${index}`}
          data-testid="workflow-demo-code-diff-file"
          data-variant={file.generated_path}
        >
          <section className="wd-code-diff-pane" aria-label={`Original source: ${file.source_path}`}>
            <h4>{/\.(cu|cuh)$/i.test(file.source_path) ? 'Original CUDA' : 'Original source'}</h4>
            <code className="wd-code-diff-path">{file.source_path}</code>
            <pre data-testid="workflow-demo-code-diff-original">
              <code>{file.source_code}</code>
            </pre>
          </section>
          <section className="wd-code-diff-pane" aria-label={`Generated C++: ${file.generated_path}`}>
            <h4>Generated C++</h4>
            <code className="wd-code-diff-path">{file.generated_path}</code>
            <pre data-testid="workflow-demo-code-diff-generated">
              <code>{file.generated_code}</code>
            </pre>
          </section>
        </div>
      ))}
    </section>
  );
}

function ValueReportPanel({ runId, artifact }: { runId: string; artifact: Artifact }) {
  const [result, setResult] = useState<{ identity: string; text?: string; error?: string } | null>(null);
  const identity = `${runId}/${artifact.id}/${artifact.sha256}`;
  useEffect(() => {
    const controller = new AbortController();
    void factoryClient
      .artifactText(runId, artifact.id, controller.signal)
      .then((text) => {
        if (!text.trim()) throw new Error('Value report artifact is empty');
        if (!controller.signal.aborted) setResult({ identity, text });
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setResult({ identity, error: String(failure) });
      });
    return () => controller.abort();
  }, [runId, artifact.id, identity]);
  const current = result?.identity === identity ? result : null;
  return (
    <section className="wd-value-report" data-testid="workflow-demo-value-report" data-artifact={artifact.id}>
      <h3>Value Report</h3>
      {current?.error && (
        <p className="wd-error" role="alert" data-testid="workflow-demo-value-report-error">
          {current.error}
        </p>
      )}
      {current?.text && <pre data-testid="workflow-demo-value-report-content">{current.text}</pre>}
    </section>
  );
}

function ContractDetails({ stage }: { stage: StageDeclaration }) {
  return (
    <div className="wd-contract" data-testid="workflow-demo-stage-contract">
      <p className="wd-lineage">
        {stage.workflow_id} / {stage.subworkflow_id} / {stage.id}
      </p>
      <h4>{copy.entrypoint}</h4>
      <code>{stage.entrypoint}</code>
      <h4>{copy.inputs}</h4>
      <ul>
        {stage.inputs.map((port) => (
          <li key={port.name}>
            {port.name}: {port.kind}
            {port.required ? ' *' : ''}
          </li>
        ))}
      </ul>
      <h4>{copy.outputs}</h4>
      <ul>
        {stage.outputs.map((port) => (
          <li key={port.name}>
            {port.name}: {port.kind}
          </li>
        ))}
      </ul>
      <h4>{copy.tools}</h4>
      <pre>{pretty(stage.tools)}</pre>
      <h4>{copy.environment}</h4>
      <pre>{pretty(stage.environment)}</pre>
      <h4>{copy.verification}</h4>
      <pre>{pretty(stage.verifier)}</pre>
    </div>
  );
}

function ExecutionDetails({ run, node, events }: { run: FactoryRun; node: FactoryNode; events: FactoryEvent[] }) {
  return (
    <div data-testid="workflow-demo-node-execution">
      <p className="wd-lineage">
        {node.workflow_id} / {node.subworkflow_id} / {node.stage_id}
      </p>
      {node.attempts.map((attempt) => (
        <section
          className="wd-attempt"
          key={attempt.number}
          data-testid="workflow-demo-attempt"
          data-variant={attempt.number}
          data-status={attempt.status}
        >
          <div className="wd-detail-title">
            <h4>{copy.attempt(attempt.number)}</h4>
            <StatusDot status={attempt.status} />
          </div>
          <p>
            {attempt.started_at}
            {attempt.finished_at ? ` → ${attempt.finished_at}` : ''}
          </p>
          {!!attempt.inputs?.length && (
            <>
              <h4>{copy.inputs}</h4>
              <ArtifactList runId={run.id} artifacts={attempt.inputs} />
            </>
          )}
          {!!attempt.commands?.length && (
            <>
              <h4>{copy.commands}</h4>
              {attempt.commands.map((command, index) => (
                <div
                  className="wd-command"
                  key={`${attempt.number}-${index}`}
                  data-testid="workflow-demo-command"
                  data-variant={index}
                >
                  <code>{command.argv.map((argument) => JSON.stringify(argument)).join(' ')}</code>
                  <p>{command.cwd}</p>
                  {command.exit_code !== null && command.exit_code !== undefined && <p>Exit {command.exit_code}</p>}
                  {command.stdout && <pre>{command.stdout}</pre>}
                  {command.stderr && <pre className="wd-error">{command.stderr}</pre>}
                </div>
              ))}
            </>
          )}
          {!!attempt.error && (
            <>
              <h4>{copy.error}</h4>
              <pre className="wd-error">{pretty(attempt.error)}</pre>
            </>
          )}
          {!!attempt.verification && (
            <>
              <h4>{copy.verification}</h4>
              <pre>{pretty(attempt.verification)}</pre>
            </>
          )}
          {!!attempt.outputs?.length && (
            <>
              <h4>{copy.outputs}</h4>
              <ArtifactList runId={run.id} artifacts={attempt.outputs} />
            </>
          )}
        </section>
      ))}
      {events.some((event) => event.node_id === node.id) && (
        <section className="wd-node-events">
          <h4>{copy.events}</h4>
          <ol>
            {events
              .filter((event) => event.node_id === node.id)
              .map((event) => (
                <li key={event.sequence} data-testid="workflow-demo-event" data-variant={event.sequence}>
                  <p>
                    {event.time} · {event.type}
                  </p>
                  {event.type === 'command.output' ? (
                    <pre data-testid="workflow-demo-live-output" data-stream={String(event.payload.stream ?? '')}>
                      {String(event.payload.text ?? '')}
                    </pre>
                  ) : (
                    <pre>{pretty(event.payload)}</pre>
                  )}
                </li>
              ))}
          </ol>
        </section>
      )}
    </div>
  );
}

function Graph({
  nodes,
  edges,
  artifacts,
  selected,
  select,
}: {
  nodes: FactoryNode[];
  edges: FactoryEdge[];
  artifacts: Artifact[];
  selected: string;
  select: (id: string) => void;
}) {
  const layout = useMemo(() => layoutGraph(nodes, edges), [nodes, edges]);
  return (
    <div className="wd-graph-scroll" data-testid="workflow-demo-graph">
      <svg
        viewBox={`0 0 800 ${layout.height}`}
        className="wd-graph"
        aria-label={copy.dependencies}
        data-testid="workflow-demo-edges"
      >
        <defs>
          {['pending', 'verified', 'failed', 'running', 'blocked'].map((status) => (
            <marker
              key={status}
              id={`factory-arrow-${status}`}
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="5"
              markerHeight="5"
              orient="auto"
              className="wd-edge"
              data-variant={status}
            >
              <path d="M0 0 L10 5 L0 10 Z" fill="currentColor" />
            </marker>
          ))}
        </defs>
        {edges.map((edge, index) => {
          const from = layout.positions[edge.from];
          const to = layout.positions[edge.to];
          if (!from || !to) return null;
          const route = edgePath(from, to);
          const status = edgeDeliveryStatus(edge, nodes, artifacts);
          return (
            <g
              key={`${edge.from}-${edge.to}-${index}`}
              className="wd-edge"
              data-variant={status}
              data-testid="workflow-demo-edge"
              data-edge={`${edge.from}-${edge.to}`}
            >
              <path
                d={route.d}
                className="wd-edge-path"
                stroke="currentColor"
                fill="none"
                strokeWidth="1"
                strokeDasharray={status === 'pending' ? '4 4' : undefined}
                markerEnd={`url(#factory-arrow-${status})`}
              />
              <text x={route.labelX} y={route.labelY} textAnchor="middle" className="wd-edge-label">
                {edge.data}
              </text>
            </g>
          );
        })}
        {nodes.map((node) => {
          const position = layout.positions[node.id];
          return (
            <foreignObject key={node.id} x={position.x - 128} y={position.y - 34} width="256" height="68">
              <button
                type="button"
                className="wd-node"
                aria-pressed={selected === node.id}
                aria-label={`${node.name}, ${node.status}`}
                onClick={() => select(node.id)}
                data-testid="workflow-demo-node"
                data-variant={node.id}
                data-status={node.status}
              >
                <span>{node.name}</span>
                <StatusDot status={node.status} />
              </button>
            </foreignObject>
          );
        })}
      </svg>
    </div>
  );
}

export function WorkflowDemo() {
  const [catalog, setCatalog] = useState<FactoryCatalog | null>(null);
  const [runId, setRunId] = useState(storedRunId);
  const [run, setRun] = useState<FactoryRun | null>(null);
  const [events, setEvents] = useState<FactoryEvent[]>([]);
  const [selected, setSelected] = useState('');
  const [stageId, setStageId] = useState('');
  const [revision, setRevision] = useState('');
  const [model, setModel] = useState('');
  const [taskText, setTaskText] = useState(initialTask);
  const [backend, setBackend] = useState<'ascend' | 'cpu' | 'cuda'>('ascend');
  const [goals, setGoals] = useState<string[]>([
    'construction.package',
    'value.report',
    'inference.result',
    'verification.comparison',
  ]);
  const [replay, setReplay] = useState(requestedReplay);
  const [replayCursor, setReplayCursor] = useState(0);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const loadCatalog = useCallback(async () => {
    try {
      const value = await factoryClient.catalog();
      if (mounted.current) {
        setCatalog(value);
        setError('');
      }
    } catch (failure) {
      if (mounted.current) setError(String(failure));
    }
  }, []);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  useEffect(() => {
    if (!runId) return;
    const controller = new AbortController();
    let refreshInFlight: Promise<void> | null = null;
    let refreshAgain = false;
    const applySnapshot = (snapshot: FactoryRun) => {
      if (controller.signal.aborted) return;
      setRun(snapshot);
      setSelected((previous) =>
        snapshot.nodes.some((node) => node.id === previous)
          ? previous
          : (snapshot.nodes.find((node) => node.status === 'running')?.id ?? snapshot.nodes[0]?.id ?? ''),
      );
    };
    const refreshFromEvent = (): Promise<void> => {
      if (refreshInFlight) {
        refreshAgain = true;
        return refreshInFlight;
      }
      refreshInFlight = factoryClient
        .run(runId, controller.signal)
        .then(applySnapshot)
        .catch((failure) => {
          if (!controller.signal.aborted) setError(String(failure));
        })
        .finally(() => {
          refreshInFlight = null;
          if (refreshAgain && !controller.signal.aborted) {
            refreshAgain = false;
            void refreshFromEvent();
          }
        });
      return refreshInFlight;
    };
    const connect = async () => {
      try {
        const [snapshot, history] = await Promise.all([
          factoryClient.run(runId, controller.signal),
          factoryClient.events(runId, 0, controller.signal),
        ]);
        if (controller.signal.aborted) return;
        setGoals(userGoalSelection(snapshot.request.goals));
        setBackend(snapshot.request.target_backend);
        setRevision(snapshot.request.revision ?? '');
        setModel(snapshot.request.model_path ?? '');
        setTaskText(snapshot.request.task ? JSON.stringify(snapshot.request.task, null, 2) : '');
        applySnapshot(snapshot);
        setEvents(history.events);
        if (replay || isTerminal(snapshot.status)) return;
        await factoryClient.stream(
          runId,
          history.sequence,
          (frame) => {
            if (controller.signal.aborted) return;
            if (frame.event === 'snapshot') {
              applySnapshot(frame.data as FactoryRun);
              return;
            }
            const event = frame.data as FactoryEvent;
            if (typeof event.sequence !== 'number' || typeof event.type !== 'string')
              throw new Error('Invalid factory event frame');
            setEvents((previous) =>
              previous.some((item) => item.sequence === event.sequence) ? previous : [...previous, event],
            );
            // Updates are requested only in response to a real server event; no playback clock exists.
            void refreshFromEvent();
          },
          controller.signal,
        );
        await refreshFromEvent();
      } catch (failure) {
        if (!controller.signal.aborted) setError(String(failure));
      }
    };
    void connect();
    return () => controller.abort();
  }, [runId, replay]);

  const start = async (event: FormEvent) => {
    event.preventDefault();
    if (replay || (!goals.length && !taskText.trim()) || submitting) return;
    setSubmitting(true);
    setError('');
    try {
      const snapshot = await factoryClient.start({
        repository_url: repository,
        goals,
        target_backend: backend,
        ...(taskText.trim() ? { task: parseEngineeringTask(taskText) } : {}),
        ...(revision.trim() ? { revision: revision.trim() } : {}),
        ...(model.trim() ? { model_path: model.trim() } : {}),
      });
      if (!mounted.current) return;
      setRun(snapshot);
      setEvents([]);
      setSelected(snapshot.nodes[0]?.id ?? '');
      setStageId('');
      setRunId(snapshot.id);
      try {
        localStorage.setItem(runStorageKey, snapshot.id);
      } catch {
        /* Storage is optional; backend custody is authoritative. */
      }
    } catch (failure) {
      if (mounted.current) setError(String(failure));
    } finally {
      if (mounted.current) setSubmitting(false);
    }
  };

  const recording = useMemo(() => {
    try {
      return { events: normalizeReplayEvents(events), error: '' };
    } catch (failure) {
      return { events: [] as FactoryEvent[], error: String(failure) };
    }
  }, [events]);
  const projection = useMemo(() => {
    if (!replay || !run || recording.error) return null;
    try {
      return { run: projectReplay(run, recording.events, replayCursor), error: '' };
    } catch (failure) {
      return { run: null, error: String(failure) };
    }
  }, [replay, run, recording, replayCursor]);
  const displayRun = replay ? (projection?.run ?? null) : run;
  const graphNodes = displayRun?.nodes ?? [];
  const graphEdges = displayRun?.edges ?? [];
  const graphEvents = replay ? recording.events.slice(0, projection?.run?.replay.cursor ?? 0) : events;
  const latestNodeEvent = replay
    ? graphEvents
        .slice()
        .reverse()
        .find((event) => event.node_id)
    : undefined;
  const selectedNode =
    graphNodes.find((node) => node.id === selected) ??
    (replay ? (graphNodes.find((node) => node.id === latestNodeEvent?.node_id) ?? graphNodes[0]) : undefined);
  const currentRevision = replay ? displayRun?.graph_revisions[displayRun.graph_revisions.length - 1] : undefined;
  const seekReplay = useCallback((cursor: number) => {
    setReplayCursor(cursor);
    setSelected('');
    setStageId('');
  }, []);
  const enterReplay = (cursor = 0) => {
    setError('');
    seekReplay(cursor);
    setReplay(true);
  };
  const returnLive = () => {
    setReplay(false);
    setSelected('');
    setStageId('');
    try {
      const url = new URL(window.location.href);
      url.searchParams.delete('replay');
      window.history.replaceState(window.history.state, '', url);
    } catch {
      /* Replay state does not require URL storage. */
    }
  };
  const jumpToRevision = (revisionNumber: string) => {
    const index = recording.events.findIndex(
      (event) => event.type === 'graph.updated' && String(event.payload.revision) === revisionNumber,
    );
    if (index < 0) {
      setError('The recorded graph revision event is unavailable');
      return;
    }
    enterReplay(index + 1);
  };
  const selectedStage = catalog?.stages.find((stage) => stage.id === (stageId || selectedNode?.stage_id));
  const selectedRunActive = !!run && !isTerminal(run.status);
  const availableGoals = (catalog?.goals ?? []).filter((kind) => copy.goals.some((goal) => goal.value === kind));
  const publishedArtifacts = Array.isArray(displayRun?.artifacts) ? displayRun.artifacts : [];
  const codeDiffArtifact = publishedArtifacts
    .slice()
    .reverse()
    .find((artifact) => artifact.kind === 'construction.code_diff');
  const valueReportArtifact = publishedArtifacts
    .slice()
    .reverse()
    .find((artifact) => artifact.kind === 'value.report');
  const deliverables =
    publishedArtifacts
      .filter((artifact) =>
        /^(candidate|implementation|construction|build|inference|verification|value)\./.test(artifact.kind),
      )
      .sort(
        (first, second) =>
          Number(second.kind === 'construction.package') - Number(first.kind === 'construction.package'),
      ) ?? [];

  return (
    <div
      className="wd-app flex-1 min-h-0 min-w-0"
      data-testid="workflow-demo"
      data-run-id={displayRun?.id ?? runId}
      data-status={displayRun?.status ?? ''}
      data-mode={replay ? 'replay' : 'live'}
    >
      <header className="wd-header">
        <h1 data-testid="workflow-demo-title">{copy.title}</h1>
        <p>{copy.narrative}</p>
      </header>
      <div className="wd-layout">
        <section className="wd-panel wd-pool" aria-label={copy.pool} data-testid="workflow-demo-pool">
          <div className="wd-panel-heading">
            <h2>{copy.pool}</h2>
            <button
              type="button"
              onClick={() => void loadCatalog()}
              aria-label="Refresh capability pool"
              data-testid="workflow-demo-refresh-pool"
            >
              {copy.refresh}
            </button>
          </div>
          <div className="wd-pool-scroll">
            {catalog?.groups.map((workflow) => (
              <section
                className="wd-workflow-group"
                key={workflow.id}
                data-testid="workflow-demo-workflow-group"
                data-variant={workflow.id}
              >
                <h3>{workflow.name}</h3>
                {catalog.subworkflows
                  .filter((item) => item.workflow_id === workflow.id)
                  .map((subworkflow) => (
                    <section
                      className="wd-group"
                      key={`${workflow.id}/${subworkflow.id}`}
                      data-testid="workflow-demo-pool-group"
                      data-variant={subworkflow.id}
                    >
                      <h4>{subworkflow.name}</h4>
                      {subworkflow.stages.map((stage) => (
                        <button
                          type="button"
                          key={stage.id}
                          className="wd-pool-card"
                          data-testid="workflow-demo-pool-card"
                          data-variant={stage.id}
                          aria-pressed={stageId === stage.id}
                          data-selection={
                            displayRun?.nodes.some((node) => node.stage_id === stage.id) ? 'selected' : 'idle'
                          }
                          onClick={() => {
                            setStageId(stage.id);
                            setSelected('');
                          }}
                        >
                          {stage.name}
                        </button>
                      ))}
                    </section>
                  ))}
              </section>
            ))}
          </div>
        </section>
        <section className="wd-panel wd-canvas-panel" aria-label={copy.canvas} data-testid="workflow-demo-canvas-panel">
          {!replay ? (
            <form className="wd-composer" onSubmit={(event) => void start(event)} data-testid="workflow-demo-task-form">
              <div className="wd-panel-heading">
                <h2>{copy.canvas}</h2>
                {run && <StatusDot status={run.status} />}
              </div>
              <a className="wd-repository" href={repository} target="_blank" rel="noreferrer">
                niko1221/strata
              </a>
              <label className="wd-task-label" htmlFor="factory-engineering-task">
                Engineering task
              </label>
              <textarea
                id="factory-engineering-task"
                className="wd-task-input"
                value={taskText}
                onChange={(event) => setTaskText(event.target.value)}
                aria-label="Engineering task"
                rows={6}
                data-testid="workflow-demo-engineering-task"
              />
              <div className="wd-goals" role="group" aria-label={copy.objective}>
                {availableGoals.map((kind) => (
                  <label key={kind}>
                    <input
                      type="checkbox"
                      checked={goals.includes(kind)}
                      onChange={(event) =>
                        setGoals((previous) =>
                          event.target.checked ? [...previous, kind] : previous.filter((item) => item !== kind),
                        )
                      }
                      data-testid="workflow-demo-goal"
                      data-variant={kind}
                    />
                    {copy.goals.find((goal) => goal.value === kind)?.label ?? kind}
                  </label>
                ))}
              </div>
              <div className="wd-run-fields">
                <input
                  aria-label={copy.revision}
                  placeholder={copy.revision}
                  value={revision}
                  onChange={(event) => setRevision(event.target.value)}
                  data-testid="workflow-demo-revision"
                />
                <select
                  aria-label={copy.backend}
                  value={backend}
                  onChange={(event) => setBackend(event.target.value as typeof backend)}
                  data-testid="workflow-demo-backend"
                >
                  <option value="ascend">Ascend Native</option>
                  <option value="cpu">CPU</option>
                  <option value="cuda">CUDA</option>
                </select>
                <input
                  aria-label={copy.model}
                  placeholder={copy.model}
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  data-testid="workflow-demo-model-path"
                />
                <Button
                  type="submit"
                  disabled={!catalog || (!goals.length && !taskText.trim()) || submitting || selectedRunActive}
                  data-testid="workflow-demo-run-button"
                >
                  {submitting || selectedRunActive ? copy.running : copy.run}
                </Button>
              </div>
              {!!(error || run?.error) && (
                <pre className="wd-error" role="alert" data-testid="workflow-demo-error">
                  {error || pretty(run?.error)}
                </pre>
              )}
              {run && (
                <div className="wd-run-navigation">
                  <code data-testid="workflow-demo-run-id">{run.id}</code>
                  <Button
                    size="sm"
                    disabled={!isTerminal(run.status) || !events.length || !!recording.error}
                    onClick={() => enterReplay()}
                    data-testid="workflow-demo-enter-replay"
                  >
                    Replay
                  </Button>
                  <select
                    aria-label={copy.history}
                    value=""
                    onChange={(event) => jumpToRevision(event.target.value)}
                    data-testid="workflow-demo-graph-revision"
                  >
                    <option value="">{copy.currentGraph}</option>
                    {run.graph_revisions.map((item) => (
                      <option key={item.revision} value={item.revision}>
                        Revision {item.revision}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </form>
          ) : (
            <>
              <ReplayControls
                runId={run?.id ?? runId}
                recordedTime={projection?.run?.replay.time ?? null}
                events={recording.events}
                cursor={projection?.run?.replay.cursor ?? 0}
                onCursorChange={seekReplay}
                onReturnLive={returnLive}
              />
              {!!(error || recording.error || projection?.error || displayRun?.error) && (
                <pre className="wd-error" role="alert" data-testid="workflow-demo-error">
                  {error || recording.error || projection?.error || pretty(displayRun?.error)}
                </pre>
              )}
            </>
          )}
          <Graph
            nodes={graphNodes}
            edges={graphEdges}
            artifacts={publishedArtifacts}
            selected={selectedNode?.id ?? selected}
            select={(id) => {
              setSelected(id);
              setStageId('');
            }}
          />
          {displayRun && deliverables.length > 0 && (
            <section className="wd-deliveries" data-testid="workflow-demo-deliverables">
              <h3>{copy.outputs}</h3>
              <ArtifactList runId={displayRun.id} artifacts={deliverables} />
            </section>
          )}
        </section>
        <aside className="wd-panel wd-detail" aria-label={copy.details} data-testid="workflow-demo-detail">
          <h2>{copy.details}</h2>
          {displayRun && codeDiffArtifact && <CodeDiffPanel runId={displayRun.id} artifact={codeDiffArtifact} />}
          {displayRun && valueReportArtifact && (
            <ValueReportPanel runId={displayRun.id} artifact={valueReportArtifact} />
          )}
          {currentRevision && (
            <section className="wd-replan-reason" data-testid="workflow-demo-replan-reason">
              <h3>Revision {currentRevision.revision}</h3>
              <p>{currentRevision.reason}</p>
            </section>
          )}
          {(selectedNode || selectedStage) && (
            <div className="wd-detail-title">
              <h3>{stageId ? selectedStage?.name : (selectedNode?.name ?? selectedStage?.name)}</h3>
              {selectedNode && !stageId && <StatusDot status={selectedNode.status} />}
            </div>
          )}
          {selectedStage && <ContractDetails stage={selectedStage} />}
          {displayRun && selectedNode && !stageId && (
            <ExecutionDetails run={displayRun} node={selectedNode} events={graphEvents} />
          )}
          {graphEvents.some((event) => event.type === 'command.output') && (
            <section className="wd-terminal" data-testid="workflow-demo-terminal">
              <h3>Terminal</h3>
              <pre>
                {graphEvents
                  .filter((event) => event.type === 'command.output')
                  .slice(-300)
                  .map(
                    (event) => `[${event.node_id} ${String(event.payload.stream)}] ${String(event.payload.text ?? '')}`,
                  )
                  .join('')}
              </pre>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
