import { createTwoFilesPatch } from 'diff';
import type { JsonRecord, NodeCapsule, NodeContract, NodeOutput, RunOperation, StoryEvent } from '../api';
import { atlasTitle } from '../cc/atlasNames.ts';
import { operatorEnabled, type Controls, type NodeCheckView, type RunKind } from './checkModel.ts';

export function evidenceRecord(value: unknown): JsonRecord | undefined {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? (value as JsonRecord) : undefined;
}

export function evidenceText(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

function sortedJson(_key: string, value: unknown) {
  const row = evidenceRecord(value);
  return row ? Object.fromEntries(Object.entries(row).sort(([left], [right]) => left.localeCompare(right))) : value;
}

export function contractDiff(contract: NodeContract | undefined) {
  const pretty = (document: JsonRecord) => JSON.stringify(document, sortedJson, 2) + '\n';
  const before = contract?.preliminary ? pretty(contract.preliminary) : undefined;
  const after = contract?.final ? pretty(contract.final) : undefined;
  return {
    before,
    after,
    patch:
      before && after && before !== after
        ? createTwoFilesPatch('preliminary.json', 'final.json', before, after, '', '', { context: 3 })
        : undefined,
  };
}

export function replayLabel(value: unknown): string | undefined {
  if (Array.isArray(value)) {
    const labels = [...new Set(value.map(replayLabel).filter(Boolean))];
    return labels.length ? labels.join(' · ') : undefined;
  }
  const row = evidenceRecord(value);
  const source =
    evidenceText(value) ??
    evidenceText(
      row?.source_run ??
        row?.run ??
        row?.run_id ??
        row?.task_id ??
        row?.source_task ??
        row?.source_home ??
        row?.original_attempt ??
        row?.attempt_id ??
        row?.source_attempt_id,
    );
  if (!source && (!row || !Object.keys(row).length)) return undefined;
  const minutes = row?.original_minutes ?? row?.minutes;
  const seconds =
    row?.duration_seconds ??
    row?.original_elapsed_seconds ??
    row?.original_elapsed_s ??
    row?.original_seconds ??
    row?.elapsed_seconds ??
    row?.elapsed_s ??
    row?.seconds;
  const originalSeconds = typeof seconds === 'number' ? seconds : typeof minutes === 'number' ? minutes * 60 : NaN;
  let duration = '';
  if (Number.isFinite(originalSeconds) && originalSeconds >= 0) {
    const wholeSeconds = Math.round(originalSeconds);
    const wholeMinutes = Math.floor(wholeSeconds / 60);
    const remainingSeconds = wholeSeconds % 60;
    duration = [
      wholeMinutes ? `${wholeMinutes} min` : '',
      remainingSeconds || !wholeMinutes ? `${remainingSeconds} s` : '',
    ]
      .filter(Boolean)
      .join(' ');
  }
  return `Replayed${source ? ` from ${source}` : ''}${duration ? `, originally ${duration}` : ''}`;
}

function indexReplay(replays: Map<string, unknown[]>, id: unknown, source: unknown) {
  if (typeof id !== 'string' || !source) return;
  const origins = replays.get(id) ?? [];
  origins.push(source);
  replays.set(id, origins);
}

export function nodeReplayOrigins(events: readonly StoryEvent[], position: number) {
  const replays = new Map<string, unknown[]>();
  for (const event of events.slice(0, position)) {
    indexReplay(replays, event.node_id, event.replayed_from);
  }
  return replays;
}

export function artifactReplayOrigins(records: readonly JsonRecord[]) {
  const replays = new Map<string, unknown[]>();
  for (const record of records) {
    const values = evidenceRecord(record.values);
    const source = values?.replayed_from ?? evidenceRecord(values?.request)?.replayed_from;
    if (!source || !Array.isArray(record.source_artifacts)) continue;
    for (const id of record.source_artifacts) indexReplay(replays, id, source);
  }
  return replays;
}

export function capsuleCard(capsule: NodeCapsule, checks: NodeCheckView | undefined) {
  const outputNames = new Set((capsule.outputs ?? []).map((output) => output.name));
  const attached =
    capsule.checks ??
    checks?.outputs.filter(
      (row) =>
        outputNames.has(row.name) ||
        [row.verifier, ...row.checks.map((check) => check.verifier?.cc)].some(
          (verifier) => verifier === capsule.id || verifier?.startsWith(capsule.id + '.'),
        ),
    );
  return {
    ...capsule,
    title: capsule.title ?? atlasTitle(capsule.id) ?? capsule.id,
    checkView: attached?.length ? { ...checks, helpful_ccs: [], capability: undefined, outputs: attached } : undefined,
    failures: Array.isArray(capsule.calls?.failures) ? capsule.calls.failures.length : (capsule.calls?.failures ?? 0),
  };
}

export function unassignedOutputs(outputs: NodeOutput[], capsules: NodeCapsule[]) {
  const attached = new Set(capsules.flatMap((capsule) => (capsule.outputs ?? []).map((output) => output.id)));
  return outputs.filter((output) => !attached.has(output.id));
}

export function runOperations(run: RunKind, controls: Controls | undefined): RunOperation[] {
  if (!operatorEnabled(run, controls)) return [];
  return [
    ...(controls?.pause ? (['pause'] as const) : []),
    ...(controls?.resume ? (['resume'] as const) : []),
    ...(controls?.revise ? (['revise-preview'] as const) : []),
    ...(controls?.revise && controls.revise_apply ? (['revise-apply'] as const) : []),
  ];
}

export function revisionEvent(event: StoryEvent) {
  const revision = event.graph_rev ?? event.rev;
  return ['revise', 'taskgraph_patch'].includes(event.kind) && typeof revision === 'number' ? revision : undefined;
}
