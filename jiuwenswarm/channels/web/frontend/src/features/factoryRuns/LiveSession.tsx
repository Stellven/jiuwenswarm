import type { SessionSnapshot } from './api';
import { useSessionCopy } from './sessionLocale';
import { sessionElapsed, sessionStatus } from './sessionPresentation';
import './factorySession.css';

export function LiveSession({ session, stale, engineViewer }: {
  session?: SessionSnapshot | null;
  stale?: boolean;
  engineViewer?: boolean;
}) {
  const copy = useSessionCopy();
  const status = sessionStatus(session, stale);
  const step = engineViewer && session?.step?.kind === 'tool' ? null : session?.step;
  const message = session?.latest_message;
  const elapsed = sessionElapsed(session?.elapsed_s);

  return (
    <section className="factory-session" aria-label={copy.session} data-testid="factory-runs-session">
      <div className="factory-session-header">
        <h3 data-testid="factory-runs-session-title">{copy.session}</h3>
        <span
          className="factory-session-status"
          data-testid="factory-runs-session-status"
          data-variant={status}
          role="status"
        >
          {copy[status]}
        </span>
      </div>
      <dl className="factory-session-details">
        <div data-testid="factory-runs-session-step">
          <dt>{stale && step ? copy.lastStep : copy.step}</dt>
          <dd>{step ? `${copy[step.kind === 'turn' ? 'agentTurn' : step.kind]} · ${step.label}` : copy.noStep}</dd>
        </div>
        <div data-testid="factory-runs-session-elapsed">
          <dt>{copy.elapsed}</dt>
          <dd className="factory-session-time">{elapsed ?? '—'}</dd>
        </div>
      </dl>
      {!engineViewer && <div
        className="factory-session-message"
        data-testid="factory-runs-session-message"
        data-variant={message ? 'recorded' : 'empty'}
      >
        <h4>{copy.lastMessage}</h4>
        {message ? <blockquote>{message.text}</blockquote> : <p>{copy.noMessage}</p>}
      </div>}
    </section>
  );
}
