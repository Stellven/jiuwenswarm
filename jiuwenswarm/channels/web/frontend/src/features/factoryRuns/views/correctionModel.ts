import type { CorrectionEvent, NodeCorrection } from '../api';

export type CorrectionCursor = { created: number; id?: string };

export function correctionStatusAt(event: CorrectionEvent, verified: ReadonlySet<string>): CorrectionEvent {
  return event.kind === 'finding' && event.status === 'verified_repair' && !verified.has(event.id)
    ? { ...event, status: 'open' }
    : event;
}

export function correctionAt(sequence: NodeCorrection, cursor?: CorrectionCursor): NodeCorrection {
  const ordered = [...sequence.events].sort((left, right) => left.created - right.created);
  if (!cursor) return { ...sequence, events: ordered };
  const position = cursor.id ? ordered.findIndex((event) => event.id === cursor.id) : -1;
  const reached =
    position < 0 ? ordered.filter((event) => event.created <= cursor.created) : ordered.slice(0, position + 1);
  const verified = new Set(
    reached.filter((event) => event.kind === 'passing_check').flatMap((event) => event.finding_ids ?? []),
  );
  const events = reached.map((event) => correctionStatusAt(event, verified));
  return {
    counts: {
      findings: events.filter((event) => event.kind === 'finding').length,
      notes: events.filter((event) => event.kind === 'note').length,
      repairs: events.filter((event) => event.kind === 'repair').length,
    },
    events,
  };
}
