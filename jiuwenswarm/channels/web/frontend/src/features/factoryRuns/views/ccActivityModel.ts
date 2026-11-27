import type {
  CapsuleActivity,
  NativeActivitySource,
  NativeCheckVerdict,
  NativeWorkerUse,
  NodeCapsuleActivity,
} from '../api';

export type VerdictRecord = { id: string; output?: string; path?: string | null };
export type TimelineVerifierResult = {
  status: 'pass' | 'fail' | 'no-node-check' | 'closed-by-decision' | 'closed-by-update';
  records: VerdictRecord[];
  closure?: NativeActivitySource & { decision_id?: string };
};
export type CapsuleFacts = Pick<CapsuleActivity, 'id' | 'version'> & {
  use: 'used' | 'bound-not-used';
  verifier: 'pass' | 'fail' | 'no-cc-verifier-record' | 'no-verifier-declared';
  uses: NativeWorkerUse[];
  checks: NativeCheckVerdict[];
};

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

export function capsuleFactsAt(
  activity: NodeCapsuleActivity | undefined,
  cutoff = Infinity,
  reopenedAt = -Infinity,
): CapsuleFacts[] {
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
    const uses = capsule.uses.filter((item) => item.created <= cutoff);
    const checks = latestVerdicts(
      capsule.verifier_records.filter((item) => item.created <= cutoff && item.created > reopenedAt),
    );
    return [
      {
        id: capsule.id,
        version: binding?.version ?? capsule.version,
        use: uses.length ? 'used' : 'bound-not-used',
        verifier:
          checks[0]?.status ??
          (capsule.verifier_declaration === 'none' ? 'no-verifier-declared' : 'no-cc-verifier-record'),
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
  return { status: 'no-node-check', records: [] };
}
