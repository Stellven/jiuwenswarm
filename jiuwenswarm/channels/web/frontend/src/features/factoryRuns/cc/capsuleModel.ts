import type { CapsuleCard } from './capsuleApi';
import { atlasName, isCcKind, type CcKind } from './atlasNames.ts';

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

export function capsuleHeadlineRows<T extends { cc: string | null }>(name: string, rows: T[]) {
  const arm = headlineArmForCapsule(name);
  return rows.filter((row) => row.cc === arm);
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
