import type { WorkflowRun, WorkflowStatus } from './workflowTypes';
import type { ResearchRef } from '../../utils/researchClient';

export interface ResearchStatus {
  run_id: string;
  client_request_id: string;
  revision: number;
  status: string;
  stage: string;
  candidate_refs: ResearchRef[];
  accepted_refs: ResearchRef[];
  reasons: string[];
  node_statuses: {
    node_id: string;
    attempt_id: string | null;
    lifecycle_status: string;
    skipped_because: string | null;
  }[];
}

/** Display-only original status details, without interpreting a scientific verdict. */
export function researchExecutionDetails(value: Pick<ResearchStatus, 'stage' | 'reasons'>): {
  stage: string | null;
  reasons: string[];
} {
  return {
    stage: typeof value.stage === 'string' && value.stage.trim() ? value.stage : null,
    reasons:
      Array.isArray(value.reasons) && value.reasons.every((reason) => typeof reason === 'string')
        ? [...value.reasons]
        : [],
  };
}

export function projectResearchWorkflow(value: ResearchStatus): WorkflowRun {
  const lifecycle: Record<string, WorkflowStatus> = {
    Pending: 'pending',
    Running: 'running',
    Evaluating: 'running',
    Completed: 'completed',
    Failed: 'failed',
  };
  const status: WorkflowStatus =
    value.status === 'in_progress'
      ? 'running'
      : value.status === 'completed'
        ? 'completed'
        : value.status === 'paused'
          ? 'paused'
          : value.status === 'cancelled'
            ? 'stopped'
            : 'failed';
  return {
    id: value.run_id,
    name: value.run_id,
    summary: value.stage,
    status,
    // This view has dedicated protected cancellation. Legacy workflow control
    // RPCs are unavailable for research, including after reload.
    recovered: true,
    research: { ...value },
    agent_count: value.node_statuses.length,
    completed_agent_count: value.node_statuses.filter((node) => node.lifecycle_status === 'Completed').length,
    phases: value.node_statuses.map((node) => ({
      id: node.node_id,
      name: node.node_id,
      description: node.lifecycle_status,
      status: lifecycle[node.lifecycle_status] ?? 'failed',
      agent_count: 1,
      completed_agent_count: node.lifecycle_status === 'Completed' ? 1 : 0,
      agents: [
        {
          id: node.attempt_id ?? node.node_id,
          name: node.node_id,
          status: lifecycle[node.lifecycle_status] ?? 'failed',
          outcome: node.lifecycle_status,
          ...(node.skipped_because ? { error: node.skipped_because } : {}),
        },
      ],
    })),
    ...(value.reasons.length ? { error: value.reasons.join('\n') } : {}),
  };
}
