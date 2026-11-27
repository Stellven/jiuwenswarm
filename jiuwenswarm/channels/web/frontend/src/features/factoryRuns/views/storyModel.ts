import type { CorrectionEvent, EvidenceFile, JsonRecord, NodeCorrection, StoryEvent } from '../api';
import { evidenceRecord, evidenceText, replayLabel, revisionEvent } from './nodeEvidenceModel.ts';

export type KeyFile = { path: string; label: string; why?: string; step?: number };
export type ReplayCheckStage = 'factory' | 'runtime' | 'mixed';
export type ReplayCheckPresentation = { stage: ReplayCheckStage; method: string; role: string; verifier_role?: string };
export type ReplayNodePresentation = {
  title: string;
  method: string;
  checks: Record<string, ReplayCheckPresentation>;
};

export function replayCheckStage(stage: ReplayCheckStage) {
  if (stage === 'factory') return 'Factory stage';
  if (stage === 'runtime') return 'Runtime stage';
  return 'Factory and Runtime stages';
}

export function replayEvidenceText(value: string) {
  return value.replace(/\bprefix[ -]store\b/gi, (name) => name.startsWith('P') ? 'Prefix reuse' : 'prefix reuse');
}

export type CuratedMeasurement = {
  baseline: string;
  accuracy: { reference_pct?: number; candidate_pct?: number; loss_pts: number; lo_pts: number; hi_pts: number; n: number; path: string };
  rows: {
    arm: string;
    request: string;
    state: string;
    sources?: { path?: string; record?: string }[];
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
  presenter_line?: string;
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
  stages?: ReplayCheckStage[];
};
export type CuratedReplay = {
  schema: string;
  title: string;
  summary: string;
  source_homes?: string[];
  native?: boolean;
  graph_mode?: 'recorded';
  node_presentation?: Record<string, ReplayNodePresentation>;
  presentation_header?: {
    objective: string;
    outcome: string;
    image_id?: string | null;
    report_kind?: 'lab' | 'run';
  };
  contract_versions?: { version: number; path: string; sha256: string; amendment?: string; reason?: string }[];
  steps: CuratedStep[];
};

const CHECK_ROLES = ['CC verifier', 'Node verifier', 'Scheduler', 'Lab agent'] as const;
type CheckRole = (typeof CHECK_ROLES)[number];

export function recordedCheckRoles(
  step: CuratedStep,
  observations: readonly JsonRecord[],
  presentation: CuratedReplay['node_presentation'],
): CheckRole[] {
  const references = new Set(step.records?.filter((row) => row.table === 'observations').map((row) => row.id));
  const roles = new Set<CheckRole>();

  if (step.original_kind === 'node_contract_final' || step.original_kind === 'node_contract_refusal') {
    return observations.some((observation) => observation.kind === step.original_kind
      && references.has(evidenceText(observation.obs_id) ?? '')) ? ['Scheduler'] : [];
  }

  for (const observation of observations) {
    if (observation.kind !== 'node_check') continue;
    const values = evidenceRecord(observation.values);
    const node = evidenceText(values?.node_id);
    const cited = references.has(evidenceText(observation.obs_id) ?? '');
    // Some steps cite source observations that the focused node's verifier checked.
    const evidenceIds = evidenceRecord(values?.refs)?.evidence_ids;
    const citesSources = node && node === step.node_id && Array.isArray(evidenceIds)
      && evidenceIds.some((value) => references.has(value));
    if (!cited && !citesSources) continue;
    roles.add('Node verifier');
    const output = evidenceText(values?.output);
    const check = node && output ? presentation?.[node]?.checks[output] : undefined;
    if (check?.verifier_role === 'CC verifier') roles.add('CC verifier');
    if (check?.role === 'Lab acceptance') roles.add('Lab agent');
  }
  // Run 1's sealed lab report is attached directly to the benchmark step.
  if (step.original_kind === 'r8-final-bench' && step.records?.some(
    (row) => row.table === 'file' && row.id === 'evidence/lab/report.json',
  )) {
    roles.add('Lab agent');
  }
  return CHECK_ROLES.filter((role) => roles.has(role));
}

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

/** Follow new records at the end, or keep the same record while a viewer is reviewing earlier steps. */
export function liveReplayPosition(previous: readonly StoryEvent[], next: readonly StoryEvent[], position: number) {
  if (position === previous.length) return next.length;
  const active = previous[position - 1];
  const match = active ? next.findIndex((event) => event.id === active.id && event.kind === active.kind) : -1;
  return match >= 0 ? match + 1 : Math.min(position, next.length);
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
