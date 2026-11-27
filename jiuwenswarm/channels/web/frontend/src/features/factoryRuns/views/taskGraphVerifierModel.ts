import type { JsonRecord } from '../api';
import { evidenceRecord, evidenceText } from './nodeEvidenceModel.ts';

type ResultStatus = 'pass' | 'fail' | 'not-run';
type RecordSource = { id: string; output: string; path?: string };
export type TimelineVerifierResult = { status: ResultStatus; records: RecordSource[] };
type CheckRecord = {
  id: string;
  created: number;
  output: string;
  values: JsonRecord;
};
type Verdict = { check: CheckRecord; status: 'pass' | 'fail' };

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

function checkOutputs(spec: unknown): JsonRecord[] {
  const fields = evidenceRecord(spec);
  if (!fields) return [];
  if (Array.isArray(fields.outputs)) return fields.outputs.map(evidenceRecord).filter((entry) => entry !== undefined);
  return [{ name: 'change', kind: 'diff', ...fields }];
}

/** Match the host's comparison of effective check entries, including pinned inputs and criteria. */
function equalJson(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  if (Array.isArray(left) && Array.isArray(right))
    return left.length === right.length && left.every((value, index) => equalJson(value, right[index]));
  const a = evidenceRecord(left);
  const b = evidenceRecord(right);
  return Boolean(
    a &&
    b &&
    Object.keys(a).length === Object.keys(b).length &&
    Object.keys(a).every((key) => Object.prototype.hasOwnProperty.call(b, key) && equalJson(a[key], b[key])),
  );
}

function verdict(check: CheckRecord | undefined, passed: unknown): Verdict | undefined {
  if (!check || check.values.state !== 'finished' || typeof passed !== 'boolean') return;
  return { check, status: passed ? 'pass' : 'fail' };
}

function summarize(verdicts: Verdict[], expected: number, path: string | undefined): TimelineVerifierResult {
  const failure = verdicts.some((result) => result.status === 'fail');
  const status = failure ? 'fail' : verdicts.length && verdicts.length === expected ? 'pass' : 'not-run';
  const records = [...verdicts]
    .sort((a, b) => Number(b.status === 'fail') - Number(a.status === 'fail') || b.check.created - a.check.created)
    .map(({ check }) => ({ id: check.id, output: check.output, path }));
  return { status, records };
}

export function summarizeTaskGraphVerifiers(
  records: readonly CheckRecord[],
  spec: unknown,
  boundCCs: readonly string[],
  cutoff: number,
  reopenedAt: number,
  path?: string,
) {
  const current = new Map<string, CheckRecord>();
  for (const row of records) {
    if (row.created > cutoff) break;
    if (row.created > reopenedAt) current.set(row.output, row);
  }

  const entries = checkOutputs(spec);
  // Some old records have no declaration in the snapshot. Retain what the host recorded.
  const outputs = entries.length
    ? entries.flatMap((entry) => {
        const name = evidenceText(entry.name);
        if (!name) return [];
        const record = current.get(name);
        const check = record && equalJson(record.values.entry, entry) ? record : undefined;
        return [{ check, required: entry.required !== false }];
      })
    : [...current.values()].map((check) => ({
        check,
        required: evidenceRecord(check.values.entry)?.required !== false,
      }));

  const required = outputs.filter((output) => output.required);
  const nodeOutputs = required.length ? required : outputs;
  const hostVerdicts = nodeOutputs
    .map(({ check }) => verdict(check, check?.values.passed))
    .filter((result) => result !== undefined);
  const nodeVerifier = summarize(hostVerdicts, nodeOutputs.length, path);

  const ccVerifiers = Object.fromEntries(
    boundCCs.map((cc) => {
      const ccId = cc.split('@', 1)[0];
      const ccVerdicts = outputs.flatMap(({ check }) => {
        const verifier = evidenceRecord(check?.values.verifier);
        const actualCC = evidenceText(verifier?.cc)?.split('@', 1)[0];
        const result = actualCC === ccId ? verdict(check, verifier?.passed) : undefined;
        return result ? [result] : [];
      });
      return [cc, summarize(ccVerdicts, ccVerdicts.length, path)];
    }),
  );
  return { nodeVerifier, ccVerifiers };
}
