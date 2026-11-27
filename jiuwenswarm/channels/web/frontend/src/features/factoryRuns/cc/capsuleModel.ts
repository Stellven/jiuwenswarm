import type { CapsuleCard } from './capsuleApi';
import { atlasName, isCcKind, type CcKind } from './atlasNames.ts';
import { inferenceCapsules } from './inferenceCapsuleCopy.ts';

const headlineArms = new Map([
  ['observability_event_recorder', 'C1'],
  ['weight_placement_planner', 'C2'],
  ['expert_weight_cache', 'C3'],
  ['expert_demand_predictor', 'C4'],
  ['batch_layout_mapper', 'C5'],
]);

export function headlineArmForCapsule(name: string) {
  return headlineArms.get(name);
}

/** Signed "saved" values from a headline metric such as "+27.08 / +92.07 s saved". */
export function savedValues(value: unknown): number[] {
  if (typeof value !== 'string' || !/saved/.test(value)) return [];
  return [...value.replace(/\u2212/g, '-').matchAll(/[+-]?\d+(?:\.\d+)?/g)].map((match) => Number(match[0]));
}

/** Evidence grade rank: verified quiet comparisons lead, then verified functional checks, then screening. */
export function gradeRank(grade: unknown): number {
  const text = typeof grade === 'string' ? grade.toLowerCase() : '';
  if (text.startsWith('verified')) return /quiet|abba/.test(text) ? 3 : 2;
  return text.startsWith('screening') ? 1 : 0;
}

/** Outcome of a row derived from its published TTFT saved values. */
export function headlineOutcome(row: { ttft?: unknown }): 'faster' | 'slower' | 'mixed' | undefined {
  const values = savedValues(row.ttft);
  if (!values.length) return undefined;
  if (values.every((value) => value > 0)) return 'faster';
  if (values.every((value) => value < 0)) return 'slower';
  return 'mixed';
}

/**
 * Headline rows for one capsule, strongest verified evidence first: grade (quiet ABBA before
 * functional before screening), then the total paired TTFT saved. Ties keep publication order.
 */
export function capsuleHeadlineRows<T extends { cc: string | null; grade?: unknown; ttft?: unknown }>(
  name: string,
  rows: T[],
) {
  const arm = headlineArmForCapsule(name);
  const total = (row: T) => savedValues(row.ttft).reduce((sum, value) => sum + value, 0);
  return rows
    .filter((row) => row.cc === arm)
    .map((row, index) => ({ row, index }))
    .sort((a, b) => gradeRank(b.row.grade) - gradeRank(a.row.grade) || total(b.row) - total(a.row) || a.index - b.index)
    .map(({ row }) => row);
}

export function readableName(value: string): string {
  return value
    .replaceAll('_', ' ')
    .replace(/\b(?:cc|gpu|cpu|kv|ssd|io|ttft)\b/g, (initialism) => initialism.toUpperCase())
    .replace(/^[a-z]/, (letter) => letter.toUpperCase());
}

export function displayName(capsule: Pick<CapsuleCard, 'name' | 'id'> & Partial<CapsuleCard>): string {
  return (
    capsule.cc_title ||
    atlasName(capsule.name)?.title ||
    atlasName(capsule.id)?.title ||
    capsule.title ||
    capsule.subcomponent ||
    readableName(capsule.name)
  );
}

export function capsuleDisplayTitle(capsule: Pick<CapsuleCard, 'name' | 'id'> & Partial<CapsuleCard>): string {
  return inferenceCapsules[capsule.id]?.title ?? displayName(capsule);
}

/** Atlas CC kind: builder, tool, analysis or factory worker. */
export function ccKind(capsule: Pick<CapsuleCard, 'name' | 'id'> & Partial<CapsuleCard>): CcKind {
  if (isCcKind(capsule.cc_kind)) return capsule.cc_kind;
  const kind = atlasName(capsule.name)?.kind || atlasName(capsule.id)?.kind;
  if (kind) return kind;
  if (capsule.kind === 'builder' || capsule.kind === 'analysis') return capsule.kind;
  return 'factory';
}

export function plainDescription(value: string): string {
  return value
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\*\*|`/g, '')
    .replace(/ at [a-f0-9]{8,40}(?=[\s.,])/gi, '')
    .split(/(?<=[.!?])\s+(?=[A-Z])/)
    .filter((sentence, index) => index === 0 || !/^(Read|Start with|See) the\b/.test(sentence))
    .slice(0, 2)
    .join(' ');
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export function findCapsules(value: unknown, capsules: CapsuleCard[]): CapsuleCard[] {
  if (!capsules.length || value == null) return [];
  const matches = new Set<string>();
  const aliases = capsules.map(({ name, id }) => ({
    name,
    id,
    slug: name.replaceAll('_', '-'),
    // The canonical ID is also the prefix of a native capability such as .verify.
    mention: new RegExp(`(?:^|[^\\w.])${id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?=$|[^\\w])`, 'i'),
  }));

  function visit(item: unknown, depth: number) {
    if (depth > 12 || matches.size === capsules.length) return;
    if (typeof item === 'string') {
      const text = item.toLowerCase();
      const tokens = text.split(/[^a-z0-9_-]+/);
      for (const { name, id, slug, mention } of aliases) {
        if (
          text === id.toLowerCase() ||
          text === name ||
          (name.includes('_') &&
            (tokens.includes(name) ||
              tokens.includes(slug) ||
              tokens.some((token) => ('-' + token + '-').includes('-' + slug + '-')))) ||
          mention.test(item)
        ) {
          matches.add(name);
        }
      }
    } else if (Array.isArray(item)) {
      for (const child of item) visit(child, depth + 1);
    } else if (isRecord(item)) {
      for (const child of Object.values(item)) visit(child, depth + 1);
    }
  }

  visit(value, 0);
  return capsules.filter((capsule) => matches.has(capsule.name));
}

type MarkdownSection = { heading: string; source: string };
export function markdownSections(markdown: string): MarkdownSection[] {
  const sections: MarkdownSection[] = [];
  let heading = '';
  let lines: string[] = [];
  let fence = '';
  for (const line of markdown.split(/\r?\n/)) {
    const marker = /^\s*(`{3,}|~{3,})/.exec(line)?.[1];
    if (marker && !fence) fence = marker;
    else if (marker && marker[0] === fence[0] && marker.length >= fence.length) fence = '';
    const title = !fence && /^#{1,3}\s+(.+?)\s*#*$/.exec(line);
    if (title) {
      if (lines.some((value) => value.trim())) sections.push({ heading, source: lines.join('\n').trim() });
      heading = title[1];
      lines = [];
    } else {
      lines.push(line);
    }
  }
  if (lines.some((value) => value.trim())) sections.push({ heading, source: lines.join('\n').trim() });
  return sections;
}

export function localMaterial(from: string, href: string, known: Set<string>): string | undefined {
  if (!href || href.startsWith('/') || href.includes(':')) return undefined;
  try {
    const [target] = href.split(/[?#]/);
    if (!target) return undefined;
    const path = from.split('/').slice(0, -1);
    for (const part of decodeURIComponent(target).split('/')) {
      if (part === '..') {
        if (!path.length) return undefined;
        path.pop();
      } else if (part && part !== '.') {
        path.push(part);
      }
    }
    const relative = path.join('/');
    return known.has(relative) ? relative : undefined;
  } catch {
    return undefined;
  }
}

export type DataRows = { path: string; rows: Record<string, unknown>[] };

export function tableData(value: unknown): DataRows[] {
  const datasets: DataRows[] = [];
  function visit(item: unknown, path: string, depth: number) {
    if (depth > 4 || datasets.length >= 30) return;
    if (Array.isArray(item)) {
      if (item.length && item.every(isRecord)) datasets.push({ path, rows: item });
    } else if (isRecord(item)) {
      const entries = Object.entries(item);
      if (entries.length > 1 && entries.every(([, entry]) => isRecord(entry))) {
        const rows = entries.map(([name, entry]) => ({ name, ...(entry as Record<string, unknown>) }));
        if (numericColumns(rows).length) datasets.push({ path, rows });
      }
      for (const [key, entry] of entries) visit(entry, path ? `${path}.${key}` : key, depth + 1);
    }
  }
  visit(value, '', 0);
  return datasets;
}

export function numericColumns(rows: Record<string, unknown>[]): string[] {
  const keys = [...new Set(rows.flatMap(Object.keys))];
  return keys.filter(
    (key) =>
      rows.some((row) => typeof row[key] === 'number' && Number.isFinite(row[key])) &&
      rows.every((row) => row[key] == null || (typeof row[key] === 'number' && Number.isFinite(row[key]))),
  );
}
