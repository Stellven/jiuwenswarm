import { useEffect, useRef, useState } from 'react';
import type { Artifact, CommandRecord, FactoryEvent, FactoryRun } from './factoryClient';
import { factoryClient } from './factoryClient';
import './execution-log.css';

const activityLabels: Record<string, string> = {
  'stage.started': 'Stage started',
  'stage.verified': 'Stage verified',
  'stage.failed': 'Stage failed',
  'stage.blocked': 'Stage blocked',
  'workflow.expanded': 'Workflow expanded',
  'implementation.selected': 'Implementation selected',
};

export function ExecutionLog({
  run,
  events,
  recordingId,
  onSelectNode,
}: {
  run: FactoryRun;
  events: FactoryEvent[];
  recordingId?: string;
  onSelectNode?: (id: string) => void;
}) {
  const [selection, setSelection] = useState('');
  const [error, setError] = useState('');
  const urls = useRef(new Set<string>());
  useEffect(() => {
    const active = urls.current;
    return () => {
      active.forEach((url) => URL.revokeObjectURL(url));
      active.clear();
    };
  }, []);
  const groups = run.nodes.flatMap((node) =>
    node.attempts
      .filter((attempt) => attempt.commands.length)
      .map((attempt) => ({
        node,
        attempt,
        commands: attempt.commands.map((command, index) => ({
          key: `${node.id}/${attempt.number}/${index + 1}`,
          node,
          attempt,
          command,
          index: index + 1,
        })),
      })),
  );
  const commands = groups.flatMap((group) => group.commands);
  const declarations = new Map<string, { name?: string; entrypoint?: string }>();
  const activity = events
    .filter((event) => event.sequence <= run.sequence && activityLabels[event.type])
    .map((event) => {
      const stage = event.payload.stage;
      if (event.type === 'stage.started' && event.node_id && stage && typeof stage === 'object') {
        declarations.set(event.node_id, stage as { name?: string; entrypoint?: string });
      }
      const node = run.nodes.find((value) => value.id === event.node_id);
      const declaration = event.node_id ? declarations.get(event.node_id) : undefined;
      const path =
        event.type === 'workflow.expanded'
          ? event.payload.path
          : event.type === 'implementation.selected'
            ? event.payload.selected_ref
            : node?.workflow_path;
      const published =
        event.type === 'stage.verified' && Array.isArray(event.payload.outputs)
          ? (event.payload.outputs as Artifact[])
          : [];
      const outputs = published.flatMap((output) =>
        run.artifacts.filter(
          (artifact) => output.id === artifact.id && output.sha256 === artifact.sha256 && output.path === artifact.path,
        ),
      );
      return { event, node, declaration, path: typeof path === 'string' ? path : '', outputs };
    });
  const latest = commands.reduce<(typeof commands)[number] | undefined>(
    (previous, next) =>
      !previous || (next.command.started_at ?? '') >= (previous.command.started_at ?? '') ? next : previous,
    undefined,
  );
  const pinned = commands.find((item) => `${run.id}/${item.key}` === selection);
  const selected = pinned ?? latest;
  const command = selected?.command;
  const state = (value: CommandRecord) =>
    value.exit_code === null || value.exit_code === undefined ? 'Started' : `Exited ${value.exit_code}`;
  const downloads =
    command && selected
      ? run.artifacts.filter(
          (artifact) =>
            artifact.producer === selected.node.id &&
            ((artifact.kind === 'process.stdout' && artifact.path === command.stdout_path) ||
              (artifact.kind === 'process.stderr' && artifact.path === command.stderr_path)),
        )
      : [];
  const download = async (artifact: Artifact) => {
    try {
      setError('');
      const response = await factoryClient.artifact(run.id, artifact.id, recordingId);
      const url = URL.createObjectURL(await response.blob());
      urls.current.add(url);
      const link = document.createElement('a');
      link.href = url;
      link.download = artifact.path.split(/[\\/]/).pop() || artifact.id;
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (failure) {
      setError(String(failure));
    }
  };

  return (
    <section className="wd-execution-log" data-testid="workflow-demo-execution-log">
      <div className="wd-log-heading">
        <div>
          <h3 data-testid="workflow-demo-log-title">Process log</h3>
          <p data-testid="workflow-demo-log-summary">
            {commands.length} observed commands · Event {events[events.length - 1]?.sequence ?? 0}
          </p>
          <p data-testid="workflow-demo-log-worker">
            Recorded factory worker PID:{' '}
            <code data-testid="workflow-demo-log-worker-pid">{run.executor?.pid ?? 'Not recorded'}</code>
          </p>
        </div>
        <button
          type="button"
          onClick={() => setSelection('')}
          aria-pressed={!pinned}
          data-testid="workflow-demo-log-follow"
        >
          Follow latest
        </button>
      </div>
      <section className="wd-log-activity" data-testid="workflow-demo-log-stage-activity">
        <h4 data-testid="workflow-demo-log-activity-title">Stage activity</h4>
        {!activity.length && (
          <p data-testid="workflow-demo-log-activity-empty">No stage activity has been observed at this event.</p>
        )}
        <ol data-testid="workflow-demo-log-activity-list">
          {activity.map(({ event, node, declaration, path, outputs }) => (
            <li
              key={event.sequence}
              data-testid="workflow-demo-log-activity-item"
              data-variant={event.sequence}
              data-event-type={event.type}
              data-node={event.node_id ?? ''}
            >
              <div className="wd-log-activity-heading">
                <strong data-testid="workflow-demo-log-activity-kind">{activityLabels[event.type]}</strong>
                <time dateTime={event.time} data-testid="workflow-demo-log-activity-time">
                  {event.time}
                </time>
              </div>
              {node && (
                <button
                  type="button"
                  onClick={() => onSelectNode?.(node.id)}
                  data-testid="workflow-demo-log-activity-node"
                  data-variant={node.id}
                >
                  {declaration?.name ?? node.name} · {node.id}
                </button>
              )}
              {path && <code data-testid="workflow-demo-log-activity-ref">{path}</code>}
              {declaration?.entrypoint && (
                <code data-testid="workflow-demo-log-activity-entrypoint">{declaration.entrypoint}</code>
              )}
              {typeof event.payload.operation_id === 'string' && (
                <code data-testid="workflow-demo-log-activity-operation">{event.payload.operation_id}</code>
              )}
              {!!outputs.length && (
                <ul data-testid="workflow-demo-log-activity-outputs">
                  {outputs.map((artifact) => (
                    <li key={artifact.id}>
                      <a
                        href={factoryClient.artifactUrl(run.id, artifact.id, recordingId)}
                        onClick={(event) => {
                          event.preventDefault();
                          void download(artifact);
                        }}
                        title={artifact.path}
                        data-testid="workflow-demo-log-activity-output"
                        data-variant={artifact.id}
                        data-sha256={artifact.sha256}
                      >
                        {artifact.path.split(/[\\/]/).pop()} · {artifact.id} · {artifact.kind}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ol>
      </section>
      <h4 data-testid="workflow-demo-log-console-title">External process console</h4>
      {!commands.length && <p data-testid="workflow-demo-log-empty">No external command has started at this event.</p>}
      {!!commands.length && (
        <div className="wd-log-layout">
          <nav
            className="wd-log-command-list"
            aria-label="Observed processes"
            data-testid="workflow-demo-log-command-list"
          >
            {groups.map(({ node, attempt, commands: items }) => (
              <section
                key={`${node.id}/${attempt.number}`}
                data-testid="workflow-demo-log-group"
                data-variant={`${node.id}/${attempt.number}`}
              >
                <h4 data-testid="workflow-demo-log-group-title">
                  {node.name} <span>· Attempt {attempt.number}</span>
                </h4>
                <ol data-testid="workflow-demo-log-attempt-commands">
                  {items.map((item) => (
                    <li key={item.key} data-testid="workflow-demo-log-command-item" data-variant={item.key}>
                      <button
                        type="button"
                        aria-pressed={selected?.key === item.key}
                        onClick={() => {
                          setSelection(`${run.id}/${item.key}`);
                          onSelectNode?.(item.node.id);
                        }}
                        data-testid="workflow-demo-log-command"
                        data-variant={item.key}
                      >
                        <strong>
                          {item.index}. {item.command.argv[0]}
                        </strong>
                        <span>{state(item.command)}</span>
                      </button>
                    </li>
                  ))}
                </ol>
              </section>
            ))}
          </nav>
          {command && selected && (
            <section className="wd-log-process" data-testid="workflow-demo-log-process" data-command={selected.key}>
              <h4 data-testid="workflow-demo-log-process-title">
                {selected.node.name} · Attempt {selected.attempt.number} · Command {selected.index}
              </h4>
              <pre className="wd-log-argv" data-testid="workflow-demo-log-argv">
                {JSON.stringify(command.argv, null, 2)}
              </pre>
              <dl className="wd-log-metadata">
                <div>
                  <dt data-testid="workflow-demo-log-cwd-label">Working directory</dt>
                  <dd data-testid="workflow-demo-log-cwd">{command.cwd}</dd>
                </div>
                <div>
                  <dt data-testid="workflow-demo-log-start-label">Started</dt>
                  <dd data-testid="workflow-demo-log-start">{command.started_at ?? 'Not recorded'}</dd>
                </div>
                <div>
                  <dt data-testid="workflow-demo-log-finish-label">Finished</dt>
                  <dd data-testid="workflow-demo-log-finish">{command.finished_at ?? 'Not recorded at this event'}</dd>
                </div>
                <div>
                  <dt data-testid="workflow-demo-log-pid-label">PID</dt>
                  <dd data-testid="workflow-demo-log-pid">{command.pid ?? 'Not recorded at this event'}</dd>
                </div>
                <div>
                  <dt data-testid="workflow-demo-log-exit-label">Exit code</dt>
                  <dd data-testid="workflow-demo-log-exit">{command.exit_code ?? 'Not recorded at this event'}</dd>
                </div>
                <div>
                  <dt data-testid="workflow-demo-log-duration-label">Duration</dt>
                  <dd data-testid="workflow-demo-log-duration">
                    {command.duration_s === undefined ? 'Not recorded at this event' : `${command.duration_s} s`}
                  </dd>
                </div>
              </dl>
              {(['stdout', 'stderr'] as const).map((stream) => (
                <section className="wd-log-stream" key={stream}>
                  <h4 data-testid={`workflow-demo-log-${stream}-title`}>{stream}</h4>
                  <pre
                    tabIndex={0}
                    aria-label={`${stream} from command ${selected.index}`}
                    data-testid={`workflow-demo-log-${stream}`}
                  >
                    {command[stream] ?? ''}
                  </pre>
                </section>
              ))}
              {!!downloads.length && (
                <section className="wd-log-downloads" data-testid="workflow-demo-log-downloads">
                  <h4 data-testid="workflow-demo-log-download-title">Published full logs</h4>
                  {downloads.map((artifact) => {
                    const stream = artifact.kind === 'process.stdout' ? 'stdout' : 'stderr';
                    return (
                      <div
                        key={`${artifact.id}/${artifact.sha256}`}
                        data-testid="workflow-demo-log-file"
                        data-variant={artifact.id}
                      >
                        <a
                          href={factoryClient.artifactUrl(run.id, artifact.id, recordingId)}
                          onClick={(event) => {
                            event.preventDefault();
                            void download(artifact);
                          }}
                          data-testid="workflow-demo-log-download"
                          data-variant={stream}
                          data-artifact-id={artifact.id}
                          data-sha256={artifact.sha256}
                        >
                          Download complete {stream} · {artifact.size.toLocaleString()} bytes
                        </a>
                        <code data-testid="workflow-demo-log-file-path">{artifact.path}</code>
                        <code data-testid="workflow-demo-log-file-hash">SHA-256 {artifact.sha256}</code>
                      </div>
                    );
                  })}
                </section>
              )}
              {error && (
                <p role="alert" data-testid="workflow-demo-log-error">
                  {error}
                </p>
              )}
            </section>
          )}
        </div>
      )}
    </section>
  );
}
