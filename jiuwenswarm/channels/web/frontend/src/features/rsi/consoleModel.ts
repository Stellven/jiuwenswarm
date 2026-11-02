import type { CcNode, CcRun, CcSnapshot, CcSourceCatalog } from './ccTypes';

export function consoleTargets(snapshot: CcSnapshot | null, catalog: CcSourceCatalog | null) {
  const targets = new Map(
    (snapshot?.targets ?? []).map((target) => [
      target.id,
      {
        ...target,
        description: 'Published capsule',
        revision: target.run.revision ?? snapshot?.revision,
      },
    ]),
  );
  for (const source of catalog?.targets ?? []) {
    const id = source.target_id ?? source.capsule_name;
    const published = targets.get(id);
    targets.set(id, {
      id,
      name: published?.name ?? source.capsule_name.replace(/_/g, ' '),
      description: source.scope,
      parent_hash: source.parent_code_sha256,
      active_hash: published?.active_hash ?? null,
      run: source.run ?? published?.run ?? { allowed: false, blocker: source.adapter_blocker },
      revision: source.run?.revision ?? source.revision ?? published?.revision,
    });
  }
  return [...targets.values()];
}

export function isRunActive(run: CcRun | undefined) {
  if (!run) return false;
  return /^(running|finalizing|pending|queued|preparing|launched|claimed|accepted_unqualified|in_progress)$/i.test(
    run.status,
  );
}

export function nodeIteration(node: CcNode, runs: CcRun[]) {
  return runs.find((run) => run.id === node.run_id)?.lineage?.iterations.find((item) => item.node_id === node.id);
}

export function nodeStatus(node: CcNode) {
  if (/^active$/i.test(node.activation_status)) return 'Active';
  if (/^admitted$/i.test(node.admission_status)) return 'Admitted';
  if (!node.parent_id) return 'Root';
  return node.evaluation_status.replace(/_/g, ' ');
}

export function statusTone(status: string) {
  if (/fail|error|reject|regress/i.test(status)) return 'bad';
  if (/pass|complete|success|active|admitted|verified/i.test(status)) return 'ok';
  if (/running|progress|preparing|launched|accepted/i.test(status)) return 'accent';
  return 'muted';
}

export const formatMeasure = (value: number | null | undefined, suffix = '') =>
  value == null ? '—' : `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)}${suffix}`;

export const percent = (value: number | null | undefined) => (value == null ? '—' : formatMeasure(value * 100, '%'));

export function runStages(run: CcRun | undefined) {
  const stages = [...new Set((run?.activity ?? []).map((item) => item.stage))];
  if (run?.stage && !stages.includes(run.stage)) stages.push(run.stage);
  return stages;
}
