import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { buildSync } from 'esbuild';
import { createInstance } from 'i18next';
import { JSDOM } from 'jsdom';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { I18nextProvider } from 'react-i18next';

test('Demo Task graph shows one responsive chain and keeps node and capsule actions independent', async (t) => {
  const cache = mkdtempSync(fileURLToPath(new URL('../node_modules/.demo-task-chain-test-', import.meta.url)));
  t.after(() => rmSync(cache, { recursive: true, force: true }));
  const bundle = join(cache, 'chain.mjs');
  buildSync({
    stdin: {
      contents: [
        "export { DemoTaskChain } from './views/DemoTaskChain';",
        "export { BoundCapsules } from './cc/BoundCapsules';",
        "export { CapsuleLinksContext } from './cc/CapsuleChips';",
        "export { NodeVerifier } from './views/TimelineVerifier';",
      ].join('\n'),
      resolveDir: fileURLToPath(new URL('../src/features/factoryRuns/', import.meta.url)),
    },
    outfile: bundle,
    bundle: true,
    packages: 'external',
    platform: 'node',
    format: 'esm',
    jsx: 'automatic',
    loader: { '.css': 'empty' },
  });
  const { DemoTaskChain, BoundCapsules, CapsuleLinksContext, NodeVerifier } = await import(pathToFileURL(bundle));
  const i18n = createInstance();
  const translation = JSON.parse(readFileSync(new URL('../src/i18n/locales/en.json', import.meta.url)));
  await i18n.init({ lng: 'en', resources: { en: { translation } } });

  const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost/' });
  let resize;
  const globals = {
    window: dom.window,
    document: dom.window.document,
    getComputedStyle: () => ({ columnGap: '26px' }),
    IS_REACT_ACT_ENVIRONMENT: true,
    ResizeObserver: class {
      constructor(callback) {
        resize = (width) => callback([{ contentRect: { width } }]);
      }
      observe() {}
      disconnect() {}
    },
  };
  const previous = Object.fromEntries(Object.keys(globals).map((key) => [key, globalThis[key]]));
  Object.assign(globalThis, globals);
  const root = createRoot(document.getElementById('root'));
  t.after(async () => {
    await act(() => root.unmount());
    Object.assign(globalThis, previous);
    dom.window.close();
  });

  const catalog = [{ id: 'engine.kv_reuse_lab', name: 'kv_reuse_lab' }];
  const bindings = ['factory.capped_runner', 'factory.builder', 'factory.lab_manager', 'factory.node_check'];
  const record = { id: 'node-check:plan_prefix_store:plan:1:1234', output: 'plan' };
  const ccVerifiers = {
    'engine.kv_reuse_lab': { status: 'pass', records: [record] },
    'factory.capped_runner': { status: 'not-run', records: [] },
  };
  const nodeVerifier = { status: 'fail', records: [record] };
  const nodes = [
    ['pin_inputs', 'done', []],
    ['plan_prefix_store', 'current', ['engine.kv_reuse_lab', 'factory.capped_runner']],
    ['build_image', 'not-reached', bindings],
    ['deliver_to_lab', 'not-reached', []],
    ['measure_engine', 'stopped', []],
    ['release_gate', 'stopped', []],
    ['archive', 'stopped', []],
  ].map(([planId, replayState, boundCCs]) => ({
    id: `step:${planId}`,
    planId,
    replayState,
    boundCCs,
    ccVerifiers: replayState === 'current' ? ccVerifiers : {},
    nodeVerifier: replayState === 'current' ? nodeVerifier : { status: 'not-run', records: [] },
  }));
  const opened = [];
  const openedRecords = [];
  const onOpenNode = (nodeId) => opened.push(nodeId);
  const onOpenRecord = (recordId) => openedRecords.push(recordId);
  const render = (selectedNode, detail) =>
    act(() =>
      root.render(
        createElement(
          I18nextProvider,
          { i18n },
          createElement(
            CapsuleLinksContext.Provider,
            { value: catalog },
            createElement(DemoTaskChain, { nodes, selectedNode, onOpenNode, onOpenRecord }),
            detail && createElement(BoundCapsules, { ids: bindings, results: ccVerifiers }),
            detail && createElement(NodeVerifier, { result: nodeVerifier, onOpenRecord }),
          ),
        ),
      ),
    );
  await render();
  await act(() => resize(980));
  const cards = [...document.querySelectorAll('[data-testid="factory-runs-demo-task-card"]')];
  assert.deepEqual(
    cards.map((node) => node.dataset.variant),
    nodes.map((node) => node.planId),
  );
  assert.deepEqual(
    cards.map((node) => node.dataset.arrow),
    ['right', 'right', 'right', 'down', 'left', 'left', undefined],
  );
  assert.deepEqual(
    cards.map((node) => node.style.gridColumn),
    ['1', '2', '3', '4', '4', '3', '2'],
  );

  const buttons = [...document.querySelectorAll('[data-testid="factory-runs-demo-task-node"]')];
  assert.deepEqual(
    buttons.map((button) => button.dataset.graphState),
    nodes.map((node) => node.replayState),
  );
  assert.equal(buttons[1].getAttribute('aria-current'), 'step');
  assert.equal(cards[0].querySelector('[data-testid="factory-runs-demo-task-node-cc-count"]').textContent, 'no CC');
  assert.equal(cards[1].querySelector('[data-testid="factory-runs-demo-task-node-cc-count"]').textContent, 'CCs: 2');
  const links = [...cards[1].querySelectorAll('a')];
  assert.deepEqual(
    links.map((link) => link.textContent),
    ['Prefix reuse', 'Capped run workbench'],
  );
  assert.deepEqual(
    links.map((link) => link.getAttribute('href')),
    ['#capsules/kv_reuse_lab', '#capsules/factory.capped_runner'],
  );
  links[0].click();
  assert.deepEqual(opened, []);
  assert.deepEqual(
    [...cards[1].querySelectorAll('[data-testid="factory-runs-demo-verifier-status"]')].map((row) => row.textContent),
    ['Pass', 'Not run', 'Fail'],
  );
  const recordLink = cards[1].querySelector('[data-testid="factory-runs-demo-task-node-verifier-link"]');
  assert.equal(recordLink.dataset.variant, record.id);
  recordLink.click();
  assert.deepEqual(openedRecords, [record.id]);
  assert.deepEqual(opened, []);
  assert.equal(cards[4].querySelector('[data-testid="factory-runs-demo-task-node-verifier-link"]'), null);
  assert.equal(cards[4].lastElementChild.dataset.testid, 'factory-runs-demo-node-verifier');
  assert.equal(cards[2].querySelector('[data-testid="factory-runs-demo-task-node-cc-count"]').textContent, 'CCs: 4');
  assert.equal(cards[2].querySelectorAll('a').length, 3);
  assert.equal(cards[2].querySelector('[data-testid="factory-runs-demo-task-node-cc-more"]').textContent, '+1 more');

  buttons[2].click();
  assert.deepEqual(opened, ['build_image']);
  await render('build_image', true);
  assert.equal(buttons[2].getAttribute('aria-expanded'), 'true');
  assert.deepEqual(
    [...document.querySelectorAll('[data-testid="factory-runs-node-bound-cc-link"]')].map(
      (link) => link.dataset.variant,
    ),
    bindings,
  );
  document.querySelector('[data-testid="factory-runs-node-verifier-record-link"]').click();
  assert.deepEqual(openedRecords, [record.id, record.id]);

  await act(() => resize(240));
  assert.deepEqual(
    cards.map((node) => node.style.gridRow),
    ['1', '2', '3', '4', '5', '6', '7'],
  );
  assert.deepEqual(
    cards.map((node) => node.dataset.arrow),
    [...Array(6).fill('down'), undefined],
  );
});
