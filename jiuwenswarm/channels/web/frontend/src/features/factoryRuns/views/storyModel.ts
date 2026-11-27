import type { CorrectionEvent, EvidenceFile, NodeCorrection, StoryEvent } from '../api';
import { replayLabel, revisionEvent } from './nodeEvidenceModel.ts';

export type KeyFile = { path: string; label: string; why?: string; step?: number };
export type CuratedMeasurement = {
  baseline: string;
  accuracy: { reference_pct?: number; candidate_pct?: number; loss_pts: number; lo_pts: number; hi_pts: number; n: number; path: string };
  rows: {
    arm: string;
    request: string;
    state: string;
    repeat?: number;
    prompt_tokens: number;
    generated_tokens?: number;
    ttft_ms: number;
    decode_tps: number;
    total_ms: number;
    status: string;
    reasons: string[];
    path: string;
    pointer: string;
  }[];
};
export type CuratedStep = {
  step: number;
  presentation_title: string;
  original_kind: string;
  summary?: string;
  say?: string;
  branch?: string;
  event_cursor?: number;
  key_files: KeyFile[];
  original_summary?: string;
  created_utc?: string;
  created?: number;
  quotes?: { path: string; line: number; text: string }[];
  records?: { table: string; id: string; source_home: string; task_id?: string }[];
  graph_nodes?: string[];
  node_id?: string;
  replayed_from?: unknown;
  correction?: CorrectionEvent;
  correction_trail?: NodeCorrection;
  measurement?: CuratedMeasurement;
  capsule_diff?: { caption: string; before: object; after: object };
};
export type CuratedReplay = {
  schema: string;
  title: string;
  summary: string;
  source_homes?: string[];
  native?: boolean;
  graph_mode?: 'recorded';
  steps: CuratedStep[];
};

// Plain-English names for record kinds that appear in raw factory homes. The
// original kind always stays visible next to the title.
const KIND_TITLES: Record<string, string> = {
  factory_iteration_summary: 'Iteration summary recorded',
  factory_iteration_successors: 'Next iterations proposed',
  taskgraph_patch: 'Task plan updated',
  revise: 'Task graph revised',
  build: 'Native build',
  lab: 'Lab measurement',
  admit: 'Lab admission',
  integrate: 'Source integrated',
  inspect: 'Configuration inspected',
  contract: 'Contract evaluation',
  ab_result: 'A/B comparison',
  report_publication: 'Report published',
  decide: 'Planner decision',
  accept: 'Accepted',
  reject: 'Rejected',
  partial: 'Partial result',
  report_inconclusive: 'Inconclusive report',
  keep_component: 'Keep component',
  revert_component: 'Revert component',
  upload: 'Upload',
};

function humanize(kind: string) {
  const base = kind.replace(/^replan\//, '');
  const known = KIND_TITLES[base];
  if (known) return kind.startsWith('replan/') ? `Replan: ${known.toLowerCase()}` : known;
  const words = base.replace(/^factory_/, '').replace(/[_./-]+/g, ' ').trim();
  return words ? words[0].toUpperCase() + words.slice(1) : kind;
}

/** Presentation title for one story event, plus its original record kind. */
export function presentEvent(event: StoryEvent) {
  const title = typeof event.presentation_title === 'string' && event.presentation_title
    ? event.presentation_title
    : humanize(event.kind);
  return { title, kind: event.kind, curated: typeof event.presentation_title === 'string' };
}

export type EventGroup = { event: StoryEvent; count: number; first: number; last: number; events: StoryEvent[] };

/** Collapse consecutive events with the same kind and summary into one entry with a count. */
export function collapseEvents(events: readonly StoryEvent[]): EventGroup[] {
  const groups: EventGroup[] = [];
  for (const event of events) {
    const previous = groups[groups.length - 1];
    if (previous && previous.event.kind === event.kind && previous.event.summary === event.summary
        && replayLabel(previous.event.replayed_from) === replayLabel(event.replayed_from)
        && !event.correction && !previous.event.correction && !event.presentation_title && event.kind !== 'taskgraph_patch' && revisionEvent(event) === undefined) {
      previous.count += 1;
      previous.last = event.cursor;
      previous.events.push(event);
      continue;
    }
    groups.push({ event, count: 1, first: event.cursor, last: event.cursor, events: [event] });
  }
  return groups;
}

export function curatedStepFor(curated: CuratedReplay | null | undefined, event: StoryEvent | undefined) {
  if (!curated || !event) return undefined;
  const step = typeof event.step === 'number' ? event.step : undefined;
  return curated.steps.find((item) => item.step === step);
}

/** Key files for the current step, resolved to run files; unresolved entries are dropped. */
export function keyFilesFor(step: CuratedStep | undefined, files: readonly EvidenceFile[]) {
  if (!step) return [];
  const byPath = new Map(files.map((file) => [file.path, file]));
  return step.key_files
    .map((key) => ({ key, file: byPath.get(key.path) }))
    .filter((row): row is { key: KeyFile; file: EvidenceFile } => Boolean(row.file));
}

export function keyFlags(curated: CuratedReplay | null | undefined) {
  const flags = new Map<string, KeyFile[]>();
  for (const step of curated?.steps ?? []) {
    for (const key of step.key_files) flags.set(key.path, [...(flags.get(key.path) ?? []), { ...key, step: step.step }]);
  }
  return flags;
}
