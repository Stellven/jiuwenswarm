import { useId, useMemo } from 'react';
import type { CorrectionCounts, CorrectionEvent, NodeCorrection } from '../api';
import { correctionAt, type CorrectionCursor } from './correctionModel';
import { SourceLinks, type EvidenceLinks } from './SourceLinks';
import './correctionSequence.css';

const corrections = [
  ['findings', 'Findings'],
  ['notes', 'Specific-fix notes'],
  ['repairs', 'Repairs'],
] as const;
const labels: Record<CorrectionEvent['kind'], string> = {
  finding: 'Finding',
  note: 'Specific-fix note',
  repair: 'Recorded repair',
  passing_check: 'Passing check',
};

export function CorrectionTally({ counts }: { counts: CorrectionCounts }) {
  return (
    <dl className="factory-correction-tally" data-testid="factory-runs-correction-counts">
      {corrections.map(([kind, label]) => (
        <div key={kind} data-testid="factory-runs-correction-count" data-variant={kind}>
          <dt>{label}</dt>
          <dd>{counts[kind]}</dd>
        </div>
      ))}
    </dl>
  );
}

export function CorrectionRecord({
  event,
  compact = false,
  r8VerifierHelp = false,
  ...links
}: EvidenceLinks & {
  event: CorrectionEvent;
  compact?: boolean;
  r8VerifierHelp?: boolean;
}) {
  const finding = event.kind === 'finding';
  const passing = event.kind === 'passing_check';
  const assisted = r8VerifierHelp && event.kind === 'note' && event.actor === 'operator';
  const attribution = [...new Set([event.actor, event.by, event.reviewer].filter(Boolean))];
  const when = Number.isFinite(event.created) && event.created > 0 ? new Date(event.created * 1000) : undefined;
  const refs = [
    ...new Set(
      [event.check_id, ...(event.evidence_ids ?? []), ...(event.finding_ids ?? []), ...(event.note_ids ?? [])].filter(
        (id): id is string => Boolean(id),
      ),
    ),
  ];
  return (
    <article
      className="factory-correction-record"
      data-testid="factory-runs-correction-record"
      data-variant={event.id}
      data-kind={event.kind}
      data-status={finding ? event.status : undefined}
    >
      <header className="factory-correction-header">
        <strong>{assisted ? 'Agent help with the verifier role' : labels[event.kind]}</strong>
        {event.advisory !== undefined && (finding || event.reviewer_verdict) && (
          <span className="factory-correction-badge" data-testid="factory-runs-correction-policy">
            {event.advisory ? 'Advisory' : 'Blocking'}
            {passing ? ' review' : ''}
          </span>
        )}
        {finding && event.severity && <span className="factory-correction-badge">{event.severity}</span>}
        {finding && event.status && (
          <span className="factory-correction-badge" data-testid="factory-runs-correction-finding-status">
            {event.status === 'verified_repair' ? 'Later repair verified' : 'Unresolved'}
          </span>
        )}
        {!compact && when && <time dateTime={when.toISOString()}>{when.toLocaleString()}</time>}
      </header>
      <p
        className="factory-correction-text"
        data-testid={passing ? 'factory-runs-correction-passing-check' : 'factory-runs-correction-text'}
        data-host-passed={passing ? event.host_passed : undefined}
        data-verifier-passed={passing ? event.verifier_passed : undefined}
      >
        {event.text}
      </p>
      {(attribution.length > 0 || event.output || event.file || event.verdict) && (
        <p className="factory-correction-meta" data-testid="factory-runs-correction-attribution">
          {[
            attribution.join(' · '),
            event.output,
            event.file && (event.line ? `${event.file}:${event.line}` : event.file),
            event.verdict,
          ]
            .filter(Boolean)
            .join(' · ')}
        </p>
      )}
      <SourceLinks {...links} source={event.source} ids={refs} />
    </article>
  );
}

export function CorrectionSequence({
  corrections: sequence,
  cursor,
  r8VerifierHelp,
  ...links
}: EvidenceLinks & {
  corrections: NodeCorrection;
  cursor?: CorrectionCursor;
  r8VerifierHelp?: boolean;
}) {
  const heading = useId();
  const view = useMemo(() => correctionAt(sequence, cursor), [sequence, cursor]);
  if (!view.events.length) return null;
  return (
    <section
      className="factory-correction-sequence"
      aria-labelledby={heading}
      data-testid="factory-runs-correction-sequence"
    >
      <header>
        <h4 id={heading}>Findings, notes and repairs</h4>
        <CorrectionTally counts={view.counts} />
      </header>
      <ol>
        {view.events.map((event) => (
          <li key={event.id} data-kind={event.kind}>
            <CorrectionRecord event={event} r8VerifierHelp={r8VerifierHelp} {...links} />
          </li>
        ))}
      </ol>
    </section>
  );
}
