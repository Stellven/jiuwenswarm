import { fromMarkdown } from 'mdast-util-from-markdown';
import { gfmFromMarkdown } from 'mdast-util-gfm';
import { gfm } from 'micromark-extension-gfm';
import type { RootContent } from 'mdast';
import type { EvidenceFile } from './api';

function evidencePaths(file: EvidenceFile): string[] {
  const aliases = file.display_path?.split(' · ') ?? [];
  for (const id of file.artifact_ids ?? []) {
    const source = /^source:(.+)@sha256:[^/]+$/.exec(id);
    if (source) aliases.push(source[1]);
  }
  return [...new Set([file.path, ...aliases])];
}

export type ReportFile = { file: EvidenceFile; format: 'markdown' | 'json' | 'html'; label: string };

export function reportFiles(files: EvidenceFile[]): ReportFile[] {
  const candidates = files.flatMap((file) =>
    evidencePaths(file).flatMap<ReportFile & { rank: number; revision: number }>((label) => {
      const name = label.split('/').pop()?.toLowerCase() ?? '';
      const match = /(?:^|[-_.:])report(?:[-_.]v(\d+))?(?:\.(md|json|html?))?$/.exec(name);
      if (match) {
        const format = match[2] === 'md' ? 'markdown' : match[2]?.startsWith('htm') ? 'html' : 'json';
        const rank = { html: 0, markdown: 1, json: 2 }[format];
        return [{ file, label, format, rank, revision: Number(match[1]) || 0 }];
      }
      return [];
    }),
  );
  const ordered = candidates.sort(
    (a, b) =>
      a.rank - b.rank ||
      b.revision - a.revision ||
      Number(b.file.path.toLowerCase() === 'report.md') - Number(a.file.path.toLowerCase() === 'report.md') ||
      a.label.localeCompare(b.label),
  );
  const unique = new Map<string, ReportFile>();
  for (const { file, label, format } of ordered) {
    if (!unique.has(file.path)) unique.set(file.path, { file, label, format });
  }
  return [...unique.values()];
}

type ReportHeading = { depth: number; title: string; offset: number; slug: string };

function headingText(node: RootContent): string {
  if (node.type === 'html') return '';
  if ('alt' in node) return node.alt ?? '';
  if ('value' in node) return node.value;
  if ('children' in node) return node.children.map(headingText).join('');
  return '';
}

export function reportHeadings(markdown: string): ReportHeading[] {
  const headings: ReportHeading[] = [];
  const used = new Set<string>();
  const tree = fromMarkdown(markdown, { extensions: [gfm()], mdastExtensions: [gfmFromMarkdown()] });
  function visit(node: RootContent) {
    if (node.type === 'heading' && node.position?.start.offset !== undefined) {
      const title = headingText(node).trim();
      if (!title) return;
      const base =
        title
          .toLowerCase()
          .replace(/[^\p{L}\p{N}\p{M}\s\-_]/gu, '')
          .replace(/\s/g, '-') || 'section';
      let slug = base;
      for (let suffix = 1; used.has(slug); suffix += 1) slug = `${base}-${suffix}`;
      used.add(slug);
      headings.push({ depth: node.depth, title, offset: node.position.start.offset, slug });
    } else if ('children' in node) {
      node.children.forEach(visit);
    }
  }
  tree.children.forEach(visit);
  return headings;
}

function confinedPath(path: string): string | undefined {
  if (/^(?:\/|[a-z][a-z\d+.-]*:)|[\\\u0000-\u001f\u007f]/i.test(path)) return undefined;
  const parts: string[] = [];
  for (const part of path.split('/')) {
    if (part === '..') {
      if (!parts.length) return undefined;
      parts.pop();
    } else if (part && part !== '.') {
      parts.push(part);
    }
  }
  return parts.join('/') || undefined;
}

export function linkedEvidence(href: string, report: EvidenceFile, files: EvidenceFile[]): EvidenceFile | undefined {
  let relative;
  try {
    relative = decodeURIComponent(href.split('#')[0]);
  } catch {
    return undefined;
  }
  if (!relative || /^(?:\/|[a-z][a-z\d+.-]*:)|[\\?:%\u0000-\u001f\u007f]/i.test(relative)) return undefined;

  const destinations = new Set(
    evidencePaths(report)
      .filter((path) => confinedPath(path))
      .map((path) => confinedPath(path.slice(0, path.lastIndexOf('/') + 1) + relative))
      .filter(Boolean),
  );
  const matches = files.filter((file) => evidencePaths(file).some((path) => destinations.has(confinedPath(path))));
  return matches.length === 1 ? matches[0] : undefined;
}

export function evidenceIndex(files: EvidenceFile[]) {
  const indexed = new Map<string, EvidenceFile | null>();
  for (const file of files) {
    for (const key of [...evidencePaths(file), ...(file.artifact_ids ?? [])]) {
      const previous = indexed.get(key);
      if (previous?.path === file.path || previous === null) continue;
      indexed.set(key, previous ? null : file);
    }
  }
  return indexed;
}

export function externalReportLink(href: string): string | undefined {
  if (!/^https?:\/\//i.test(href) || /[\\\u0000-\u0020\u007f]/.test(href)) return undefined;
  try {
    const url = new URL(href);
    return url.username || url.password ? undefined : url.href;
  } catch {
    return undefined;
  }
}

type ReportCell = string | number | boolean | null;

export function isReportCell(value: unknown): value is ReportCell {
  return value === null || typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean';
}

export function reportTable(values: unknown[]) {
  if (!values.length) return undefined;
  const columns = new Set<string>();
  const rows: Record<string, ReportCell>[] = [];
  for (const value of values) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined;
    for (const [key, cell] of Object.entries(value)) {
      if (!isReportCell(cell)) return undefined;
      columns.add(key);
      if (columns.size > 8) return undefined;
    }
    rows.push(value as Record<string, ReportCell>);
  }
  return columns.size ? { columns: [...columns], rows } : undefined;
}
