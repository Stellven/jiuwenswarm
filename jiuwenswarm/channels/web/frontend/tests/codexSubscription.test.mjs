import test from 'node:test';
import assert from 'node:assert/strict';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { JSDOM } from 'jsdom';
import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';
const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost/' });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, IS_REACT_ACT_ENVIRONMENT: true });
await i18next.use(initReactI18next).init({ lng: 'en', resources: { en: { translation: {} } } });
const { CodexSubscriptionPanel } = await import('../node_modules/.cache/codex-subscription/CodexSubscriptionPanel.mjs');
const root = createRoot(document.getElementById('root'));
const find = (id) => document.querySelector(`[data-testid="codex-subscription-${id}"]`);
const tick = () =>
  act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });

test('signed-out UI offers login without key inputs and prevents duplicate submission', async () => {
  let finish;
  let calls = 0;
  const request = async (method) => {
    if (method === 'codex.auth.status') return { enabled: true, state: 'signed_out' };
    calls++;
    return new Promise((resolve) => {
      finish = resolve;
    });
  };
  await act(async () => root.render(React.createElement(CodexSubscriptionPanel, { connected: true, request })));
  await tick();
  assert.equal(document.querySelectorAll('input').length, 0);
  await act(async () => find('login').click());
  assert.equal(find('login').disabled, true);
  find('login').click();
  assert.equal(calls, 1);
  await act(async () => finish({ state: 'signing_in', auth_url: 'https://auth.openai.com/authorize?fixture=1' }));
  assert.match(find('login-link').href, /^https:\/\/auth.openai.com/);
  assert.ok(find('cancel'));
});

test('late login response after disconnect cannot restore sign-in link', async () => {
  await act(async () => root.render(null));
  let finish;
  const request = async (method) =>
    method === 'codex.auth.status'
      ? { enabled: true, state: 'signed_out' }
      : new Promise((r) => {
          finish = r;
        });
  await act(async () => root.render(React.createElement(CodexSubscriptionPanel, { connected: true, request })));
  await tick();
  await act(async () => find('login').click());
  await act(async () => root.render(React.createElement(CodexSubscriptionPanel, { connected: false, request })));
  await act(async () => finish({ auth_url: 'https://auth.openai.com/authorize?fixture=2' }));
  assert.equal(find('login-link'), null);
  assert.equal(find('login').disabled, true);
});

test('runtime failure remains visible with retry and no key fallback', async () => {
  await act(async () => root.render(null));
  const request = async () => {
    throw new Error('RUNTIME_UNAVAILABLE');
  };
  await act(async () => root.render(React.createElement(CodexSubscriptionPanel, { connected: true, request })));
  await tick();
  assert.ok(find('error'));
  assert.ok(find('refresh'));
  assert.equal(document.querySelectorAll('input').length, 0);
  await act(async () => root.unmount());
});
