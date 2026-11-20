import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Button } from '../../components/ui/Button/Button';
import { copy, userGoalSelection } from './copy.en';
import { factoryClient, isTerminal, parseEngineeringTask, pretty, statusColor } from './factoryClient';
import type {
  Artifact,
  FactoryCatalog,
  FactoryEdge,
  FactoryEvent,
  FactoryNode,
  FactoryRun,
  StageDeclaration,
  FactoryRecordingSummary,
  WorkflowLibrary,
} from './factoryClient';
import { edgeDeliveryStatus, edgePath, layoutGraph } from './graphLayout';
import { ReplayControls } from './ReplayControls';
import { ArtifactList, EvidencePanel } from './EvidencePanel';
import { CapabilityPool } from './CapabilityPool';
import {
  catalogFromStages,
  compositionCounts,
  nextRecordedCursor,
  nodeOperationIdentity,
  recordingTitle,
  requestScope,
  stageLabel,
  publishedSourceProducer,
  replayCheckpoints,
  nodePoolRef,
} from './presentationModel';
import { normalizeReplayEvents, projectReplay } from './replayProjection.js';
import { WorkflowLibraryDemo } from './WorkflowLibraryDemo';
import { GuidedFactoryReplay } from './GuidedFactoryReplay';
import { LiveFactoryWorkflow } from './LiveFactoryWorkflow';
import './workflow-demo.css';

const repository = 'https://github.com/niko1221/strata';
const runStorageKey = 'ai4research.factory.last-run';
const initialTask = JSON.stringify(
  {
    description:
      'Construct STRATA for Huawei Ascend Native, build it, execute model inference, and compare with the original.',
    capabilities: ['routing', 'activation', 'aggregation'],
    acceptance: {
      source_project: true,
      cpu_validation: true,
      full_model_inference: true,
      native_execution: true,
      compare_original: true,
    },
  },
  null,
  2,
);

function storedRunId(): string {
  try {
    const requested = new URLSearchParams(window.location.search).get('factoryRun');
    if (requested) return requested;
    return '';
  } catch {
    return '';
  }
}

function requestedRecording(): string {
  try {
    const query = new URLSearchParams(window.location.search);
    return query.get('recording') ?? query.get('factoryRecording') ?? '';
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

function ContractDetails({ stage }: { stage: StageDeclaration }) {
  return (
    <div className="wd-contract" data-testid="workflow-demo-stage-contract">
      <h3>Canonical stage contract</h3>
      <dl className="wd-lineage" data-testid="workflow-demo-contract-lineage">
        <dt>Workflow</dt>
        <dd>{stage.workflow_id}</dd>
        <dt>Sub-workflow</dt>
        <dd>{stage.subworkflow_id}</dd>
        <dt>Stage</dt>
        <dd>{stage.id}</dd>
      </dl>
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

function ExecutionDetails({
  run,
  node,
  events,
  recordingId,
}: {
  run: FactoryRun;
  node: FactoryNode;
  events: FactoryEvent[];
  recordingId?: string;
}) {
  const origin = nodePoolRef(node).split('/');
  return (
    <div data-testid="workflow-demo-node-execution">
      <dl className="wd-lineage" data-testid="workflow-demo-node-lineage">
        <dt>Workflow</dt>
        <dd data-testid="workflow-demo-node-workflow">{origin[0] || node.workflow_id}</dd>
        <dt>Sub-workflow</dt>
        <dd data-testid="workflow-demo-node-subworkflow">{origin[1] || node.subworkflow_id}</dd>
        <dt>Stage</dt>
        <dd data-testid="workflow-demo-node-stage">{origin[2] || node.stage_id}</dd>
        <dt>Canonical stage ID</dt>
        <dd data-testid="workflow-demo-node-canonical-stage">{node.stage_id}</dd>
        <dt>Instance</dt>
        <dd data-testid="workflow-demo-node-instance">{node.instance_id || node.instance_key || node.id}</dd>
        {nodePoolRef(node) && (
          <>
            <dt>Selected internal path</dt>
            <dd data-testid="workflow-demo-node-origin">{nodePoolRef(node)}</dd>
          </>
        )}
        {nodeOperationIdentity(node, run) && (
          <>
            <dt>Source function</dt>
            <dd data-testid="workflow-demo-node-operation">{nodeOperationIdentity(node, run)}</dd>
          </>
        )}
      </dl>
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
              <ArtifactList runId={run.id} artifacts={attempt.inputs} recordingId={recordingId} />
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
              <ArtifactList runId={run.id} artifacts={attempt.outputs} recordingId={recordingId} />
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
  const scroll = useRef<HTMLDivElement>(null);
  const previousFollow = useRef('');
  useEffect(() => {
    const previous = previousFollow.current;
    previousFollow.current = selected;
    if (previous === selected || !selected) return;
    const container = scroll.current;
    const node = Array.from(
      container?.querySelectorAll<HTMLButtonElement>('[data-testid="workflow-demo-node"]') ?? [],
    ).find((element) => element.dataset.variant === selected);
    if (!container || !node) return;
    const nodeBox = node.getBoundingClientRect();
    const viewport = container.getBoundingClientRect();
    container.scrollTop = Math.max(
      0,
      container.scrollTop + nodeBox.top - viewport.top - (container.clientHeight - nodeBox.height) / 2,
    );
  }, [selected]);
  return (
    <div ref={scroll} className="wd-graph-scroll" data-testid="workflow-demo-graph">
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
                <span>{stageLabel(node)}</span>
                <StatusDot status={node.status} />
              </button>
            </foreignObject>
          );
        })}
      </svg>
    </div>
  );
}

function RecordedWorkflowDemo() {
  const [catalog, setCatalog] = useState<FactoryCatalog | null>(null);
  const [recordedCatalog, setRecordedCatalog] = useState<FactoryCatalog | null>(null);
  const [recordedLibrary, setRecordedLibrary] = useState<WorkflowLibrary | null>(null);
  const [recordings, setRecordings] = useState<FactoryRecordingSummary[]>([]);
  const [loadingRecordingList, setLoadingRecordingList] = useState(true);
  const [recordingId, setRecordingId] = useState(requestedRecording);
  const [showEngineeringTask, setShowEngineeringTask] = useState(() => Boolean(storedRunId()));
  const navigationChosen = useRef(false);
  const [loadingRecording, setLoadingRecording] = useState(false);
  const [runId, setRunId] = useState(storedRunId);
  const [run, setRun] = useState<FactoryRun | null>(null);
  const [events, setEvents] = useState<FactoryEvent[]>([]);
  const [selected, setSelected] = useState('');
  const [stageId, setStageId] = useState('');
  const [poolRef, setPoolRef] = useState('');
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
  const [playing, setPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(4);
  const [inspectedRevision, setInspectedRevision] = useState<number | null>(null);
  const replayStream = useRef<AbortController | null>(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const mounted = useRef(true);
  const pauseReplay = useCallback(() => {
    replayStream.current?.abort();
    replayStream.current = null;
    setPlaying(false);
  }, []);

  useEffect(
    () => () => {
      replayStream.current?.abort();
      replayStream.current = null;
    },
    [recordingId, runId],
  );

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
    const controller = new AbortController();
    void factoryClient
      .recordings(controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setRecordings(value.recordings);
        const hasRequestedRun = new URLSearchParams(window.location.search).has('factoryRun');
        if (!navigationChosen.current && !hasRequestedRun && !requestedRecording() && value.recordings.length) {
          setRun(null);
          setEvents([]);
          setRecordingId(value.recordings[0].id);
          setReplay(true);
        }
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(String(failure));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingRecordingList(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!recordingId) return;
    const controller = new AbortController();
    setLoadingRecording(true);
    setError('');
    void factoryClient
      .recording(recordingId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setRun(value.run);
        setRunId(value.run.id);
        setEvents(value.events);
        setRecordedCatalog(catalogFromStages(value.catalog));
        setRecordedLibrary(value.workflow_catalog || value.run.workflow_catalog || null);
        setSelected('');
        setStageId('');
        setPoolRef('');
        setReplayCursor(0);
        setReplay(true);
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(String(failure));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingRecording(false);
      });
    return () => controller.abort();
  }, [recordingId]);

  useEffect(() => {
    if (!runId || recordingId) return;
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
  }, [runId, replay, recordingId]);

  const start = async (event: FormEvent) => {
    event.preventDefault();
    if (recordingId || replay || (!goals.length && !taskText.trim()) || submitting) return;
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
      setPoolRef('');
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
  const checkpoints = useMemo(() => replayCheckpoints(recording.events), [recording.events]);
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
  const seekReplay = useCallback(
    (cursor: number) => {
      pauseReplay();
      setReplayCursor(cursor);
      setSelected(
        run && cursor === recording.events.length
          ? publishedSourceProducer(projectReplay(run, recording.events, cursor))
          : '',
      );
      setStageId('');
      setPoolRef('');
      setInspectedRevision(null);
    },
    [pauseReplay, run, recording.events],
  );
  const playReplay = (speed: number) => {
    if (!recordingId || !run || recording.error || replayCursor >= recording.events.length) return;
    pauseReplay();
    const controller = new AbortController();
    replayStream.current = controller;
    setPlaying(true);
    setInspectedRevision(null);
    setError('');
    let position = replayCursor;
    const after = recording.events[position - 1]?.sequence ?? 0;
    const checkpoint = checkpoints.find((item) => item.cursor > position);
    const stopCursor = checkpoint?.cursor ?? recording.events.length;
    const until = checkpoint?.sequence ?? recording.events[recording.events.length - 1]?.sequence ?? 0;
    void factoryClient
      .replay(
        recordingId,
        after,
        speed,
        (frame) => {
          if (controller.signal.aborted || replayStream.current !== controller) return;
          if (frame.event !== 'recorded') throw new Error('Invalid recorded replay stream frame');
          position = nextRecordedCursor(recording.events, position, frame.data);
          if (position > stopCursor) throw new Error('Replay stream passed the selected publication checkpoint');
          setReplayCursor(position);
          setSelected(
            position === recording.events.length
              ? publishedSourceProducer(projectReplay(run, recording.events, position))
              : '',
          );
          setStageId('');
          setPoolRef('');
        },
        controller.signal,
        until,
      )
      .then(() => {
        if (!controller.signal.aborted && position !== stopCursor)
          throw new Error('Replay stream ended before the selected publication checkpoint');
      })
      .catch((failure) => {
        if (!controller.signal.aborted && replayStream.current === controller) setError(String(failure));
      })
      .finally(() => {
        if (replayStream.current === controller) {
          replayStream.current = null;
          setPlaying(false);
        }
      });
  };
  const enterReplay = (cursor = 0) => {
    setError('');
    seekReplay(cursor);
    setReplay(true);
  };
  const returnLive = () => {
    pauseReplay();
    if (recordingId) {
      newTask();
      return;
    }
    setReplay(false);
    setSelected('');
    setStageId('');
    setPoolRef('');
    try {
      const url = new URL(window.location.href);
      url.searchParams.delete('replay');
      window.history.replaceState(window.history.state, '', url);
    } catch {
      /* Replay state does not require URL storage. */
    }
  };
  const newTask = () => {
    navigationChosen.current = true;
    setShowEngineeringTask(true);
    pauseReplay();
    setRecordingId('');
    setRunId('');
    setRun(null);
    setEvents([]);
    setReplay(false);
    setSelected('');
    setStageId('');
    setPoolRef('');
    setInspectedRevision(null);
    setTaskText(initialTask);
    setBackend('ascend');
    setGoals(['construction.package', 'value.report', 'inference.result', 'verification.comparison']);
    setRevision('');
    setModel('');
    setError('');
    const url = new URL(window.location.href);
    url.searchParams.delete('recording');
    url.searchParams.delete('factoryRecording');
    url.searchParams.delete('factoryRun');
    url.searchParams.delete('replay');
    window.history.replaceState(window.history.state, '', url);
  };
  const openRecording = (id: string) => {
    navigationChosen.current = true;
    if (id === recordingId) return;
    pauseReplay();
    setRun(null);
    setRunId('');
    setRecordedCatalog(null);
    setRecordedLibrary(null);
    setEvents([]);
    setSelected('');
    setStageId('');
    setPoolRef('');
    setInspectedRevision(null);
    setReplayCursor(0);
    setReplay(true);
    setShowEngineeringTask(false);
    setRecordingId(id);
    const url = new URL(window.location.href);
    url.searchParams.set('view', 'workflow');
    url.searchParams.set('recording', id);
    url.searchParams.delete('factoryRecording');
    url.searchParams.delete('factoryRun');
    url.searchParams.set('replay', '1');
    window.history.replaceState(window.history.state, '', url);
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
    setInspectedRevision(Number(revisionNumber));
  };
  const displayCatalog = recordingId ? recordedCatalog : catalog;
  const workflowLibrary = recordingId ? recordedLibrary : run?.workflow_catalog;
  const inspectedPoolStage = workflowLibrary?.stage_refs.find((reference) => reference.path === poolRef);
  const sourceOnlyTask =
    !!run?.request.goals.includes('construction.native_sources') &&
    run.request.goals.every((goal) => ['construction.native_sources', 'construction.cpu_validation'].includes(goal)) &&
    !run.request.task?.acceptance.native_execution &&
    !run.request.task?.acceptance.full_model_inference;
  const selectedStage = displayCatalog?.stages.find((stage) => stage.id === (stageId || selectedNode?.stage_id));
  const selectedRunActive = !!run && !isTerminal(run.status);
  const availableGoals = (catalog?.goals ?? []).filter((kind) => copy.goals.some((goal) => goal.value === kind));
  const publishedArtifacts = Array.isArray(displayRun?.artifacts) ? displayRun.artifacts : [];
  const counts = compositionCounts(graphNodes);

  return (
    <div
      className="wd-app flex-1 min-h-0 min-w-0"
      data-testid="workflow-demo"
      data-run-id={displayRun?.id ?? runId}
      data-status={displayRun?.status ?? ''}
      data-mode={replay ? 'replay' : 'live'}
      data-recording-id={recordingId}
    >
      <header className="wd-header">
        <h1 data-testid="workflow-demo-title">{copy.title}</h1>
      </header>
      <div className="wd-layout">
        <CapabilityPool
          catalog={displayCatalog}
          run={displayRun}
          nodes={graphNodes}
          library={workflowLibrary}
          selected={poolRef || (selectedNode && nodePoolRef(selectedNode)) || stageId || ''}
          onSelect={(id, fullRef) => {
            setStageId(id);
            setPoolRef(fullRef || '');
            setSelected('');
          }}
          onRefresh={() => void loadCatalog()}
        />
        <section className="wd-panel wd-canvas-panel" aria-label={copy.canvas} data-testid="workflow-demo-canvas-panel">
          <div className="wd-recording-navigation" data-testid="workflow-demo-recording-navigation">
            <label htmlFor="factory-recording" data-testid="workflow-demo-recording-label">
              Saved run
            </label>
            <select
              id="factory-recording"
              value={recordingId}
              onChange={(event) => (event.target.value ? openRecording(event.target.value) : newTask())}
              data-testid="workflow-demo-recording-selector"
            >
              <option value="" disabled={!showEngineeringTask}>
                {showEngineeringTask ? 'New engineering task' : 'Choose a saved run'}
              </option>
              {recordings.map((item) => (
                <option
                  key={item.id}
                  value={item.id}
                  data-testid="workflow-demo-recording-option"
                  data-variant={item.id}
                >
                  {recordingTitle(item)} ·{' '}
                  {item.request.goals.includes('construction.native_sources')
                    ? 'source recording'
                    : item.request.target_backend.toUpperCase()}{' '}
                  · {item.status}
                </option>
              ))}
            </select>
            <Button size="sm" onClick={newTask} data-testid="workflow-demo-new-task">
              Open new engineering task
            </Button>
          </div>
          {replay && run ? (
            <section className="wd-recorded-request" data-testid="workflow-demo-recorded-input">
              <h3 data-testid="workflow-demo-recorded-input-title">Recorded request</h3>
              <p className="wd-task-description" data-testid="workflow-demo-recorded-task">
                {run.request.task?.description || run.request.goals.join(', ')}
              </p>
              <dl className="wd-request-fields">
                {recordingId && (
                  <div>
                    <dt>Recorded run</dt>
                    <dd data-testid="workflow-demo-recorded-run-identity">
                      <code>{run.id}</code>
                      {' · '}
                      {new Date(run.created_at).toLocaleString()}
                    </dd>
                  </div>
                )}
                <div>
                  <dt>Input source</dt>
                  <dd data-testid="workflow-demo-recorded-source-role">
                    {run.request.task?.source_scope?.some((scope) => /cuda|\.cuh?\b/i.test(scope))
                      ? 'STRATA CUDA'
                      : 'STRATA source'}
                  </dd>
                </div>
                <div>
                  <dt>Recorded target</dt>
                  <dd data-testid="workflow-demo-recorded-target">{run.request.target_backend.toUpperCase()}</dd>
                </div>
                {run.request.task?.acceptance.cpu_validation && (
                  <div>
                    <dt>Source validation</dt>
                    <dd data-testid="workflow-demo-recorded-cpu-role">CPU checks requested</dd>
                  </div>
                )}
                {typeof run.request.options?.reference_backend === 'string' &&
                  (run.request.task?.acceptance.compare_original ||
                    run.request.goals.includes('verification.comparison')) && (
                    <div>
                      <dt>Original reference</dt>
                      <dd data-testid="workflow-demo-recorded-reference-role">
                        {run.request.options.reference_backend.toUpperCase()} (configured)
                      </dd>
                    </div>
                  )}
                <div>
                  <dt>Capabilities</dt>
                  <dd data-testid="workflow-demo-recorded-capabilities">
                    {run.request.task?.capabilities?.join(', ') || '—'}
                  </dd>
                </div>
                <div className="wd-request-scope">
                  <dt>Source scope</dt>
                  <dd data-testid="workflow-demo-recorded-source-scope">
                    {run.request.task?.source_scope?.join(', ') || '—'}
                  </dd>
                </div>
                <div className="wd-request-acceptance">
                  <dt>Acceptance</dt>
                  <dd data-testid="workflow-demo-recorded-acceptance">{requestScope(run.request)}</dd>
                  {sourceOnlyTask && (
                    <dd className="wd-native-source-scope" data-testid="workflow-demo-recorded-native-scope">
                      Source generation and CPU reference; native compile, device and model execution not requested
                    </dd>
                  )}
                </div>
                <div>
                  <dt>Repository</dt>
                  <dd>
                    <a
                      href={run.request.repository_url}
                      target="_blank"
                      rel="noreferrer"
                      data-testid="workflow-demo-recorded-repository"
                    >
                      {run.request.repository_url.replace('https://github.com/', '')}
                    </a>
                  </dd>
                </div>
              </dl>
            </section>
          ) : showEngineeringTask && !recordingId && !replay ? (
            <form className="wd-composer" onSubmit={(event) => void start(event)} data-testid="workflow-demo-task-form">
              <label
                className="wd-task-label"
                htmlFor="factory-engineering-task"
                data-testid="workflow-demo-task-label"
              >
                Engineering task
              </label>
              <textarea
                id="factory-engineering-task"
                className="wd-task-input"
                value={taskText}
                onChange={(event) => setTaskText(event.target.value)}
                aria-label="Engineering task"
                rows={3}
                data-testid="workflow-demo-engineering-task"
              />
              <div className="wd-run-fields">
                <a
                  className="wd-repository"
                  href={repository}
                  target="_blank"
                  rel="noreferrer"
                  data-testid="workflow-demo-repository"
                >
                  niko1221/strata
                </a>
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
                  aria-label={copy.revision}
                  placeholder={copy.revision}
                  value={revision}
                  onChange={(event) => setRevision(event.target.value)}
                  data-testid="workflow-demo-revision"
                />
                <input
                  aria-label={copy.model}
                  placeholder={copy.model}
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  data-testid="workflow-demo-model-path"
                />
              </div>
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
              <Button
                type="submit"
                disabled={!catalog || (!goals.length && !taskText.trim()) || submitting || selectedRunActive}
                data-testid="workflow-demo-run-button"
              >
                {submitting || selectedRunActive ? copy.running : copy.run}
              </Button>
              {run && (
                <Button
                  size="sm"
                  disabled={!isTerminal(run.status) || !events.length || !!recording.error}
                  onClick={() => enterReplay()}
                  data-testid="workflow-demo-enter-replay"
                >
                  Replay
                </Button>
              )}
            </form>
          ) : null}
          {loadingRecording && (
            <p className="wd-loading" role="status" data-testid="workflow-demo-recording-loading">
              Loading recording
            </p>
          )}
          {!showEngineeringTask && !run && !loadingRecording && !recordings.length && !error && (
            <p className="wd-loading" role="status" data-testid="workflow-demo-opening-recordings">
              {loadingRecordingList ? 'Opening saved factory records' : 'No saved factory runs available'}
            </p>
          )}
          {replay && run && (
            <ReplayControls
              key={recordingId || run.id}
              runId={run.id}
              recordedTime={projection?.run?.replay.time ?? null}
              events={recording.events}
              cursor={projection?.run?.replay.cursor ?? 0}
              onCursorChange={seekReplay}
              onPlay={playReplay}
              onPause={pauseReplay}
              playing={playing}
              canPlay={!!recordingId && !loadingRecording && !recording.error}
              playbackSpeed={playbackSpeed}
              onSpeedChange={setPlaybackSpeed}
              checkpoints={checkpoints}
              onReturnLive={returnLive}
              returnLabel={recordingId ? 'New task' : 'Return to live'}
            />
          )}
          {!!(error || recording.error || projection?.error || displayRun?.error) && (
            <pre className="wd-error" role="alert" data-testid="workflow-demo-error">
              {error || recording.error || projection?.error || pretty(displayRun?.error)}
            </pre>
          )}
          <div className="wd-graph-heading" data-testid="workflow-demo-graph-heading">
            <h2 data-testid="workflow-demo-canvas-title">{copy.canvas}</h2>
            {(run || showEngineeringTask) && (
              <span data-testid="workflow-demo-composition-counts">
                {counts.workflows} workflows · {counts.subworkflows} sub-workflows · {counts.stages} stages ·{' '}
                {counts.implementations} lowering instances
              </span>
            )}
            {displayRun && (
              <span className="wd-run-status" data-testid="workflow-demo-run-status">
                <StatusDot status={displayRun.status} />
                {sourceOnlyTask && displayRun.status === 'completed' ? 'Source complete' : displayRun.status}
              </span>
            )}
            {run && (
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
            )}
          </div>
          <Graph
            nodes={graphNodes}
            edges={graphEdges}
            artifacts={publishedArtifacts}
            selected={selectedNode?.id ?? selected}
            select={(id) => {
              setSelected(id);
              setStageId('');
              setPoolRef('');
            }}
          />
          {(run || showEngineeringTask) && (
            <EvidencePanel
              run={displayRun}
              events={graphEvents}
              recordingId={recordingId || undefined}
              catalog={displayCatalog}
              library={workflowLibrary}
              selected={selectedNode?.id ?? ''}
              onSelectNode={(id) => {
                setSelected(id);
                setStageId('');
                setPoolRef('');
              }}
            />
          )}
        </section>
        <aside className="wd-panel wd-detail" aria-label={copy.details} data-testid="workflow-demo-detail">
          <h2 data-testid="workflow-demo-detail-title">{copy.details}</h2>
          {currentRevision && inspectedRevision === currentRevision.revision && (
            <section className="wd-replan-reason" data-testid="workflow-demo-replan-reason">
              <h3>Revision {currentRevision.revision}</h3>
              <p>{currentRevision.reason}</p>
            </section>
          )}
          {(selectedNode || selectedStage) && (
            <div className="wd-detail-title">
              <h3 data-testid="workflow-demo-selected-stage">
                {stageId ? selectedStage?.name : (selectedNode?.name ?? selectedStage?.name)}
              </h3>
              {selectedNode && !stageId && <StatusDot status={selectedNode.status} />}
            </div>
          )}
          {displayRun && selectedNode && !stageId && (
            <ExecutionDetails
              run={displayRun}
              node={selectedNode}
              events={graphEvents}
              recordingId={recordingId || undefined}
            />
          )}
          {inspectedPoolStage && (
            <section data-testid="workflow-demo-inspected-pool-stage">
              <h3>Pool internal stage</h3>
              <p data-testid="workflow-demo-inspected-pool-ref">{inspectedPoolStage.path}</p>
              <dl className="wd-lineage">
                <dt>Parent definition</dt>
                <dd>{inspectedPoolStage.pool_origin.parent_definition_id}</dd>
                <dt>Definition SHA-256</dt>
                <dd>{inspectedPoolStage.pool_origin.parent_definition_hash}</dd>
                <dt>Other internal children</dt>
                <dd>{inspectedPoolStage.pool_origin.all_sibling_refs.join(', ') || 'None'}</dd>
              </dl>
            </section>
          )}
          {selectedStage && <ContractDetails stage={selectedStage} />}
        </aside>
      </div>
    </div>
  );
}

export function WorkflowDemo() {
  const libraryParameters = ['libraryExecution', 'libraryPlan', 'libraryCheck', 'libraryImport'];
  const recordingParameters = ['recording', 'factoryRecording', 'replay', 'factoryRun'];
  type WorkspaceView = 'live' | 'guided' | 'library' | 'recording';
  const [view, setView] = useState<WorkspaceView>(() => {
    const query = new URLSearchParams(window.location.search);
    if (query.has('workflowBuild')) return 'live';
    if (libraryParameters.some((parameter) => query.has(parameter))) return 'library';
    if (requestedRecording() || requestedReplay() || query.has('factoryRun')) return 'recording';
    const selected = query.get('workflowMode');
    return selected === 'live' || selected === 'recording' || selected === 'guided' ? selected : 'library';
  });
  const openView = (target: WorkspaceView) => {
    if (target === view) return;
    const url = new URL(window.location.href);
    if (target !== 'library') libraryParameters.forEach((parameter) => url.searchParams.delete(parameter));
    if (target !== 'recording') recordingParameters.forEach((parameter) => url.searchParams.delete(parameter));
    if (target !== 'live') url.searchParams.delete('workflowBuild');
    if (target === 'library') url.searchParams.delete('workflowMode');
    else url.searchParams.set('workflowMode', target);
    window.history.replaceState(window.history.state, '', url);
    setView(target);
  };
  return (
    <div className="wd-workspace" data-testid="workflow-demo-workspace">
      <nav
        className="wd-workspace-navigation"
        aria-label="Factory workspace"
        data-testid="workflow-demo-workspace-navigation"
      >
        <Button
          size="sm"
          aria-pressed={view === 'live'}
          onClick={() => openView('live')}
          data-testid="workflow-demo-workspace-live"
        >
          STRATA build
        </Button>
        <Button
          size="sm"
          aria-pressed={view === 'guided'}
          onClick={() => openView('guided')}
          data-testid="workflow-demo-workspace-guided"
        >
          Guided example
        </Button>
        <Button
          size="sm"
          aria-pressed={view === 'library'}
          onClick={() => openView('library')}
          data-testid="workflow-demo-workspace-library"
        >
          Workflow Library
        </Button>
        <Button
          size="sm"
          aria-pressed={view === 'recording'}
          onClick={() => openView('recording')}
          data-testid="workflow-demo-workspace-recording"
        >
          Previous factory recordings
        </Button>
      </nav>
      {view === 'live' && <LiveFactoryWorkflow />}
      {view === 'guided' && <GuidedFactoryReplay />}
      {view === 'library' && <WorkflowLibraryDemo />}
      {view === 'recording' && <RecordedWorkflowDemo />}
    </div>
  );
}
