/**
 * Lab results of a factory.contract/2 run: the lab reports the lab manager
 * recorded (observation kind `lab_report`, values from factory.lab-report/1)
 * laid out by the contract's own arms, workload requests and metrics.
 * Nothing about arms, metrics or the reference arm is assumed; all of it is
 * read from the contract, with stated fallbacks when the contract is silent.
 */

type Fields = Record<string, unknown>;

export type Better = 'lower' | 'higher' | undefined;
export type LabArm = { id: string; role?: string; summary?: string; declared: boolean };
export type LabMetric = { id: string; unit?: string; better: Better; how?: string; primary: boolean; declared: boolean };
export type RawRow = Fields & { test_id?: string; arm?: string; metric?: string; request?: string };
export type LabCell = {
  value?: number;
  unit?: string;
  /** Rows the value comes from (several rows of one cell are summarized by their median). */
  rows: RawRow[];
  /** (value - reference) / reference, for the same metric, request and condition. */
  change?: number;
  /** better | worse | same | undetermined (no direction declared) */
  verdict?: 'better' | 'worse' | 'same' | 'undetermined';
  reference: boolean;
};
export type LabLine = { request: string; condition: string; cells: Record<string, LabCell> };
export type LabMetricTable = { metric: LabMetric; lines: LabLine[] };
export type LabCheck = {
  id: string;
  does?: string;
  appliesTo: string[];
  verdict: 'pass' | 'fail' | 'not_run' | 'no result';
  rows: RawRow[];
  declared: boolean;
};
export type LabReport = {
  obsId: string;
  requestId?: string;
  created?: number;
  valid: boolean;
  problems: string[];
  outcome?: string;
  summary?: string;
  lab?: string;
  limitations?: string;
  notRun: RawRow[];
  reportFile?: string;
  tables: LabMetricTable[];
  checks: LabCheck[];
};
export type LabResults = {
  contractId?: string;
  arms: LabArm[];
  reference: { arm?: string; source: string };
  metrics: LabMetric[];
  reports: LabReport[];
};

const record = (value: unknown): Fields | undefined =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as Fields) : undefined;
const rows = (value: unknown): Fields[] => (Array.isArray(value) ? value.map(record).filter((r): r is Fields => !!r) : []);
const text = (value: unknown) => (typeof value === 'string' && value.trim() ? value.trim() : undefined);
const finite = (value: unknown) => (typeof value === 'number' && Number.isFinite(value) ? value : undefined);

export function median(values: number[]) {
  if (!values.length) return undefined;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

export function rowValue(row: Fields) {
  const value = finite(row.value);
  if (value !== undefined) return value;
  const samples = Array.isArray(row.samples) ? row.samples.map(finite).filter((v): v is number => v !== undefined) : [];
  return median(samples);
}

/**
 * Cold/warm is not a field of factory.lab-report/1; a lab names it in the test
 * or request id (`ttft-cold`, `p512:warm`). Ids without either token keep their
 * test id as the condition, so nothing is merged that the lab kept apart.
 */
const PHASE = /(?:^|[^a-z0-9])(cold|warm)(?=$|[^a-z0-9])/i;
export function conditionOf(row: RawRow) {
  for (const value of [text(row.request), text(row.test_id)]) {
    const match = value ? PHASE.exec(value) : null;
    if (match) return match[1].toLowerCase();
  }
  return text(row.test_id) ?? '';
}
export function requestOf(row: RawRow) {
  const request = text(row.request);
  if (!request) return '';
  return request.replace(PHASE, '').replace(/^[^a-z0-9]+|[^a-z0-9]+$/gi, '') || request;
}

export function contractArms(contract: Fields): { id: string; role?: string; summary?: string }[] {
  return rows(contract.arms).flatMap((arm) => {
    const id = text(arm.id);
    return id ? [{ id, role: text(arm.role), summary: text(arm.summary) }] : [];
  });
}

/** The arm every change is measured against: the contract's comparison, its correctness reference, its baseline role. */
export function referenceArm(contract: Fields): { arm?: string; source: string } {
  const comparison = record(contract.comparison);
  const fromComparison = text(comparison?.reference) ?? text(comparison?.base) ?? text(comparison?.baseline);
  if (fromComparison) return { arm: fromComparison, source: 'contract comparison' };
  const reference = text(record(record(contract.correctness)?.reference)?.arm);
  if (reference) return { arm: reference, source: 'contract correctness reference' };
  const arms = contractArms(contract);
  const baseline = arms.find((arm) => arm.role === 'baseline');
  if (baseline) return { arm: baseline.id, source: 'contract arm with role baseline' };
  if (arms[0]) return { arm: arms[0].id, source: 'first contract arm (the contract names no reference)' };
  return { source: 'the contract names no arms' };
}

export function contractMetrics(contract: Fields): LabMetric[] {
  const measurement = record(contract.measurement);
  const metrics = record(measurement?.metrics) ?? {};
  const primary = text(measurement?.primary);
  const list = Object.entries(metrics).map(([id, spec]) => {
    const value = record(spec) ?? {};
    const better: Better = value.better === 'lower' || value.better === 'higher' ? value.better : undefined;
    return { id, unit: text(value.unit), better, how: text(value.how), primary: id === primary, declared: true };
  });
  return [...list.filter((m) => m.primary), ...list.filter((m) => !m.primary)];
}

function judge(change: number | undefined, better: Better): LabCell['verdict'] {
  if (change === undefined) return undefined;
  if (change === 0) return 'same';
  if (!better) return 'undetermined';
  return (change < 0) === (better === 'lower') ? 'better' : 'worse';
}

function appliesTo(check: Fields, arms: LabArm[]) {
  const named = Array.isArray(check.applies_to) ? check.applies_to.map(text).filter((v): v is string => !!v) : [];
  return arms.filter((arm) => named.includes(arm.id) || (arm.role && named.includes(arm.role))).map((arm) => arm.id);
}

function reportOf(
  observation: Fields,
  contract: Fields,
  arms: LabArm[],
  metrics: LabMetric[],
  reference: string | undefined,
  requestOrder: string[],
  files: readonly { path: string; artifact_ids?: string[] }[],
): LabReport {
  const values = record(observation.values) ?? {};
  const requestId = text(values.request_id);
  const results = rows(values.results) as RawRow[];
  const metricIds = [...metrics.map((m) => m.id)];
  const extraMetrics: LabMetric[] = [];
  for (const row of results) {
    const id = text(row.metric);
    if (id && !metricIds.includes(id)) {
      metricIds.push(id);
      extraMetrics.push({ id, unit: text(row.unit), better: undefined, primary: false, declared: false });
    }
  }
  const tables: LabMetricTable[] = [];
  for (const metric of [...metrics, ...extraMetrics]) {
    const own = results.filter((row) => row.metric === metric.id);
    if (!own.length) continue;
    const lines = new Map<string, LabLine>();
    for (const row of own) {
      const request = requestOf(row);
      const condition = conditionOf(row);
      const key = JSON.stringify([request, condition]);
      const line = lines.get(key) ?? { request, condition, cells: {} };
      const arm = text(row.arm) ?? '';
      const cell = line.cells[arm] ?? { rows: [], reference: arm === reference };
      cell.rows.push(row);
      line.cells[arm] = cell;
      lines.set(key, line);
    }
    for (const line of lines.values()) {
      for (const cell of Object.values(line.cells)) {
        cell.value = median(cell.rows.map(rowValue).filter((v): v is number => v !== undefined));
        cell.unit = text(cell.rows[0]?.unit) ?? metric.unit;
      }
      const base = reference ? line.cells[reference]?.value : undefined;
      for (const cell of Object.values(line.cells)) {
        if (cell.reference || base === undefined || base === 0 || cell.value === undefined) continue;
        cell.change = (cell.value - base) / base;
        cell.verdict = judge(cell.change, metric.better);
      }
    }
    const order = (request: string) => {
      const index = requestOrder.indexOf(request);
      return index < 0 ? requestOrder.length : index;
    };
    const conditionOrder = (condition: string) => (condition === 'cold' ? 0 : condition === 'warm' ? 1 : 2);
    tables.push({
      metric,
      lines: [...lines.values()].sort(
        (a, b) =>
          order(a.request) - order(b.request) ||
          a.request.localeCompare(b.request) ||
          conditionOrder(a.condition) - conditionOrder(b.condition) ||
          a.condition.localeCompare(b.condition),
      ),
    });
  }
  const reported = rows(values.checks) as RawRow[];
  const checks: LabCheck[] = rows(record(contract.correctness)?.checks).map((check) => {
    const id = text(check.id) ?? '';
    const own = reported.filter((row) => row.check === id);
    return { id, does: text(check.does), appliesTo: appliesTo(check, arms), ...verdictOf(own), declared: true };
  });
  for (const row of reported) {
    const id = text(row.check);
    if (id && !checks.some((check) => check.id === id)) {
      const own = reported.filter((r) => r.check === id);
      checks.push({ id, appliesTo: [], ...verdictOf(own), declared: false });
    }
  }
  const reportArtifact = requestId ? `${requestId}:report.json` : undefined;
  const reportFile = files.find((file) => reportArtifact && file.artifact_ids?.includes(reportArtifact))?.path;
  return {
    obsId: text(observation.obs_id) ?? '',
    requestId,
    created: finite(observation.created),
    valid: values.valid !== false,
    problems: Array.isArray(values.problems) ? values.problems.filter((p): p is string => typeof p === 'string') : [],
    outcome: text(values.outcome),
    summary: text(values.summary),
    lab: text(record(values.lab)?.name),
    limitations: text(observation.limitations),
    notRun: rows(values.not_run) as RawRow[],
    reportFile,
    tables,
    checks,
  };
}

function verdictOf(own: RawRow[]): { verdict: LabCheck['verdict']; rows: RawRow[] } {
  const verdicts = own.map((row) => row.verdict);
  const verdict = !own.length
    ? 'no result'
    : verdicts.includes('fail')
      ? 'fail'
      : verdicts.every((v) => v === 'pass')
        ? 'pass'
        : 'not_run';
  return { verdict, rows: own };
}

export function isContractV2(contract: unknown) {
  return record(contract)?.schema === 'factory.contract/2';
}

export function labResults(
  contract: unknown,
  observations: readonly unknown[] | undefined,
  files: readonly { path: string; artifact_ids?: string[] }[] = [],
): LabResults | null {
  const document = record(contract);
  if (!document || !isContractV2(document)) return null;
  const declared: LabArm[] = contractArms(document).map((arm) => ({ ...arm, declared: true }));
  const reference = referenceArm(document);
  const metrics = contractMetrics(document);
  const requestOrder = rows(record(document.workload)?.requests)
    .map((request) => text(request.id))
    .filter((id): id is string => !!id);
  const labReports = rows(observations)
    .filter((row) => row.kind === 'lab_report')
    .sort((a, b) => (finite(a.created) ?? 0) - (finite(b.created) ?? 0));
  const arms = [...declared];
  for (const observation of labReports) {
    for (const row of rows(record(observation.values)?.results)) {
      const id = text(row.arm);
      if (id && !arms.some((arm) => arm.id === id)) arms.push({ id, declared: false });
    }
  }
  return {
    contractId: text(document.contract_id),
    arms,
    reference,
    metrics,
    reports: labReports.map((row) => reportOf(row, document, arms, metrics, reference.arm, requestOrder, files)),
  };
}

export function formatChange(change: number | undefined) {
  if (change === undefined) return '';
  const percent = change * 100;
  const digits = Math.abs(percent) >= 10 ? 0 : 1;
  return `${percent > 0 ? '+' : percent < 0 ? '−' : '±'}${Math.abs(percent).toFixed(digits)}%`;
}

export function formatValue(value: number | undefined, unit?: string) {
  if (value === undefined) return '—';
  const abs = Math.abs(value);
  const digits = abs >= 1000 ? 0 : abs >= 100 ? 1 : abs >= 1 ? 2 : 3;
  const shown = unit === 'bytes' && abs >= 1024 ** 3 ? `${(value / 1024 ** 3).toFixed(2)} GiB` : value.toLocaleString('en-US', { maximumFractionDigits: digits });
  return unit && unit !== 'bytes' ? `${shown} ${unit}` : unit === 'bytes' && abs < 1024 ** 3 ? `${shown} B` : shown;
}
