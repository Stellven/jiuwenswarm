import assert from 'node:assert/strict';
import test from 'node:test';
import {
  capsuleHeadlineRows,
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

test('headline results follow capsule identity independently of historical arm numbering', () => {
  const rows = [
    { cc: null, id: 's' },
    { cc: 'C1', id: 'c1' },
    { cc: 'C2', id: 'c2' },
    { cc: 'C3', id: 'c3-original30' },
    { cc: 'C3', id: 'c3-direct30' },
    { cc: 'C3', id: 'c3-60' },
    { cc: 'C4', id: 'c4' },
    { cc: 'C5', id: 'c5' },
    { cc: 'C5', id: 'c5-mapper-matched' },
    { cc: 'C5', id: 'c5-stock-flags' },
  ];
  const results = (name) => capsuleHeadlineRows(name, rows).map(({ id }) => id);
  assert.deepEqual(results('observability_event_recorder'), ['c1']);
  assert.deepEqual(results('weight_placement_planner'), ['c2']);
  assert.deepEqual(results('expert_weight_cache'), ['c3-original30', 'c3-direct30', 'c3-60']);
  assert.deepEqual(results('expert_demand_predictor'), ['c4']);
  assert.deepEqual(results('batch_layout_mapper'), ['c5', 'c5-mapper-matched', 'c5-stock-flags']);
  assert.deepEqual(results('builder'), []);
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

test('atlas names give every capsule a rule-conforming title and kind, keyed by stable directory ids', async () => {
  const { atlasName, atlasTitle, builderSubtitle, ccKinds } = await import('../src/features/factoryRuns/cc/atlasNames.ts');
  const { ccKind, displayName } = await import('../src/features/factoryRuns/cc/capsuleModel.ts');
  assert.deepEqual([...ccKinds], ['builder', 'tool', 'analysis', 'factory']);
  assert.equal(atlasTitle('expert_weight_cache'), 'Expert weight cache builder');
  assert.equal(atlasTitle('engine.build_expert_weight_cache'), 'Expert weight cache builder');
  assert.equal(atlasTitle('observability.build_runtime_event_recorder@1.1.4'), 'Runtime event recorder builder');
  assert.equal(atlasTitle('factory.lab_client.submit'), 'Capped lab runner');
  assert.equal(atlasTitle('factory.builder'), 'Image assembler');
  assert.equal(atlasTitle('batch_layout_mapper'), 'Batch layout mapper builder');
  assert.equal(atlasTitle('expert_fill'), 'Expert fill builder');
  assert.equal(atlasTitle('unknown.capsule'), undefined);
  assert.equal(
    builderSubtitle(atlasName('expert_weight_cache')),
    'Builds the code for the expert weight cache component in llama.cpp.',
  );
  assert.equal(builderSubtitle(atlasName('lab_client')), undefined);
  const card = { name: 'weight_placement_planner', id: 'placement.build_weight_placement_planner', kind: 'builder' };
  assert.equal(displayName(card), 'Weight placement planner builder');
  assert.equal(ccKind({ name: 'spark_gap_analysis', id: 'factory.spark_gap_analysis', kind: 'analysis' }), 'analysis');
  assert.equal(ccKind({ name: 'cache_size_pareto', id: 'analysis.cache_size_pareto', kind: 'analysis' }), 'tool');
  assert.equal(displayName({ ...card, cc_title: 'Server title' }), 'Server title');
});

test('capsule headline rows lead with the strongest verified quiet result and keep the rest', () => {
  const rows = [
    { cc: 'C3', id: 'c3-original30', grade: 'Verified · quiet ABBA', ttft: '−1.18 / −2.84 s saved' },
    { cc: 'C3', id: 'c3-direct30', grade: 'Verified · quiet ABBA', ttft: '−0.02 / +0.20 s saved' },
    { cc: 'C3', id: 'c3-60', grade: 'Verified · quiet ABBA', ttft: '+27.08 / +92.07 s saved' },
    { cc: 'C3', id: 'c3-screen', grade: 'Screening · pooled A+30', ttft: '+99 / +99 s saved' },
  ];
  assert.deepEqual(capsuleHeadlineRows('expert_weight_cache', rows).map(({ id }) => id),
    ['c3-60', 'c3-direct30', 'c3-original30', 'c3-screen']);
});

test('headline outcomes are derived from the published saved values', async () => {
  const { headlineOutcome, savedValues } = await import('../src/features/factoryRuns/cc/capsuleModel.ts');
  assert.deepEqual(savedValues('−1.18 / −2.84 s saved'), [-1.18, -2.84]);
  assert.equal(headlineOutcome({ ttft: '+27.08 / +92.07 s saved' }), 'faster');
  assert.equal(headlineOutcome({ ttft: '−1.18 / −2.84 s saved' }), 'slower');
  assert.equal(headlineOutcome({ ttft: '−0.02 / +0.20 s saved' }), 'mixed');
  assert.equal(headlineOutcome({ ttft: 'Unmeasured' }), undefined);
});
