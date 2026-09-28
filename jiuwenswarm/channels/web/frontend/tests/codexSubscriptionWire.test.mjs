import assert from 'node:assert/strict';
import test from 'node:test';
import { build } from 'esbuild';

await build({
  stdin: {
    contents:
      "export { webClient } from './src/services/webClient'; export { useCodexSubscription } from './src/features/codexSubscription/state';",
    resolveDir: process.cwd(),
    loader: 'ts',
  },
  bundle: true,
  platform: 'node',
  format: 'esm',
  outfile: 'node_modules/.cache/codex-subscription/wire.mjs',
  define: {
    'import.meta.env.DEV': 'false',
    'import.meta.env.VITE_API_BASE': 'undefined',
    'import.meta.env.VITE_WS_BASE': 'undefined',
  },
});

globalThis.window = globalThis;
window.location = { protocol: 'http:', host: 'localhost:5173' };
class Socket {
  static OPEN = 1;
  static instance;
  sent = [];
  constructor() {
    Socket.instance = this;
    queueMicrotask(() => {
      this.readyState = 1;
      this.onopen?.();
    });
  }
  send(raw) {
    const request = JSON.parse(raw);
    this.sent.push(request);
    queueMicrotask(() =>
      this.onmessage?.({
        data: JSON.stringify({ type: 'res', id: request.id, ok: true, payload: { accepted: true } }),
      }),
    );
  }
  addEventListener() {}
}
globalThis.WebSocket = Socket;
const { webClient, useCodexSubscription } = await import('../node_modules/.cache/codex-subscription/wire.mjs');
await webClient.connect();

test('signed-out subscription blocks chat before socket send', async () => {
  useCodexSubscription.getState().set({ enabled: true, state: 'signed_out' });
  const count = Socket.instance.sent.length;
  await assert.rejects(webClient.request('chat.send', { session_id: 'a', content: 'Hello' }), {
    code: 'SIGN_IN_REQUIRED',
  });
  assert.equal(Socket.instance.sent.length, count);
});

test('subscription model and cancellation target stay tied to each conversation', async () => {
  useCodexSubscription.getState().set({ enabled: true, state: 'ready', model: 'fixture-model' });
  await webClient.request('chat.send', { session_id: 'a', content: 'Hello' });
  const a = Socket.instance.sent.at(-1);
  await webClient.request('chat.send', { session_id: 'b', content: 'Other' });
  const b = Socket.instance.sent.at(-1);
  assert.equal(a.params.codex_model, 'fixture-model');
  await webClient.request('chat.interrupt', { session_id: 'a', intent: 'cancel' });
  assert.equal(Socket.instance.sent.at(-1).params.target_request_id, a.id);
  assert.notEqual(Socket.instance.sent.at(-1).params.target_request_id, b.id);
});
