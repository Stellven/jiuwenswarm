import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

const memory = new Map();
globalThis.window = {
  location: { origin: 'http://private:5173', hash: '#research_bootstrap=one-use', pathname: '/', search: '' },
  sessionStorage: {
    getItem: (k) => memory.get(k) ?? null,
    setItem: (k, v) => memory.set(k, v),
    removeItem: (k) => memory.delete(k),
  },
  history: {
    replaceState: () => {
      window.location.hash = '';
    },
  },
};
const calls = [];
globalThis.fetch = async (path, options = {}) => {
  calls.push({ path, options });
  return {
    ok: true,
    status: 200,
    json: async () =>
      path.includes('bootstrap')
        ? {
            token: 'opaque-session',
            defaults: {
              account_id: 'owner',
              workspace_id: 'work',
              configuration_ref: { id: 'config', sha256: 'a'.repeat(64) },
            },
          }
        : { run_id: 'run:1', status: 'in_progress' },
  };
};
const client = await import('../node_modules/.cache/research-shell/utils/researchClient.js');

test('input capability is separate from execution configuration and supports older servers', () => {
  const key = 'ai4r.native-session';
  const original = memory.get(key);
  const saved = {
    token: 'local',
    defaults: { account_id: 'owner', workspace_id: 'local', configuration_ref: null, inputs_ready: true },
  };
  memory.set(key, JSON.stringify(saved));
  assert.equal(client.hasResearchInputs(), true);
  assert.equal(client.hasResearchConfiguration(), false);
  saved.defaults.inputs_ready = false;
  assert.equal(client.hasResearchInputs(), true);
  memory.set(key, JSON.stringify(saved));
  assert.equal(client.hasResearchInputs(), false);
  delete saved.defaults.inputs_ready;
  saved.defaults.configuration_ref = { id: 'config', sha256: 'a'.repeat(64) };
  memory.set(key, JSON.stringify(saved));
  assert.equal(client.hasResearchInputs(), true);
  if (original === undefined) memory.delete(key);
  else memory.set(key, original);
});

test('native bootstrap scrubs fragment and Bearer stays at same origin', async () => {
  await client.bootstrapResearchSession();
  assert.equal(window.location.hash, '');
  await client.researchRequest('/api/v1/readiness');
  assert.equal(new Headers(calls.at(-1).options.headers).get('authorization'), 'Bearer opaque-session');
  await assert.rejects(client.researchRequest('http://foreign.invalid/api/v1/runs'));
});

test('idempotent submission uses server defaults and exact source fields', async () => {
  await client.submitResearchIntake({ id: 'intake', sha256: 'b'.repeat(64) }, 'request:1');
  const sent = JSON.parse(calls.at(-1).options.body);
  assert.equal(sent.account_id, 'owner');
  assert.equal(sent.workspace_id, 'work');
  assert.equal(sent.client_request_id, 'request:1');
  assert.equal(sent.interaction_mode, 'interactive');
  assert.ok(!('prompt' in sent));
});

test('upload selection and local run handles remain conversation scoped', async () => {
  client.selectResearchInputs('session:1', ['upload:1', 'upload:1']);
  assert.deepEqual(client.selectedResearchInputs('session:1'), ['upload:1']);
  assert.deepEqual(client.selectedResearchInputs('session:2'), []);
  client.markResearchUpload('session:1', true);
  assert.throws(() => client.selectedResearchInputs('session:1'));
  client.markResearchUpload('session:1', false);
  client.rememberResearchRun('session:1', 'run:1');
  assert.deepEqual(client.researchRunHandles('session:1'), ['run:1']);
  assert.deepEqual(client.researchRunHandles('session:2'), []);
  await assert.rejects(client.researchRequest('/api/v1/../../foreign'));
});

test('research controls keep complete English and Chinese resources', async () => {
  const en = JSON.parse(await readFile(new URL('../src/i18n/locales/en.json', import.meta.url), 'utf8'));
  const zh = JSON.parse(await readFile(new URL('../src/i18n/locales/zh.json', import.meta.url), 'utf8'));
  const flatten = (value, prefix = '') =>
    Object.entries(value).flatMap(([key, child]) =>
      typeof child === 'string' ? [[prefix + key, child]] : flatten(child, prefix + key + '.'),
    );
  for (const section of ['researchShell', 'researchPreferences', 'researchInputs']) {
    const source = flatten(en[section]);
    const translated = flatten(zh[section]);
    assert.deepEqual(
      translated.map(([key]) => key),
      source.map(([key]) => key),
    );
    for (const [, value] of translated) assert.match(value, /[\u4e00-\u9fff]/);
    assert.ok(!translated.some(([, value]) => value.includes('???') || value.includes('\ufffd')));
  }
});

test('authenticated inspection survives unavailable operator configuration without submit effects', async () => {
  const originalFetch = globalThis.fetch;
  const originalMemory = new Map(memory);
  memory.clear();
  window.location.hash = '#research_bootstrap=inspection-only';
  const observed = [];
  globalThis.fetch = async (path, options = {}) => {
    observed.push({ path, options });
    return {
      ok: true,
      status: 200,
      json: async () =>
        path.includes('bootstrap')
          ? {
              token: 'inspection-session',
              defaults: { account_id: 'owner', workspace_id: 'work', configuration_ref: null, plan_source: null },
            }
          : { ready: false, reasons: ['operator configuration unavailable'] },
    };
  };
  try {
    assert.equal(await client.bootstrapResearchSession(), true);
    assert.equal(window.location.hash, '');
    assert.equal(client.hasResearchSession(), true);
    await client.researchRequest('/api/v1/readiness');
    assert.equal(new Headers(observed.at(-1).options.headers).get('authorization'), 'Bearer inspection-session');
    const before = observed.length;
    await assert.rejects(
      client.submitResearchIntake({ id: 'intake', sha256: 'b'.repeat(64) }, 'request:blocked'),
      /configuration/,
    );
    assert.equal(observed.length, before);
  } finally {
    globalThis.fetch = originalFetch;
    memory.clear();
    for (const [k, v] of originalMemory) memory.set(k, v);
  }
});

test('failed bootstrap scrubs its one-use fragment and starts no authenticated operation', async () => {
  const originalFetch = globalThis.fetch;
  const originalMemory = new Map(memory);
  memory.clear();
  window.location.hash = '#research_bootstrap=failed-one-use';
  let requests = 0;
  globalThis.fetch = async () => {
    requests++;
    return { ok: false, status: 503 };
  };
  try {
    await assert.rejects(client.bootstrapResearchSession(), /authentication/);
    assert.equal(window.location.hash, '');
    assert.equal(client.hasResearchSession(), false);
    assert.equal(await client.bootstrapResearchSession(), false);
    assert.equal(requests, 1);
  } finally {
    globalThis.fetch = originalFetch;
    memory.clear();
    for (const [k, v] of originalMemory) memory.set(k, v);
  }
});

test('concurrent connection waits for the same scrubbed bootstrap request', async () => {
  const originalFetch = globalThis.fetch;
  const originalMemory = new Map(memory);
  memory.clear();
  window.location.hash = '#research_bootstrap=concurrent-one-use';
  let finish;
  let requests = 0;
  globalThis.fetch = () => {
    requests++;
    return new Promise((resolve) => {
      finish = resolve;
    });
  };
  try {
    const first = client.bootstrapResearchSession();
    const second = client.bootstrapResearchSession();
    assert.equal(requests, 1);
    assert.equal(window.location.hash, '');
    finish({
      ok: true,
      status: 200,
      json: async () => ({
        token: 'one-shared-session',
        defaults: { account_id: 'owner', workspace_id: null, configuration_ref: null },
      }),
    });
    assert.deepEqual(await Promise.all([first, second]), [true, true]);
    assert.equal(client.hasResearchSession(), true);
    assert.throws(() => client.researchWorkspace());
  } finally {
    if (finish) finish({ ok: false, status: 503 });
    globalThis.fetch = originalFetch;
    memory.clear();
    for (const [k, v] of originalMemory) memory.set(k, v);
  }
});

test('reusable local login renews the browser grant without a URL fragment', async () => {
  const originalFetch = globalThis.fetch;
  const originalMemory = new Map(memory);
  let attempts = 0;
  memory.clear();
  window.location.hash = '#research_bootstrap=reusable-local-fixture';
  globalThis.fetch = async (path, options) => {
    attempts++;
    assert.equal(path, '/auth/research/bootstrap');
    assert.equal(JSON.parse(options.body).challenge, 'reusable-local-fixture');
    return {
      ok: true,
      json: async () => ({
        token: 'renewed-' + attempts,
        reusable_bootstrap: true,
        defaults: { account_id: 'owner', workspace_id: 'work', configuration_ref: null },
      }),
    };
  };
  try {
    assert.equal(await client.bootstrapResearchSession(), true);
    assert.equal(window.location.hash, '');
    assert.equal(await client.bootstrapResearchSession(), true);
    assert.equal(attempts, 2);
    assert.equal(client.hasResearchConfiguration(), false);
  } finally {
    globalThis.fetch = originalFetch;
    memory.clear();
    for (const [key, value] of originalMemory) memory.set(key, value);
  }
});
