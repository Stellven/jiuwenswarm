import test from 'node:test';
import assert from 'node:assert/strict';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { JSDOM } from 'jsdom';

const dom = new JSDOM('<div id="root"></div>', { url: 'http://127.0.0.1:5173' });
Object.assign(globalThis, {
  window: dom.window,
  document: dom.window.document,
  localStorage: dom.window.localStorage,
  IS_REACT_ACT_ENVIRONMENT: true,
});
const { useIntentCompilation } = await import('../dist/intent-test/useIntentCompilation.mjs');
const root = createRoot(document.getElementById('root'));
let observed;
function Host() {
  observed = useIntentCompilation(true);
  return null;
}
const tick = () =>
  act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 5));
  });
const terminal = (runId, state = 'ACCEPTED') => ({
  run_id: runId,
  state,
  verdict: state === 'ACCEPTED' ? 'PASS' : 'FAIL',
  reasons: [],
  warnings: [],
  accepted_intent: null,
  accepted_reference: state === 'ACCEPTED' ? {} : null,
  evidence: { artifacts: [] },
  durable: true,
});

test('exact original text, protected browser request, inspection and linked correction', async () => {
  const calls = [];
  let next = 'first';
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true,
      json: async () =>
        options.method === 'POST'
          ? { run_id: next, state: 'CAPTURED' }
          : terminal(next, next === 'first' ? 'HALTED' : 'ACCEPTED'),
    };
  };
  await act(async () => root.render(React.createElement(Host)));
  const original = '  Compare A and B.\nNever use network.  ';
  await act(async () => observed.submit(original));
  await tick();
  const first = calls.find((call) => call.options.method === 'POST');
  assert.equal(JSON.parse(first.options.body).text, original);
  assert.equal(first.options.credentials, 'include');
  assert.equal(first.options.headers['X-Jiuwen-Intent'], '1');
  assert.equal(observed.run.state, 'HALTED');
  await act(async () => observed.prepareCorrection());
  next = 'second';
  await act(async () => observed.submit(original));
  await tick();
  assert.equal(
    JSON.parse(calls.filter((call) => call.options.method === 'POST')[1].options.body).corrects_run_id,
    'first',
  );
  assert.equal(observed.run.state, 'ACCEPTED');
  assert.equal(localStorage.getItem('ai4r.intent.lastRun'), 'second');
  await act(async () => root.render(null));
});

test('reload inspects same run and never resubmits model work', async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push(options.method);
    return { ok: true, json: async () => terminal('second') };
  };
  await act(async () => root.render(React.createElement(Host)));
  await tick();
  assert.equal(observed.run.run_id, 'second');
  assert.deepEqual(calls, ['GET']);
  await act(async () => root.render(null));
});

test('submission error remains visible and never retries submission', async () => {
  localStorage.clear();
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    return { ok: false, json: async () => ({ code: 'INTENT_UNAUTHORIZED' }) };
  };
  await act(async () => root.render(React.createElement(Host)));
  await act(async () => observed.submit('Research objective'));
  await tick();
  assert.equal(calls, 1);
  assert.equal(observed.error, 'INTENT_UNAUTHORIZED');
  assert.equal(observed.busy, false);
  await act(async () => root.render(null));
});
