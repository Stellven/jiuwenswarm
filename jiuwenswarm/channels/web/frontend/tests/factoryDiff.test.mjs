import assert from 'node:assert/strict';
import test from 'node:test';
import { buildDiffTree, pairDiffLines, readDiff } from '../src/features/factoryRuns/views/diffModel.ts';

test('parses multi-file Git patches with email signatures and builds a file tree', () => {
  const result = readDiff(
    [
      'Subject: [PATCH] Example',
      '',
      'diff --git a/src/a.cc b/src/a.cc',
      '--- a/src/a.cc',
      '+++ b/src/a.cc',
      '@@ -8,2 +8,3 @@ void run()',
      ' shared',
      '-old',
      '+new',
      '+extra',
      'diff --git a/src/sub/b.cc b/src/sub/b.cc',
      'new file mode 100644',
      '--- /dev/null',
      '+++ b/src/sub/b.cc',
      '@@ -0,0 +1 @@',
      '+created',
      '-- ',
      '2.34.1',
      '',
    ].join('\n'),
  );
  assert.equal(result.added, 3);
  assert.equal(result.removed, 1);
  assert.deepEqual(
    result.files.map(({ path }) => path),
    ['src/a.cc', 'src/sub/b.cc'],
  );
  assert.equal(result.files[0].hunks[0].header, '@@ -8,2 +8,3 @@ void run()');
  assert.equal(result.files[1].hunks[0].header, '@@ -0,0 +1 @@');
  const [src] = buildDiffTree(result.files);
  assert.equal(src.kind, 'directory');
  assert.equal(src.children[0].name, 'a.cc');
  assert.equal(src.children[1].children[0].name, 'b.cc');
});

test('aligns replacements and preserves line numbers and newline notes on the relevant side', () => {
  const result = readDiff(
    [
      '--- file',
      '+++ file',
      '@@ -2,3 +2,2 @@',
      ' context',
      '-old one',
      '-old two',
      '\\ No newline at end of file',
      '+new one',
      '',
    ].join('\r\n'),
  );
  const rows = pairDiffLines(result.files[0].hunks[0].lines);
  assert.equal(rows[0].before, rows[0].after);
  assert.equal(rows[1].before.oldNumber, 3);
  assert.equal(rows[1].after.newNumber, 3);
  assert.equal(rows[2].before.oldNumber, 4);
  assert.equal(rows[2].before.note, 'No newline at end of file');
  assert.equal(rows[2].after, undefined);
});

test('handles renamed and deleted files and leaves other content to the raw view', () => {
  const result = readDiff(
    [
      'diff --git a/old.cc b/new.cc',
      'similarity index 100%',
      'rename from old.cc',
      'rename to new.cc',
      'diff --git a/deleted.cc b/deleted.cc',
      'deleted file mode 100644',
      '--- a/deleted.cc',
      '+++ /dev/null',
      '@@ -1 +0,0 @@',
      '-removed',
      '',
    ].join('\n'),
  );
  assert.equal(result.files[0].path, 'new.cc');
  assert.equal(result.files[0].previousPath, 'old.cc');
  assert.equal(result.files[1].path, 'deleted.cc');
  assert.equal(result.removed, 1);
  assert.equal(readDiff('ordinary evidence'), null);
  assert.equal(readDiff('--- a/file\n+++ b/file\n@@ -1 +1 @@\n'), null);
});
