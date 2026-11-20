import { CORE_SCHEMA, load } from 'js-yaml';
import type { EvidenceFile } from '../api';

export type StructuredValue = null | boolean | number | string | StructuredValue[] | { [key: string]: StructuredValue };
export type StructuredRecord = { [key: string]: StructuredValue };
export type DocumentFormat = 'json' | 'yaml' | 'mermaid' | 'text';
type Inspection =
  | { format: DocumentFormat; value: StructuredValue }
  | { format: DocumentFormat; issue?: 'parseError' | 'structureLimit' };

const MAX_DEPTH = 40;
const MAX_VALUES = 25_000;
const MAX_EXPANDED_TEXT = 24 * 1024 * 1024;

export function documentFormat(name: string, source: string): DocumentFormat {
  if (/\.ya?ml$/i.test(name)) return 'yaml';
  if (/\.(mmd|mermaid)$/i.test(name)) return 'mermaid';
  if (/\.json$/i.test(name) || /^[\uFEFF\s]*[\[{]/.test(source)) return 'json';
  return 'text';
}

export function inspectDocument(name: string, source: string): Inspection {
  const format = documentFormat(name, source);
  let value: unknown;
  try {
    if (format === 'json') value = JSON.parse(source.replace(/^\uFEFF/, ''));
    else if (format === 'yaml') {
      value = load(source, { schema: CORE_SCHEMA, maxDepth: MAX_DEPTH, maxTotalMergeKeys: 0 });
      if (value === undefined) return { format };
    } else return { format };
  } catch {
    if (format === 'json' && !/\.json$/i.test(name)) return { format: 'text' };
    return { format, issue: 'parseError' };
  }
  return inspectValue(value, format);
}

export function inspectValue(value: unknown, format: DocumentFormat = 'json'): Inspection {
  let remaining = MAX_VALUES;
  let textBudget = MAX_EXPANDED_TEXT;
  const ancestors = new Set<object>();

  function canVisit(item: unknown, depth: number): boolean {
    if (depth > MAX_DEPTH || --remaining < 0 || textBudget < 0) return false;
    if (typeof item === 'string') {
      textBudget -= item.length;
      return textBudget >= 0;
    }
    if (item === null || typeof item === 'number' || typeof item === 'boolean') return true;
    if (typeof item !== 'object' || ancestors.has(item)) return false;

    // YAML aliases can share objects. Count every occurrence that the viewer would expand.
    ancestors.add(item);
    const valid = Object.keys(item).every((key) => {
      textBudget -= key.length;
      return canVisit((item as Record<string, unknown>)[key], depth + 1);
    });
    ancestors.delete(item);
    return valid;
  }

  return canVisit(value, 0) ? { format, value: value as StructuredValue } : { format, issue: 'structureLimit' };
}

export function isRecord(value: StructuredValue): value is StructuredRecord {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export function formatKey(key: string): string {
  const words = key
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .trim()
    .replace(
      /\b(?:ttft|sha256|gpu|cpu|id|json|yaml|mib|gib|cc|ms)\b/gi,
      (word) => ({ sha256: 'SHA-256', mib: 'MiB', gib: 'GiB', ms: 'ms' })[word.toLowerCase()] || word.toUpperCase(),
    );
  return words.charAt(0).toUpperCase() + words.slice(1) || key;
}

export type TreeEntry = {
  key: string;
  path: string;
  value: StructuredValue;
  children: TreeEntry[];
};

export function treeEntries(value: StructuredValue, parent = ''): TreeEntry[] {
  if (value === null || typeof value !== 'object') return [];
  return Object.entries(value).map(([key, child]) => {
    const path = parent + '/' + key.replaceAll('~', '~0').replaceAll('/', '~1');
    return { key, path, value: child, children: treeEntries(child, path) };
  });
}

export function filterTree(entries: TreeEntry[], query: string): TreeEntry[] {
  const term = query.trim().toLocaleLowerCase();
  if (!term) return entries;
  return entries.flatMap((entry) => {
    const match = [
      entry.key,
      entry.path,
      typeof entry.value !== 'object' || entry.value === null ? String(entry.value) : '',
    ].some((part) => part.toLocaleLowerCase().includes(term));
    const children = filterTree(entry.children, term);
    return match || children.length ? [{ ...entry, children }] : [];
  });
}

export type TableSource = { path: string; rows: StructuredRecord[]; columns: string[] };

export function collectTables(value: StructuredValue, entries: TreeEntry[]): TableSource[] {
  const tables: TableSource[] = [];
  function visit(item: StructuredValue, path: string, children: TreeEntry[]) {
    if (Array.isArray(item) && item.length && item.every(isRecord)) {
      const columns = Array.from(new Set(item.flatMap(Object.keys)));
      if (columns.length) tables.push({ path, rows: item, columns });
    }
    children.forEach((entry) => visit(entry.value, entry.path, entry.children));
  }
  visit(value, '', entries);
  return tables;
}

export function sortRows(rows: StructuredRecord[], column: string, descending: boolean, collator: Intl.Collator) {
  const key = (value: StructuredValue | undefined) => {
    if (value && typeof value === 'object') return JSON.stringify(value);
    return value;
  };
  return rows
    .map((row) => ({ row, sortKey: Object.prototype.hasOwnProperty.call(row, column) ? key(row[column]) : undefined }))
    .sort((left, right) => {
      const a = left.sortKey;
      const b = right.sortKey;
      if (a == null) return b == null ? 0 : 1;
      if (b == null) return -1;
      const order = typeof a === 'number' && typeof b === 'number' ? a - b : collator.compare(String(a), String(b));
      return descending ? -order : order;
    })
    .map(({ row }) => row);
}

export function evidenceKind(
  path: string,
  displayPath?: string,
  source?: string,
): 'diff' | 'log' | 'markdown' | 'data' {
  const names = [path, ...(displayPath?.split(' · ') ?? [])];
  if (names.some((name) => /\.(patch|diff)(?:$|[@?#])/i.test(name))) return 'diff';
  if (
    names.some((name) =>
      /\.(log|jsonl|ndjson|out|err)(?:$|[@?#])|(?:^|[/:._-])(?:stdout|stderr)(?:$|[/:._-])/i.test(name),
    )
  ) {
    return 'log';
  }
  if (names.some((name) => /\.(md|markdown)(?:$|[@?#])/i.test(name))) return 'markdown';
  if (source && /^(?:diff --git |--- [^\n]+\r?\n\+\+\+ )/m.test(source.slice(0, 8192))) return 'diff';
  return 'data';
}

function isChartLabel(value: StructuredValue | undefined): value is string | number {
  return typeof value === 'string' || (typeof value === 'number' && Number.isFinite(value));
}

export function chartableTable(table: TableSource) {
  const label = table.columns.find(
    (column) =>
      /^(?:phase|stage|layer|expert(?:_id)?|arm|component|metric|bucket|k_per_layer)$/i.test(column) &&
      table.rows.filter((row) => isChartLabel(row[column])).length >= 2,
  );
  if (!label) return null;
  const numeric = new Map<string, number>();
  for (const row of table.rows) {
    if (!isChartLabel(row[label])) continue;
    for (const [column, value] of Object.entries(row)) {
      if (column !== label && typeof value === 'number' && Number.isFinite(value)) {
        numeric.set(column, (numeric.get(column) ?? 0) + 1);
      }
    }
  }
  const metrics = table.columns.filter((column) => (numeric.get(column) ?? 0) >= 2);
  return metrics.length ? { table, label, metrics } : null;
}

export type ChartSource = NonNullable<ReturnType<typeof chartableTable>>;

export function chartRows(source: ChartSource, metric: string) {
  return source.table.rows.flatMap((row) => {
    const label = row[source.label];
    const value = row[metric];
    return (typeof label === 'string' || typeof label === 'number') &&
      typeof value === 'number' &&
      Number.isFinite(value)
      ? [{ label: String(label), value }]
      : [];
  });
}

export function resolveEvidenceLink(files: EvidenceFile[], from: EvidenceFile, href: string): string | undefined {
  if (!href || /^(?:[a-z][a-z0-9+.-]*:|\/\/|#)/i.test(href)) return undefined;
  const names = (file: EvidenceFile) => [file.path, ...(file.display_path?.split(' · ') ?? [])];
  let target: string;
  try {
    const base = 'https://evidence.invalid/' + (from.display_path || from.path).split(' · ')[0];
    target = decodeURIComponent(new URL(href, base).pathname).replace(/^\/+/, '');
  } catch {
    return undefined;
  }
  const parts = target.split('/');
  for (let offset = 0; offset < parts.length; offset += 1) {
    const suffix = parts.slice(offset).join('/');
    if (!suffix) return undefined;
    const exact = files.filter((file) => names(file).includes(suffix));
    const matches = exact.length
      ? exact
      : files.filter((file) => names(file).some((name) => name.endsWith('/' + suffix)));
    if (matches.length) {
      const available = matches.filter((file) => file.integrity !== 'missing');
      const best = available.find((file) => file.path === suffix) ?? available[0] ?? matches[0];
      if (
        matches.length === 1 ||
        (best.sha256 && available.length > 0 && available.every((file) => file.sha256 === best.sha256))
      ) {
        return best.path;
      }
      return undefined;
    }
  }
  return undefined;
}
