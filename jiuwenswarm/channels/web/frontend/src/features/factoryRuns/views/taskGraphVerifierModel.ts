import type { JsonRecord, NativeCheckVerdict, NodeCapsuleActivity } from '../api';
import { evidenceRecord, evidenceText } from './nodeEvidenceModel.ts';

type CheckRecord = {
  id: string;
  created: number;
  output: string;
  values: JsonRecord;
};

export function indexTaskGraphChecks(observations: readonly unknown[], taskId: string | undefined) {
  const byNode = new Map<string, CheckRecord[]>();
  for (const item of observations) {
    const row = evidenceRecord(item);
    if (row?.kind !== 'node_check' || (row.task_id && row.task_id !== taskId)) continue;
    const id = evidenceText(row.obs_id);
    const created = row.created;
    const values = evidenceRecord(row.values);
    const nodeId = evidenceText(values?.node_id);
    if (!id || typeof created !== 'number' || !nodeId || !values) continue;
    const checks = byNode.get(nodeId) ?? [];
    checks.push({ id, created, output: evidenceText(values.output) ?? 'change', values });
    byNode.set(nodeId, checks);
  }
  for (const checks of byNode.values()) checks.sort((a, b) => a.created - b.created);
  return byNode;
}

/** Read older API snapshots without treating a contract's declaration as a verdict. */
export function legacyTimelineActivity(
  records: readonly CheckRecord[],
  boundCCs: readonly string[],
  path?: string,
): NodeCapsuleActivity {
  const terminal = records.filter(({ values }) => values.state == null || values.state === 'finished');
  const asVerdict = (record: CheckRecord, passed: unknown): NativeCheckVerdict[] =>
    typeof passed === 'boolean'
      ? [{ id: record.id, created: record.created, output: record.output, path, status: passed ? 'pass' : 'fail' }]
      : [];
  return {
    node_checks: terminal.flatMap((record) => asVerdict(record, record.values.passed)),
    closures: [],
    capsules: boundCCs.map((id) => ({
      id,
      verifier_declaration: 'unknown',
      uses: [],
      verifier_records: terminal.flatMap((record) => {
        const verifier = evidenceRecord(record.values.verifier);
        const cc = evidenceText(verifier?.cc)?.split('@', 1)[0];
        return cc === id.split('@', 1)[0] ? asVerdict(record, verifier?.passed) : [];
      }),
    })),
  };
}
