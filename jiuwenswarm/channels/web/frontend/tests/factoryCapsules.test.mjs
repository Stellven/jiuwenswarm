import assert from 'node:assert/strict';
import test from 'node:test';
import {
  findCapsules,
  localMaterial,
  markdownSections,
  numericColumns,
  tableData,
} from '../src/features/factoryRuns/cc/capsuleModel.ts';
import { capsuleHref, readFactoryEntry, runHref } from '../src/features/factoryRuns/cc/navigation.ts';

test('capsule and replay links round-trip hashes without confusing file paths with navigation', () => {
  assert.deepEqual(readFactoryEntry(capsuleHref('analysis.expert_routing_profile')), {
    view: 'capabilityCapsules',
    capsule: 'analysis.expert_routing_profile',
  });
  const file = 'artifacts/aa/report #1+raw.json';
  assert.deepEqual(readFactoryEntry(runHref('recorded-run', file)), { view: 'factoryRuns', run: 'recorded-run', file });
  assert.equal(readFactoryEntry('#capsules/%E0%A4%A'), undefined);
  assert.equal(readFactoryEntry('#factory-run/..%2Fexternal'), undefined);
  assert.equal(readFactoryEntry('#research_bootstrap=placeholder'), undefined);
});

test('capsule chips resolve qualified tools and explicit aliases without matching generic unqualified words', () => {
  const builder = { name: 'builder', id: 'factory.builder' };
  const recorder = { name: 'observability_event_recorder', id: 'observability.build_runtime_event_recorder' };
  const routing = { name: 'routing_profile_analysis', id: 'analysis.expert_routing_profile' };
  const catalog = [builder, recorder, routing];
  const value = {
    report: { analysis: { call: 'analysis.expert_routing_profile.analyze' } },
    artifact: 'files/observability_event_recorder.diff',
    summary: 'This uses a builder capsule.',
  };
  assert.deepEqual(findCapsules(value, catalog), [recorder, routing]);
  assert.deepEqual(
    findCapsules('factory.builder.build and notfactory.builder x.analysis.expert_routing_profile', catalog),
    [builder],
  );
  assert.deepEqual(findCapsules({ component: 'builder' }, catalog), [builder]);
});

test('markdown excerpts ignore headings inside code fences and resolve only known capsule files', () => {
  const source = '# Guide\n\nFirst steps.\n\n```bash\n# printed output\n```\n\n## Done\n\nPass.';
  const sections = markdownSections(source);
  assert.equal(sections.length, 2);
  assert.match(sections[0].source, /# printed output/);
  assert.deepEqual(sections[1], { heading: 'Done', source: 'Pass.' });
  const known = new Set(['METHOD.md', 'samples/gate.cpp']);
  assert.equal(localMaterial('GUIDE.md', 'samples/gate.cpp#anchor', known), 'samples/gate.cpp');
  assert.equal(localMaterial('samples/README.md', '../METHOD.md', known), 'METHOD.md');
  assert.equal(localMaterial('GUIDE.md', '%2e%2e/METHOD.md', known), undefined);
  assert.equal(localMaterial('GUIDE.md', 'javascript:doSomething()', known), undefined);
});

test('analysis tables discover measured data and chart only consistently numeric columns', () => {
  const rows = [
    { phase: 'prefill', elapsed_ms: 12, count: 2 },
    { phase: 'decode', elapsed_ms: 8, count: 'unknown' },
  ];
  assert.deepEqual(tableData({ results: { rows } }), [{ path: 'results.rows', rows }]);
  assert.deepEqual(numericColumns(rows), ['elapsed_ms']);
  assert.deepEqual(tableData({ before: { ttft_s: 9 }, after: { ttft_s: 6 } })[0].rows, [
    { name: 'before', ttft_s: 9 },
    { name: 'after', ttft_s: 6 },
  ]);
  assert.deepEqual(tableData({ prose: 'Diagnostic only.', rows: [] }), []);
});
