import { parsePatch, type StructuredPatchHunk } from 'diff';

export type DiffLine = {
  kind: 'added' | 'removed' | 'context';
  text: string;
  oldNumber?: number;
  newNumber?: number;
  note?: string;
};

type DiffHunk = { header: string; lines: DiffLine[] };
type DiffStats = { added: number; removed: number };

export type DiffFile = DiffStats & {
  id: string;
  path: string;
  previousPath?: string;
  binary: boolean;
  hunks: DiffHunk[];
};

export type DiffTreeNode =
  | { kind: 'file'; name: string; file: DiffFile }
  | { kind: 'directory'; name: string; path: string; children: DiffTreeNode[] };

function readHunk(hunk: StructuredPatchHunk, header: string): DiffHunk {
  let oldNumber = hunk.oldStart;
  let newNumber = hunk.newStart;
  const lines: DiffLine[] = [];

  for (const rawLine of hunk.lines) {
    if (rawLine.startsWith('\\')) {
      const previous = lines.at(-1);
      if (previous) previous.note = rawLine.slice(1).trimStart();
    } else {
      const text = rawLine.slice(1);
      if (rawLine.startsWith('+')) lines.push({ kind: 'added', text, newNumber: newNumber++ });
      else if (rawLine.startsWith('-')) lines.push({ kind: 'removed', text, oldNumber: oldNumber++ });
      else lines.push({ kind: 'context', text, oldNumber: oldNumber++, newNumber: newNumber++ });
    }
  }
  return { header, lines };
}

export function readDiff(content: string): (DiffStats & { files: DiffFile[] }) | null {
  if (!/^(?:diff --git |--- |@@ )/m.test(content)) return null;
  try {
    const normalized = content.replace(/\r\n/g, '\n');
    // Git format-patch adds a signature after the final hunk. Its "-- " line
    // looks like a deletion to a unified-diff parser.
    const patchText = normalized.replace(/\n-- \n\d+\.\d+(?:\.\d+)?[^\n]*\n*$/, '\n');
    const patches = parsePatch(patchText);
    const headers = patchText.match(/^@@ .*$/gm) ?? [];
    let headerIndex = 0;
    const files: DiffFile[] = [];
    let added = 0;
    let removed = 0;
    for (const patch of patches) {
      if (!patch.oldFileName && !patch.newFileName && !patch.hunks.length) continue;
      if (patch.hunks.some((hunk) => !Number.isFinite(hunk.oldStart) || !Number.isFinite(hunk.newStart))) return null;
      const oldPath = patch.isGit ? patch.oldFileName?.replace(/^a\//, '') : patch.oldFileName;
      const newPath = patch.isGit ? patch.newFileName?.replace(/^b\//, '') : patch.newFileName;
      const path = (newPath === '/dev/null' ? oldPath : newPath) || oldPath || '';
      const hunks = patch.hunks.map((hunk) => readHunk(hunk, headers[headerIndex++]));
      const file: DiffFile = {
        id: `${path}:${files.length}`,
        path,
        previousPath: oldPath && oldPath !== '/dev/null' && oldPath !== path ? oldPath : undefined,
        binary: Boolean(patch.isBinary),
        hunks,
        added: 0,
        removed: 0,
      };
      for (const hunk of hunks) {
        for (const { kind } of hunk.lines) {
          if (kind === 'added') file.added++;
          if (kind === 'removed') file.removed++;
        }
      }
      files.push(file);
      added += file.added;
      removed += file.removed;
    }
    return files.length ? { files, added, removed } : null;
  } catch {
    return null;
  }
}

type SplitRow = { before?: DiffLine; after?: DiffLine };

export function pairDiffLines(lines: DiffLine[]): SplitRow[] {
  const rows: SplitRow[] = [];
  let before: DiffLine[] = [];
  let after: DiffLine[] = [];
  function flushChanges() {
    for (let i = 0; i < Math.max(before.length, after.length); i++) {
      rows.push({ before: before[i], after: after[i] });
    }
    before = [];
    after = [];
  }
  for (const line of lines) {
    if (line.kind === 'removed') before.push(line);
    else if (line.kind === 'added') after.push(line);
    else {
      flushChanges();
      rows.push({ before: line, after: line });
    }
  }
  flushChanges();
  return rows;
}

export function buildDiffTree(files: DiffFile[]): DiffTreeNode[] {
  const roots: DiffTreeNode[] = [];
  const directories = new Map<string, DiffTreeNode & { kind: 'directory' }>();
  for (const file of files) {
    const parts = file.path.split('/').filter(Boolean);
    const name = parts.pop() ?? '';
    let children = roots;
    let path = '';
    for (const folder of parts) {
      path = `${path}/${folder}`;
      let directory = directories.get(path);
      if (!directory) {
        directory = { kind: 'directory', name: folder, path, children: [] };
        directories.set(path, directory);
        children.push(directory);
      }
      children = directory.children;
    }
    children.push({ kind: 'file', name, file });
  }
  return roots;
}
