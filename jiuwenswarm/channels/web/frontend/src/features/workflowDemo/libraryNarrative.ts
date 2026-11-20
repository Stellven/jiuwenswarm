import type { LibraryCheck, LibraryEvent, LibraryGraphNode, LibraryPart } from './libraryClient';

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
}

function filename(path: unknown): string | undefined {
  return typeof path === 'string' ? path.split(/[/\\]/).pop() : undefined;
}

export function expectedFileForPort(part: LibraryPart, side: 'inputs' | 'outputs', port: string): string | undefined {
  const entries = record(part.inspection)[side];
  if (!Array.isArray(entries)) return undefined;
  const entry = entries.map(record).find((item) => item.port === port);
  return filename(entry?.expected_filename);
}

export function componentOutcome(check: LibraryCheck): { label: string; value: string }[] {
  const report = check.verification;
  if (!report) return [];
  const rows: { label: string; value: string }[] = [];
  const cmake = check.command_records.filter((command) => /^cmake(?:\.exe)?$/.test(filename(command.argv?.[0]) || ''));
  const configure = cmake.find((command) => command.argv?.includes('-S') && command.argv.includes('-B'));
  const build = cmake.find((command) => command.argv?.includes('--build'));
  if (configure && build) {
    rows.push({
      label: 'CPU build',
      value: configure.exit_code === 0 && build.exit_code === 0 ? 'Completed' : 'Failed',
    });
  }
  const reference = record(report.original_source_reference);
  if (typeof reference.outputs_compared === 'number') {
    const passed = reference.status === 'verified' && reference.coverage_complete === true;
    rows.push({
      label: 'CPU comparisons with the reference',
      value: `${reference.outputs_compared} ${passed ? 'passed' : 'recorded'}`,
    });
    const checks = Array.isArray(reference.operation_checks) ? reference.operation_checks.map(record) : [];
    const errors = checks.flatMap((item) => (typeof item.max_abs_error === 'number' ? [item.max_abs_error] : []));
    if (errors.length) rows.push({ label: 'Largest measured difference', value: Math.max(...errors).toExponential(3) });
  }
  if (report.native_compilation === 'NOT_RUN') rows.push({ label: 'Build with Ascend tools', value: 'Not run' });
  if (report.native_device_validated === false) rows.push({ label: 'Run on Ascend hardware', value: 'Unverified' });
  if (report.full_inference_validated === false) rows.push({ label: 'Run the complete model', value: 'Unverified' });
  return rows;
}

export function recordedReferenceSources(check: LibraryCheck): string[] {
  const ids = record(check.verification?.original_source_reference).selected_source_ids;
  if (!Array.isArray(ids)) return [];
  return ids.filter((id): id is string => typeof id === 'string' && id.length > 0);
}

export function readSchedulerAssignment(value: unknown) {
  const { node_id, worker_type, builder, execution_reason } = record(value);
  if (typeof node_id !== 'string' || typeof worker_type !== 'string' || typeof builder !== 'string') return undefined;
  return { nodeId: node_id, workerType: worker_type, builder,
    reason: typeof execution_reason === 'string' ? execution_reason : undefined };
}

export function readSchedulerDispatch(event: LibraryEvent) {
  return event.type === 'scheduler.dispatched' ? readSchedulerAssignment(event.payload) : undefined;
}

export function schedulerNarrative(event: LibraryEvent, step?: string): string | undefined {
  if (event.type === 'scheduler.started') return 'Scheduler received the Task Graph';
  if (event.type === 'scheduler.assignments_ready') return 'Scheduler assigned an execution method to each step';
  if (event.type === 'scheduler.finished') return 'Scheduler finished dispatching steps';
  const dispatch = readSchedulerDispatch(event);
  if (dispatch) return `Assigned ${step ?? dispatch.nodeId} to ${dispatch.builder}`;
  return undefined;
}

/** Describe only actions and objects observed in the persisted event. */
export function eventNarrative(event: LibraryEvent, nodes: LibraryGraphNode[] = []): string | undefined {
  const payload = event.payload;
  const part = record(payload.subworkflow);
  const node = record(payload.node);
  const artifact = record(payload.artifact);
  const nodeName = (id: unknown) => nodes.find((item) => item.id === id)?.name;
  const step = nodeName(payload.node_id ?? event.node_id) || (typeof node.name === 'string' ? node.name : undefined);
  const file = filename(artifact.path);
  switch (event.type) {
    case 'import.subworkflow.created':
      return typeof part.name === 'string' ? `Created a reusable step: ${part.name}` : undefined;
    case 'import.completed':
      return typeof payload.project_id === 'string'
        ? `Saved the workflow definition for ${payload.project_id}`
        : undefined;
    case 'library.workflow_registered': {
      const workflow = record(payload.workflow);
      return typeof workflow.name === 'string' ? `Added ${workflow.name} to the library` : undefined;
    }
    case 'planner.model_requested':
      return 'Sent the request and available evidence to the planner';
    case 'planner.tool_finished':
      switch (payload.name) {
        case 'library.search':
          return 'Planner searched the library';
        case 'library.read':
          return 'Planner opened a saved workflow';
        case 'library.inspect_part':
          return 'Planner opened a reusable step';
        case 'library.read_source':
          return 'Planner opened a source file';
        default:
          return undefined;
      }
    case 'planner.graph_created':
      return 'Checked the planner’s choices and saved the task graph';
    case 'graph.validated':
      return 'Checked the steps and their input connections';
    case 'scheduler.started':
    case 'scheduler.assignments_ready':
    case 'scheduler.dispatched':
    case 'scheduler.finished':
      return schedulerNarrative(event, step);
    case 'node.started':
      return step ? `Started ${step}` : undefined;
    case 'node.verified':
      return step ? `Checked the files produced by ${step}` : undefined;
    case 'node.failed':
    case 'node.blocked':
      return step ? `${step} ${event.type === 'node.failed' ? 'failed' : 'could not run'}` : undefined;
    case 'artifact.consumed': {
      const source = nodeName(payload.producer ?? artifact.producer);
      return step && file ? `${step} received ${file}${source ? ` from ${source}` : ''}` : undefined;
    }
    case 'artifact.published':
      return step && file ? `${step} saved ${file}` : undefined;
    case 'source.project.generated':
      return 'Generated the C++ source project';
    case 'framework.built':
      return typeof payload.name === 'string' ? `Built ${payload.name}` : undefined;
    case 'run.verified':
      return 'Completed the recorded steps';
    default:
      return undefined;
  }
}
