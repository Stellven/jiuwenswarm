import assert from 'node:assert/strict';
import test from 'node:test';
import {
  externalReportLink,
  linkedEvidence,
  reportFiles,
  reportHeadings,
  reportTable,
} from '../src/features/factoryRuns/reportModel.ts';

function evidence(path, fields = {}) {
  return { path, size: 32, sha256: 'a'.repeat(64), integrity: 'verified', ...fields };
}

test('identifies persisted reports by canonical path or original artifact name', () => {
  const files = [
    evidence('artifacts/hashA', { display_path: 'OPS/runs/session/report.md · another label', integrity: 'mismatch' }),
    evidence('report.md'),
    evidence('analysis/factory-report.md'),
    evidence('artifacts/hashB', { artifact_ids: ['source:attached/report.md@sha256:abc'] }),
    evidence('artifacts/hashC', { display_path: 'prefill-main-report' }),
    evidence('artifacts/hashD', { display_path: 'lab:cell/quality/report.json' }),
    evidence('analysis/summary.md'),
    evidence('reports/raw-metrics.json'),
  ];
  const found = reportFiles(files);
  assert.equal(found[0].file.path, 'report.md');
  assert.deepEqual(
    found.map(({ file }) => file.path).sort(),
    files
      .slice(0, 6)
      .map(({ path }) => path)
      .sort(),
  );
  assert.equal(found.find(({ file }) => file.path.endsWith('hashA')).file.integrity, 'mismatch');
  assert.equal(found.find(({ file }) => file.path.endsWith('hashB')).format, 'markdown');
  assert.equal(found.find(({ file }) => file.path.endsWith('hashC')).format, 'json');
});

test('uses actual Markdown headings and makes repeated and non-Latin labels linkable', () => {
  const markdown = [
    '# Run **report**',
    '```markdown',
    '## Sample heading',
    '```',
    '<h2>Raw HTML heading</h2>',
    '',
    'Validation',
    '----------',
    '',
    '### Validation',
    '### 验证结果',
    '### `Plan` [rationale](#run-report)',
  ].join('\n');
  const headings = reportHeadings(markdown);
  assert.deepEqual(
    headings.map(({ slug, depth }) => [slug, depth]),
    [
      ['run-report', 1],
      ['validation', 2],
      ['validation-1', 3],
      ['验证结果', 3],
      ['plan-rationale', 3],
    ],
  );
  assert.equal(headings[1].offset, markdown.indexOf('\nValidation') + 1);
});

test('resolves relative report links within the indexed evidence and rejects ambiguous or unsafe destinations', () => {
  const report = evidence('artifacts/hashA', { display_path: 'attached/run/report.md' });
  const results = evidence('artifacts/hashB', { display_path: 'attached/run/bench results.json' });
  const peer = evidence('attached/summary.md');
  const files = [report, results, peer];
  assert.equal(linkedEvidence('./bench%20results.json#metrics', report, files), results);
  assert.equal(linkedEvidence('../summary.md', report, files), peer);
  assert.equal(
    linkedEvidence('bench%20results.json', report, [...files, evidence('attached/run/bench results.json')]),
    undefined,
  );
  for (const unsafe of [
    '../../../outside',
    '/attached/summary.md',
    '//evil.test',
    'file:///etc/hosts',
    'javascript:alert(1)',
    '%2Fetc/hosts',
    'foo?x=1',
    '%5Cattached',
    '%00hidden',
    '%',
    'not-recorded.md',
  ]) {
    assert.equal(linkedEvidence(unsafe, report, files), undefined);
  }
});

test('only explicit HTTP and HTTPS links are forwarded as external navigation', () => {
  assert.equal(externalReportLink('https://example.org/evidence#row'), 'https://example.org/evidence#row');
  assert.equal(externalReportLink('http://example.org'), 'http://example.org/');
  for (const unsafe of [
    'https://user:secret@example.org',
    '//example.org',
    'https:/example.org',
    'https://example.org\\redirect',
    'mailto:test@example.org',
    'data:text/html,test',
    'javascript:alert(1)',
  ]) {
    assert.equal(externalReportLink(unsafe), undefined);
  }
});

test('builds compact tables for record arrays without inventing missing data', () => {
  const rows = [
    { arm: 'A', ttft: 2.3 },
    { arm: 'C1', eligible: false, ttft: null },
  ];
  assert.deepEqual(reportTable(rows), { columns: ['arm', 'ttft', 'eligible'], rows });
  for (const values of [
    [],
    ['a', 4],
    [{ arm: 'A', samples: [1, 2] }],
    [{}],
    [Object.fromEntries(new Array(9).fill(null).map((_, index) => [`c${index}`, index]))],
  ]) {
    assert.equal(reportTable(values), undefined);
  }
});
