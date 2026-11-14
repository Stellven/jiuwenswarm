import type { Artifact, FactoryEdge, FactoryEvent, FactoryNode, FactoryRun } from './factoryClient';

export interface ReplayPosition {
  cursor: number;
  event_count: number;
  time: string | null;
  elapsed_ms: number;
  duration_ms: number;
  recorded_status: string;
}

export type ReplayRun = FactoryRun & { replay: ReplayPosition };
/** Validate a complete recording in original sequence order; never reorder it. */
export function normalizeReplayEvents(events: FactoryEvent[]): FactoryEvent[];
/** Recorded milliseconds from the first event, index is zero based. */
export function eventOffset(events: FactoryEvent[], index: number): number;
export function replayDuration(events: FactoryEvent[]): number;
export function replayEdgeStatus(
  edge: FactoryEdge,
  run: { nodes?: FactoryNode[]; artifacts?: Artifact[] },
): 'pending' | 'running' | 'verified' | 'failed';
/** cursor is a prefix event count, from zero through events.length. */
export function projectReplay(run: FactoryRun, events: FactoryEvent[], cursor?: number): ReplayRun;
