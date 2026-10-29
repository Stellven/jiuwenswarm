import assert from 'node:assert/strict';
import test, { afterEach } from 'node:test';

const memory = new Map();
const nativeSession = () => ({
  token: 'unit-native-session-only',
  defaults: {
    account_id: 'unit-owner',
    workspace_id: null,
    configuration_ref: null,
  },
});
globalThis.window = globalThis;
window.location = {
  origin: 'http://private:5173',
  protocol: 'http:',
  host: 'private:5173',
  hash: '',
  pathname: '/',
  search: '',
};
window.sessionStorage = {
  getItem: (k) => memory.get(k) ?? null,
  setItem: (k, v) => memory.set(k, v),
  removeItem: (k) => memory.delete(k),
};
window.history = {
  replaceState() {
    window.location.hash = '';
  },
};
let fetchCount = 0;
let bootstrapResponse = null;
globalThis.fetch = async () => {
  fetchCount += 1;
  return bootstrapResponse ?? { ok: true, json: async () => nativeSession() };
};

class FakeWebSocket {
  static OPEN = 1;
  static all = [];
  constructor(url) {
    this.url = url;
    this.readyState = 0;
    this.listeners = new Map();
    FakeWebSocket.all.push(this);
  }
  open() {
    this.readyState = 1;
    this.onopen?.();
  }
  addEventListener(name, handler) {
    const list = this.listeners.get(name) ?? [];
    list.push(handler);
    this.listeners.set(name, list);
  }
  send(raw) {
    this.lastRequest = JSON.parse(raw);
  }
  receive(value) {
    this.onmessage?.({ data: JSON.stringify(value) });
  }
  close(code = 1000, reason = '') {
    this.readyState = 3;
    const event = { code, reason, wasClean: code === 1000 };
    this.onclose?.(event);
    for (const handler of this.listeners.get('close') ?? []) handler(event);
  }
}
globalThis.WebSocket = FakeWebSocket;
const { webClient } = await import('../node_modules/.cache/web-client-runtime-ack/webClient.mjs');
const tick = async () => {
  for (let i = 0; i < 8; i += 1) await Promise.resolve();
};

async function ready() {
  const connected = webClient.connect();
  await tick();
  const socket = FakeWebSocket.all.at(-1);
  socket.open();
  await connected;
  return socket;
}

afterEach(async () => {
  await webClient.disconnect();
  for (const socket of FakeWebSocket.all) if (socket.readyState !== 3) socket.close();
  FakeWebSocket.all = [];
  memory.clear();
  window.location.hash = '';
  fetchCount = 0;
  bootstrapResponse = null;
});

test('concurrent restored-session startup owns one socket throughout bootstrap await', async () => {
  memory.set('ai4r.native-session', JSON.stringify(nativeSession()));
  const callers = Array.from({ length: 8 }, () => webClient.connect());
  await tick();
  for (const socket of FakeWebSocket.all) socket.open();
  await Promise.all(callers);
  assert.equal(FakeWebSocket.all.length, 1);
  assert.equal(FakeWebSocket.all[0].url, 'ws://private:5173/ws');
  assert.equal(fetchCount, 0, 'reload must reuse the existing session without replaying one-use bootstrap');
});

test('concurrent first bootstrap shares one bootstrap and one socket', async () => {
  window.location.hash = '#research_bootstrap=unit-one-use';
  let release;
  bootstrapResponse = new Promise((resolve) => {
    release = resolve;
  });
  const callers = [webClient.connect(), webClient.connect(), webClient.connect()];
  await tick();
  assert.equal(FakeWebSocket.all.length, 0);
  release({ ok: true, json: async () => nativeSession() });
  await tick();
  for (const socket of FakeWebSocket.all) socket.open();
  await Promise.all(callers);
  assert.equal(fetchCount, 1);
  assert.equal(FakeWebSocket.all.length, 1);
});

test('late close and error from replaced socket cannot clear the live connection', async () => {
  const previous = await ready();
  await webClient.disconnect();
  const current = await ready();
  previous.onclose?.({ code: 1006, reason: 'late prior callback', wasClean: false });
  previous.onerror?.();
  assert.equal(webClient.getState(), 'ready');
  const stillReady = webClient.connect();
  await tick();
  assert.equal(FakeWebSocket.all.at(-1), current);
  await stillReady;
});

test('replaced socket cannot settle a request owned by the current socket', async () => {
  const previous = await ready();
  await webClient.disconnect();
  const current = await ready();
  let settled = false;
  const pending = webClient.request('research.preferences.get').finally(() => {
    settled = true;
  });
  await tick();
  const id = current.lastRequest.id;
  try {
    previous.receive({ type: 'res', id, ok: true, payload: { source: 'stale' } });
    await tick();
    assert.equal(settled, false);
  } finally {
    current.receive({ type: 'res', id, ok: true, payload: { source: 'current' } });
  }
  assert.deepEqual(await pending, { source: 'current' });
});

test('disconnect during bootstrap prevents a late unowned socket', async () => {
  window.location.hash = '#research_bootstrap=unit-cancel';
  let release;
  bootstrapResponse = new Promise((resolve) => {
    release = resolve;
  });
  const pending = webClient.connect();
  const rejected = assert.rejects(pending, (error) => error.code === 'WS_CLOSED');
  await tick();
  await webClient.disconnect();
  release({ ok: true, json: async () => nativeSession() });
  await tick();
  for (const socket of FakeWebSocket.all) socket.open();
  await rejected;
  assert.equal(FakeWebSocket.all.length, 0);
  assert.equal(webClient.getState(), 'closed');
});

test('failed bootstrap releases single-flight state for an explicit later connection', async () => {
  window.location.hash = '#research_bootstrap=unit-failed';
  bootstrapResponse = { ok: false };
  await assert.rejects(Promise.all([webClient.connect(), webClient.connect()]), /authentication/);
  assert.equal(FakeWebSocket.all.length, 0);
  bootstrapResponse = null;
  await ready();
  assert.equal(FakeWebSocket.all.length, 1);
});

test('explicit reconnect preserves durable native session and current preference request', async () => {
  memory.set('ai4r.native-session', JSON.stringify(nativeSession()));
  const previous = await ready();
  const connecting = webClient.reconnect('unit reload/reconnect');
  await tick();
  const current = FakeWebSocket.all.at(-1);
  current.open();
  await connecting;
  previous.onopen?.();
  previous.onclose?.({ code: 1006, reason: 'late', wasClean: false });
  assert.equal(webClient.getState(), 'ready');
  const request = webClient.request('research.preferences.get');
  await tick();
  current.receive({ type: 'res', id: current.lastRequest.id, ok: true, payload: { applies_on: 'next_start' } });
  assert.deepEqual(await request, { applies_on: 'next_start' });
  assert.equal(fetchCount, 0);
});

test('temporary reusable-bootstrap outage keeps retrying until the server returns', async () => {
  const originalSetTimeout = window.setTimeout;
  const originalClearTimeout = window.clearTimeout;
  let retry;
  window.setTimeout = (callback) => {
    retry = callback;
    return 1;
  };
  window.clearTimeout = () => {};
  memory.set('ai4r.local-bootstrap', 'unit-reusable');
  bootstrapResponse = { ok: false, status: 503 };
  try {
    await assert.rejects(webClient.connect(), /authentication/);
    assert.equal(webClient.getState(), 'reconnecting');
    assert.equal(typeof retry, 'function');
    assert.equal(memory.get('ai4r.local-bootstrap'), 'unit-reusable');
    bootstrapResponse = null;
    retry();
    await tick();
    const current = FakeWebSocket.all.at(-1);
    assert.ok(current);
    current.open();
    await tick();
    assert.equal(webClient.getState(), 'ready');
  } finally {
    window.setTimeout = originalSetTimeout;
    window.clearTimeout = originalClearTimeout;
  }
});
