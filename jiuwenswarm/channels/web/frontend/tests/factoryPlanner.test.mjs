import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const en = JSON.parse(readFileSync(path.join(ROOT, 'src', 'i18n', 'locales', 'en.json'), 'utf8'));
const zh = JSON.parse(readFileSync(path.join(ROOT, 'src', 'i18n', 'locales', 'zh.json'), 'utf8'));

function flatten(obj, prefix = '', out = new Set()) {
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    out.add(key);
    if (v && typeof v === 'object' && !Array.isArray(v)) flatten(v, key, out);
  }
  return out;
}

test('Planner nav and factoryPlanner translation keys match symmetrically between en and zh', () => {
  assert.equal(en.nav.planner, 'Planner');
  assert.equal(zh.nav.planner, '规划器');

  const enKeys = [...flatten(en.factoryPlanner, 'factoryPlanner')].sort();
  const zhKeys = [...flatten(zh.factoryPlanner, 'factoryPlanner')].sort();
  assert.deepEqual(zhKeys, enKeys);
});

test('SessionSidebar promotes planner to a top-level mainNavItem', () => {
  const sidebar = readFileSync(path.join(ROOT, 'src', 'components', 'SessionSidebar', 'index.tsx'), 'utf8');
  const mainNavBlock = sidebar.slice(sidebar.indexOf('const mainNavItems'), sidebar.indexOf('export function SessionSidebar'));
  assert.match(mainNavBlock, /key:\s*'planner',\s*labelKey:\s*'nav\.planner'/);
});

test('AblationTab and locale copy never expose B0 or T1 codenames', () => {
  const ablationTsx = readFileSync(
    path.join(ROOT, 'src', 'features', 'factoryRuns', 'planner', 'AblationTab.tsx'),
    'utf8',
  );
  for (const src of [ablationTsx, JSON.stringify(en.factoryPlanner.ablationTab), JSON.stringify(zh.factoryPlanner.ablationTab)]) {
    assert.doesNotMatch(src, /\b(B0|T1)\b/);
  }
});

test('WorkflowLibraryTab is removed and PlannerPage renders autonomous steps + CC bindings directly', () => {
  const wfPath = path.join(ROOT, 'src', 'features', 'factoryRuns', 'planner', 'WorkflowLibraryTab.tsx');
  assert.equal(existsSync(wfPath), false);
  const plannerPage = readFileSync(path.join(ROOT, 'src', 'features', 'factoryRuns', 'planner', 'PlannerPage.tsx'), 'utf8');
  const plannerApi = readFileSync(path.join(ROOT, 'src', 'features', 'factoryRuns', 'planner', 'plannerApi.ts'), 'utf8');
  assert.doesNotMatch(plannerPage, /WorkflowLibraryTab|custom_workflow|slot_bindings/);
  assert.doesNotMatch(plannerApi, /WorkflowChoice|distillWorkflow|workflowDetail/);
  assert.match(plannerPage, /factoryPlanner\.decisions\.steps/);
  assert.match(plannerApi, /export type PlanStep/);
  assert.equal('workflows' in en.factoryPlanner.tabs, false);
  assert.equal('workflowTab' in en.factoryPlanner, false);
});

test('AblationTab and locales render 3-way Old M1 vs M2 Static vs TLC-Verified comparison', () => {
  const ablationTsx = readFileSync(
    path.join(ROOT, 'src', 'features', 'factoryRuns', 'planner', 'AblationTab.tsx'),
    'utf8',
  );
  assert.match(en.factoryPlanner.ablationTab.title, /Old M1.*M2 Static.*TLC-Verified Planner/);
  assert.match(zh.factoryPlanner.ablationTab.title, /Old M1.*M2 Static.*TLC-Verified Planner/);
  assert.match(ablationTsx, /m1_legacy/);
  assert.match(ablationTsx, /m1_limitations/);
  assert.match(ablationTsx, /ablationReportUrl/);
  assert.match(en.factoryPlanner.handoff.title, /Sole Verified Output Ready: graph\.json/);
  assert.match(zh.factoryPlanner.handoff.title, /唯一可信输出已就绪：graph\.json/);
  assert.equal(en.factoryPlanner.downloadGraphJson, 'Download graph.json');
  assert.equal(zh.factoryPlanner.downloadGraphJson, '下载 graph.json');
});
