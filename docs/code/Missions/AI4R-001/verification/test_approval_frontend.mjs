import assert from 'node:assert/strict';
import test from 'node:test';
import { ApprovalController } from './approval_frontend.mjs';

const scope = { session_id: 's1', execution_id: 'e1', thread_id: 'thread1', turn_id: 'turn1', generation: 1 };
const notice = { ...scope, kind: 'tool_approval', tool_name: 'fixture_write', request_id: 'r1', call_id: 'call1', ticket: 'ticket1' };
function pending() {
  const controller = new ApprovalController(scope);
  assert.equal(controller.receive(notice), true);
  return controller;
}

test('approve and decline carry explicit boolean and exact identity', async () => {
  for (const approved of [false, true]) {
    const c = pending();
    assert.equal(c.buttonsEnabled, true);
    assert.equal(await c.decide(approved, async (payload) => {
      assert.equal(c.buttonsEnabled, false);
      assert.deepEqual(payload, { ...scope, request_id: 'r1', call_id: 'call1', ticket: 'ticket1', approved });
      return { accepted: true, ticket: payload.ticket };
    }), true);
    assert.equal(c.state, 'resolved');
    assert.equal(c.buttonsEnabled, false);
  }
});

test('double click dispatches only once', async () => {
  const c = pending();
  let finish;
  let calls = 0;
  const send = () => { calls += 1; return new Promise((resolve) => { finish = resolve; }); };
  const first = c.decide(true, send);
  assert.equal(await c.decide(false, send), false);
  finish({ accepted: true, ticket: 'ticket1' });
  await first;
  assert.equal(calls, 1);
});

test('network ambiguity disables resubmission and preserves unknown state', async () => {
  const c = pending();
  let calls = 0;
  const send = async () => { calls += 1; throw new Error('network'); };
  assert.equal(await c.decide(true, send), false);
  assert.equal(c.state, 'delivery_unknown');
  assert.equal(await c.decide(true, send), false);
  assert.equal(calls, 1);
});

test('late acknowledgment cannot restore a changed session or signed-out state', async () => {
  for (const ready of [false, true]) {
    const c = pending();
    let finish;
    const result = c.decide(true, () => new Promise((resolve) => { finish = resolve; }));
    c.changeContext({ ...scope, session_id: 's2' }, ready);
    finish({ accepted: true, ticket: 'ticket1' });
    assert.equal(await result, false);
    assert.equal(c.state, ready ? 'expired' : 'signed_out');
    assert.equal(c.buttonsEnabled, false);
  }
});

test('wrong-session, missing and malformed notice rejected', () => {
  for (const bad of [{ ...notice, session_id: 's2' }, { ...notice, generation: true },
                     { ...notice, ticket: '' }, { ...notice, tool_name: null }, {}]) {
    const c = new ApprovalController(scope);
    assert.equal(c.receive(bad), false);
    assert.equal(c.buttonsEnabled, false);
  }
});

test('expired response surfaces expiration, not success', async () => {
  const c = pending();
  await c.decide(true, async () => ({ code: 'STALE_OPERATION' }));
  assert.equal(c.state, 'expired');
  assert.equal(c.buttonsEnabled, false);
  assert.equal(c.receive(notice), false);
});

test('mismatched acknowledgment cannot claim completion', async () => {
  const c = pending();
  await c.decide(true, async () => ({ accepted: true, ticket: 'other' }));
  assert.equal(c.state, 'delivery_unknown');
});

test('invalid button decision never sends; pending request cannot be overwritten', async () => {
  const c = pending();
  assert.equal(await c.decide('true', () => assert.fail('must not send')), false);
  assert.equal(c.receive({ ...notice, ticket: 'other', request_id: 'r2' }), false);
  assert.equal(c.notice.ticket, 'ticket1');
});
