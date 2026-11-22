import assert from 'node:assert/strict';
import test from 'node:test';
import {
  chartRows,
  chartableTable,
  collectTables,
  evidenceKind,
  filterTree,
  formatKey,
  inspectDocument,
  resolveEvidenceLink,
  sortRows,
  treeEntries,
} from '../src/features/factoryRuns/views/dataModel.ts';

test('reads ontology YAML and JSON with a BOM and leaves source text available to Raw', () => {
  const yaml = inspectDocument('ONTOLOGY.yaml', 'version: "0.2"\nrelations:\n  measures: observation -> quantity\n');
  assert.equal(yaml.format, 'yaml');
  assert.equal(yaml.value.relations.measures, 'observation -> quantity');
  assert.deepEqual(inspectDocument('hashed-file', '\uFEFF {"data":[0,true,null]}').value.data, [0, true, null]);
  assert.deepEqual(inspectDocument('ontology.mmd', 'block-beta\n  columns 3'), { format: 'mermaid' });
  assert.deepEqual(inspectDocument('result.log', 'text'), { format: 'text' });
});

test('rejects custom tags, duplicate keys, cyclic aliases and disproportionate alias expansion', () => {
  assert.equal(inspectDocument('x.yaml', 'run: !!js/function return 1;').issue, 'parseError');
  assert.equal(inspectDocument('x.yaml', 'status: passed\nstatus: failed\n').issue, 'parseError');
  assert.equal(inspectDocument('x.yaml', 'cycle: &cycle [*cycle]').issue, 'structureLimit');
  const shared = ['a: &a [1,2,3,4,5,6,7,8]'];
  for (const [index, key] of [...'bcdef'].entries()) {
    shared.push(
      key +
        ': &' +
        key +
        ' [' +
        Array(8)
          .fill('*' + 'abcde'[index])
          .join(',') +
        ']',
    );
  }
  assert.equal(inspectDocument('x.yaml', shared.join('\n')).issue, 'structureLimit');
  const record = inspectDocument('x.yaml', '__proto__: { untouched: true }');
  assert.equal(Object.getPrototypeOf(record.value).untouched, undefined);
});

test('filters nested keys and values while retaining navigable parent paths', () => {
  const entries = treeEntries({ 'a/b': { '~nested': 'Weights retained' }, skip: 11 });
  const [matching] = filterTree(entries, 'weights');
  assert.equal(matching.path, '/a~1b');
  assert.equal(matching.children[0].path, '/a~1b/~0nested');
  assert.deepEqual(filterTree(entries, 'missing'), []);
  assert.equal(formatKey('median_ttft_ms'), 'Median TTFT ms');
});

test('collects nested arrays, uses a union of columns, sorts numbers, and leaves missing cells last', () => {
  const data = {
    results: [
      { arm: 'A', latency_ms: 10 },
      { arm: 'S', latency_ms: 2 },
      { arm: 'D', notes: 'pending' },
    ],
  };
  const [table] = collectTables(data, treeEntries(data));
  assert.equal(table.path, '/results');
  assert.deepEqual(table.columns, ['arm', 'latency_ms', 'notes']);
  const collator = new Intl.Collator('en', { numeric: true });
  assert.deepEqual(
    sortRows(table.rows, 'latency_ms', false, collator).map((row) => row.arm),
    ['S', 'A', 'D'],
  );
  assert.deepEqual(
    sortRows(table.rows, 'latency_ms', true, collator).map((row) => row.arm),
    ['A', 'S', 'D'],
  );
  const chart = chartableTable(table);
  assert.deepEqual(chart.metrics, ['latency_ms']);
  assert.deepEqual(chartRows(chart, 'latency_ms'), [
    { label: 'A', value: 10 },
    { label: 'S', value: 2 },
  ]);
});

test('dispatches evidence by file path, artifact aliases and patch headers', () => {
  assert.equal(evidenceKind('artifacts/sha', 'build.log · next.txt'), 'log');
  assert.equal(evidenceKind('artifacts/sha', 'owner_report.md'), 'markdown');
  assert.equal(evidenceKind('capsules/a.diff', 'aliased-output'), 'diff');
  assert.equal(evidenceKind('artifacts/sha', 'source:builder@abc', 'diff --git a/x b/x\n'), 'diff');
  assert.equal(evidenceKind('artifacts/sha', 'profile.json'), 'data');
});

test('report links resolve to inventoried source files and keep ambiguous aliases inert', () => {
  const report = { path: 'artifacts/report', display_path: 'contracts/report.md' };
  const ontology = { path: 'artifacts/ontology', display_path: 'ontology/overview.mmd', sha256: 'a' };
  const duplicate = { path: 'ontology/overview.mmd', sha256: 'a' };
  const files = [report, ontology, duplicate];
  assert.equal(resolveEvidenceLink(files, report, '../../../../inputs/ontology/overview.mmd'), duplicate.path);
  assert.equal(resolveEvidenceLink(files, report, 'https://example.test/ontology/overview.mmd'), undefined);
  assert.equal(resolveEvidenceLink(files, report, '/api/factory/launch'), undefined);
  assert.equal(
    resolveEvidenceLink(
      [report, { ...ontology, display_path: 'other/data.json' }, { path: 'alt/data.json', sha256: 'b' }],
      report,
      'data.json',
    ),
    undefined,
  );
});

test('routing analysis coverage uses recorded k values as categories', () => {
  const rows = [
    { k_per_layer: 16, fraction_new_routes: 0.31 },
    { k_per_layer: 32, fraction_new_routes: 0.44 },
  ];
  const [table] = collectTables(rows, treeEntries(rows));
  const chart = chartableTable(table);
  assert.equal(chart.label, 'k_per_layer');
  assert.deepEqual(
    chartRows(chart, 'fraction_new_routes').map((row) => row.label),
    ['16', '32'],
  );
});
