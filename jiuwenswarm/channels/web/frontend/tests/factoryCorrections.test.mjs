import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { correctionAt } from '../src/features/factoryRuns/views/correctionModel.ts';
import { collapseEvents } from '../src/features/factoryRuns/views/storyModel.ts';

const record = (id, kind, created, extra = {}) => ({
  id,
  kind,
  created,
  source: `source-${id}`,
  text: `Recorded ${id}`,
  node_id: 'requant_2bit',
  ...extra,
});
const first = record('finding-provenance', 'finding', 1, {
  advisory: true,
  actor: 'reviewer',
  status: 'verified_repair',
  severity: 'major',
  verdict: 'needs_revision',
  text: 'The producer and hash convention need a provenance explanation.',
});
const pending = record('finding-smoke', 'finding', 1, {
  advisory: true,
  actor: 'reviewer',
  status: 'open',
  text: 'A real smoke response is still missing.',
});
const note = record('note', 'note', 2, { by: 'review coordinator', finding_ids: [first.id] });
const repair = record('repair', 'repair', 3, { finding_ids: [first.id], note_ids: [note.id] });
const pass = record('pass', 'passing_check', 3, {
  finding_ids: [first.id],
  host_passed: true,
  verifier_passed: true,
  advisory: true,
  reviewer_verdict: 'needs_revision',
});
const sequence = { counts: { findings: 2, notes: 1, repairs: 1 }, events: [first, pending, repair, pass, note] };

test('the correction model orders actual stages and preserves unresolved advisory findings', () => {
  const current = correctionAt(sequence);
  assert.deepEqual(
    current.events.map(({ id }) => id),
    [first.id, pending.id, note.id, repair.id, pass.id],
  );
  assert.deepEqual(current.counts, { findings: 2, notes: 1, repairs: 1 });
  assert.equal(current.events[0], first);
  assert.equal(current.events[1], pending);
  assert.equal(current.events[4].host_passed, true);
  assert.equal(current.events[4].verifier_passed, true);
  assert.equal(current.events[4].reviewer_verdict, 'needs_revision');
});

test('a replay stage shows findings and notes only when their recorded events have occurred', () => {
  const initial = correctionAt(sequence, { id: first.id, created: first.created });
  assert.deepEqual(initial.counts, { findings: 1, notes: 0, repairs: 0 });
  assert.deepEqual(initial.events, [{ ...first, status: 'open' }]);
  const atRepair = correctionAt(sequence, { id: repair.id, created: repair.created });
  assert.equal(atRepair.events[0].status, 'open');
  assert.equal(atRepair.counts.repairs, 1);
  assert.ok(atRepair.events.every((event) => event.kind !== 'passing_check'));
  const afterPass = correctionAt(sequence, { id: pass.id, created: pass.created });
  assert.equal(afterPass.events[0].status, 'verified_repair');
  assert.equal(afterPass.events[1].status, 'open');
});

test('separate correction records stay separate even when their story summaries match', () => {
  const story = (correction, index) => ({
    correction,
    id: correction.id,
    cursor: index + 1,
    kind: 'finding',
    created: correction.created,
    summary: 'Reviewer finding',
  });
  assert.equal(collapseEvents([story(first, 0), story(pending, 1)]).length, 2);
});

test('a replay tally counts a repeated finding once and preserves both reports', () => {
  const report = { ...first, finding_key: 'missing-source-pin' };
  const repeated = { ...report, id: 'repeated-finding', created: 4, source: 'later-check' };
  const history = { counts: { findings: 1, notes: 0, repairs: 0 }, events: [report, repeated] };
  const view = correctionAt(history, { id: repeated.id, created: repeated.created });
  assert.equal(view.counts.findings, 1);
  assert.equal(view.events.length, 2);
});

const recordedPath = process.env.FACTORY_CORRECTIONS_SAMPLE;
if (recordedPath) {
  test('real R8 correction payload keeps its review findings and independently cited check', () => {
    const sample = JSON.parse(readFileSync(recordedPath, 'utf8'));
    const history = correctionAt(sample.corrections);
    assert.ok(history.counts.findings > 0);
    assert.ok(history.events.some((event) => event.kind === 'finding' && event.advisory && event.text && event.source));
    assert.ok(history.events.every((event) => event.source && event.text));
    const distinct = new Set(history.events.filter(({ kind }) => kind === 'finding').map(({ id, finding_key }) => finding_key ?? id));
    assert.equal(history.counts.findings, distinct.size);
  });
}
