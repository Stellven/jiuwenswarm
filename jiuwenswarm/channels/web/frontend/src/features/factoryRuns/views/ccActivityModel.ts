import type {
  CapsuleActivity,
  NativeActivitySource,
  NativeCheckVerdict,
  NativeWorkerUse,
  NodeCapsuleActivity,
} from '../api';

export type VerdictRecord = { id: string; output?: string; path?: string | null };
export type TimelineVerifierResult = {
  status: 'pass' | 'fail' | 'not-reached' | 'no-node-check' | 'closed-by-decision' | 'closed-by-update';
  records: VerdictRecord[];
  closure?: NativeActivitySource & { decision_id?: string };
};
export type CapsuleFacts = Pick<CapsuleActivity, 'id' | 'version'> & {
  use: 'used' | 'bound-not-used' | 'not-reached';
  verifier: 'pass' | 'fail' | 'no-cc-verifier-record' | 'no-verifier-declared' | 'not-reached';
  uses: NativeWorkerUse[];
  checks: NativeCheckVerdict[];
};

export type NodeExecutionFacts = { capsuleFacts: CapsuleFacts[]; nodeVerifier: TimelineVerifierResult };

export function latestVerdicts(records: readonly NativeCheckVerdict[]) {
  const latest = new Map<string, NativeCheckVerdict>();
  for (const record of records) {
    const key = record.output ?? record.id;
    const before = latest.get(key);
    if (!before || record.created >= before.created) latest.set(key, record);
  }
  return [...latest.values()].sort(
    (a, b) => Number(b.status === 'fail') - Number(a.status === 'fail') || b.created - a.created,
  );
}

export function nodeReachedAt(activity: NodeCapsuleActivity | undefined, cutoff = Infinity) {
  if (!activity) return false;
  const seen = (record: NativeActivitySource) => record.created <= cutoff;
  return Boolean(
    (activity.reached && seen(activity.reached)) ||
    activity.node_checks?.some(seen) ||
    activity.closures?.some((record) => record.state === 'done' && seen(record)) ||
    activity.capsules.some((capsule) => capsule.uses.some(seen) || capsule.verifier_records.some(seen)),
  );
}

export function capsuleFactsAt(
  activity: NodeCapsuleActivity | undefined,
  cutoff = Infinity,
  reopenedAt = -Infinity,
): CapsuleFacts[] {
  const reached = nodeReachedAt(activity, cutoff);
  return (activity?.capsules ?? []).flatMap((capsule) => {
    const binding = capsule.bindings
      ?.filter((item) => item.source.created <= cutoff && (item.unbound_at == null || cutoff < item.unbound_at))
      .at(-1);
    if (
      capsule.bindings?.length
        ? !binding
        : (capsule.bound_at != null && capsule.bound_at > cutoff) ||
          (capsule.unbound_at != null && cutoff >= capsule.unbound_at) ||
          (capsule.active === false && cutoff === Infinity)
    )
      return [];
    const verifierRecords = capsule.verifier_records.filter((item) => item.created <= cutoff);
    // Older replays can have the actual verifier receipt without a separate use row.
    const byId = new Map<string, NativeWorkerUse>(
      verifierRecords.map((item) => [item.id, { ...item, kind: 'cc-verifier' }]),
    );
    for (const item of capsule.uses) {
      if (item.created <= cutoff) byId.set(item.id, item);
    }
    const uses = [...byId.values()].sort((a, b) => a.created - b.created);
    const checks = latestVerdicts(verifierRecords.filter((item) => item.created > reopenedAt));
    return [
      {
        id: capsule.id,
        version: binding?.version ?? capsule.version,
        use: uses.length ? 'used' : reached ? 'bound-not-used' : 'not-reached',
        verifier: reached
          ? (checks[0]?.status ??
            (capsule.verifier_declaration === 'none' ? 'no-verifier-declared' : 'no-cc-verifier-record'))
          : 'not-reached',
        uses,
        checks,
      },
    ];
  });
}

export function reopenBoundary(activity: NodeCapsuleActivity | undefined, cutoff: number, fromGraph = -Infinity) {
  return (activity?.closures ?? []).reduce(
    (last, item) => (item.state === 'reopened' && item.created <= cutoff ? Math.max(last, item.created) : last),
    fromGraph,
  );
}

export function nodeVerifierAt(
  activity: NodeCapsuleActivity | undefined,
  cutoff = Infinity,
  reopenedAt = -Infinity,
  done = false,
): TimelineVerifierResult {
  const visible = (row: NativeActivitySource) => row.created <= cutoff && row.created > reopenedAt;
  const verdicts = latestVerdicts((activity?.node_checks ?? []).filter(visible));
  if (verdicts.length) {
    return {
      status: verdicts[0].status,
      records: verdicts.map(({ id, output, path }) => ({ id, output, path })),
    };
  }
  const closure = done
    ? (activity?.closures ?? [])
        .filter((row) => row.state === 'done' && visible(row))
        .sort((a, b) => b.created - a.created)[0]
    : undefined;
  if (closure)
    return {
      status: closure.decision_id ? 'closed-by-decision' : 'closed-by-update',
      closure,
      records: [],
    };
  return { status: nodeReachedAt(activity, cutoff) ? 'no-node-check' : 'not-reached', records: [] };
}
