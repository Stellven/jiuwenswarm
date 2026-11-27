import { useEffect, useId, useRef, useState } from 'react';
import { CircleAlert, CircleDot, GitBranch, Hourglass, Pause, Square } from 'lucide-react';
import type { RunOperation, RunOperationResult, RunState as RunStateRecord } from '../api';
import { StructuredData } from '../cc/CapsuleMaterial';
import { ReplayLabel } from './NodeEvidence';

const stateLabels: Record<string, string> = {
  running: 'Running',
  waiting: 'Waiting on a job',
  waiting_on_job: 'Waiting on a job',
  paused: 'Paused',
  halted: 'Halted',
  step: 'Step checkpoint',
  checkpoint: 'Step checkpoint',
  step_checkpoint: 'Step checkpoint',
  finished: 'Finished',
  completed: 'Completed',
  idle: 'Idle',
  ready: 'Ready',
  partial: 'Partial',
  failed: 'Failed',
  stopped: 'Stopped',
};

type ResumeMode = 'clear_pause' | 'start_controller' | null;

const actionLabels: Record<RunOperation, string> = {
  pause: 'Pause',
  resume: 'Resume',
  'revise-preview': 'Preview revision',
  'revise-apply': 'Apply revision',
};

const actionDetails: Record<RunOperation, string> = {
  pause: 'Request a pause at the next checkpoint. The running job may finish first.',
  resume: 'Clear the operator pause so the run can continue.',
  'revise-preview': 'Show the graph changes the revision would make.',
  'revise-apply':
    'Apply the revision to this run’s task graph. The controller will use the revised graph when it resumes.',
};

function formatElapsed(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor(total / 60) % 60;
  return [hours ? `${hours} h` : '', minutes ? `${minutes} min` : '', `${total % 60} s`].filter(Boolean).join(' ');
}

function timestamp(value: number | string | undefined) {
  return typeof value === 'number' ? value * 1000 : typeof value === 'string' ? Date.parse(value) : NaN;
}

function RunStateBanner({ status, live }: { status: RunStateRecord; live: boolean }) {
  const [now, setNow] = useState(Date.now);
  const waiting = status.state.startsWith('waiting');
  useEffect(() => {
    if (!waiting || !live) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [waiting, live]);
  const marker = status.source ? status.markers?.[status.source] : undefined;
  const since = timestamp(status.since ?? marker?.mtime);
  const jobSince = timestamp(status.job?.since ?? status.since);
  const elapsed = live && Number.isFinite(jobSince) ? (now - jobSince) / 1000 : status.job?.elapsed_seconds;
  const stopped = status.state === 'stopped';
  const outcomeLabel =
    status.outcome === 'stop_missing_prerequisite'
      ? 'Missing prerequisite'
      : status.outcome?.replace(/^stop_/, '').replaceAll('_', ' ');
  const Icon = waiting
    ? Hourglass
    : status.state === 'paused'
      ? Pause
      : status.state === 'halted' || stopped
        ? Square
        : status.state.includes('step') || status.state === 'checkpoint'
          ? GitBranch
          : CircleDot;
  return (
    <div className="factory-run-state-description">
      <div className="factory-node-evidence-heading">
        <Icon size={18} aria-hidden="true" />
        <strong data-testid="factory-runs-state-label">
          {stateLabels[status.state] ?? status.state.replaceAll('_', ' ')}
        </strong>
        {stopped && outcomeLabel && (
          <span className="factory-node-evidence-kind" data-testid="factory-runs-state-outcome">
            {outcomeLabel}
          </span>
        )}
        {status.node_id && <code data-testid="factory-runs-state-node">{status.node_id}</code>}
        <ReplayLabel value={status.job?.replayed_from} />
      </div>
      {status.job && (
        <p data-testid="factory-runs-state-job">
          {status.job.effect && <strong>{status.job.effect} </strong>}
          {status.job.attempt_id && <code>{status.job.attempt_id}</code>}
          {typeof elapsed === 'number' && <> · {formatElapsed(elapsed)}</>}
        </p>
      )}
      {(status.reason || marker?.text) && (
        <p data-testid="factory-runs-state-reason">{status.reason || marker?.text}</p>
      )}
      {status.source && (
        <code className="factory-muted" data-testid="factory-runs-state-source">
          {status.source}
        </code>
      )}
      {(status.by || Number.isFinite(since)) && (
        <p className="factory-muted" data-testid="factory-runs-state-actor">
          {status.by && <span>{status.by}</span>}
          {status.by && Number.isFinite(since) && ' · '}
          {Number.isFinite(since) && (
            <time dateTime={new Date(since).toISOString()}>{new Date(since).toLocaleString()}</time>
          )}
        </p>
      )}
      {!!Object.keys(status.markers ?? {}).length && (
        <details className="factory-node-evidence-disclosure" data-testid="factory-runs-state-markers">
          <summary data-testid="factory-runs-state-markers-toggle">Run markers</summary>
          {Object.entries(status.markers ?? {}).map(([name, marker]) => (
            <section key={name} data-testid="factory-runs-state-marker" data-variant={name}>
              <h5>{name}</h5>
              <pre>{marker.text}</pre>
            </section>
          ))}
        </details>
      )}
    </div>
  );
}

function RunConfirmation({
  action,
  resumeMode,
  run,
  onClose,
  onComplete,
}: {
  action: RunOperation;
  resumeMode?: ResumeMode;
  run: (action: RunOperation, reason: string) => Promise<RunOperationResult>;
  onClose: () => void;
  onComplete: (action: RunOperation, result: RunOperationResult) => void;
}) {
  const title = useId();
  const details = useId();
  const dialog = useRef<HTMLDialogElement>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  return (
    <dialog
      ref={dialog}
      className="factory-run-confirmation cc-dialog"
      aria-labelledby={title}
      aria-describedby={details}
      data-testid="factory-runs-operation-confirmation"
      data-variant={action}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          if (!reason.trim() || busy) return;
          setBusy(true);
          setError('');
          try {
            onComplete(action, await run(action, reason.trim()));
          } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
            setBusy(false);
          }
        }}
      >
        <h3 id={title}>{actionLabels[action]}</h3>
        <p id={details}>
          {action === 'resume' && resumeMode === 'start_controller'
            ? 'Start the controller from the recorded checkpoint.'
            : actionDetails[action]}
        </p>
        <label>
          Reason
          <textarea
            autoFocus
            required
            maxLength={500}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            data-testid="factory-runs-operation-reason"
          />
        </label>
        {error && (
          <p className="factory-error" role="alert" data-testid="factory-runs-operation-error">
            {error}
          </p>
        )}
        <div className="factory-run-state-actions">
          <button
            type="submit"
            className="factory-node-evidence-button"
            disabled={busy || !reason.trim()}
            data-testid="factory-runs-operation-confirm"
          >
            {busy ? 'Working…' : `Confirm ${actionLabels[action].toLowerCase()}`}
          </button>
          <button
            type="button"
            className="factory-node-evidence-button"
            disabled={busy}
            onClick={onClose}
            data-testid="factory-runs-operation-cancel"
          >
            Cancel
          </button>
        </div>
      </form>
    </dialog>
  );
}

export function RunState({
  status,
  fallback,
  live,
  historical,
  actions,
  resumeMode,
  onRun,
  publishedReport,
}: {
  status?: RunStateRecord;
  fallback?: string;
  live: boolean;
  historical: boolean;
  actions: RunOperation[];
  resumeMode?: ResumeMode;
  onRun: (action: RunOperation, reason: string) => Promise<RunOperationResult>;
  publishedReport?: { label: string; outcome: string; onOpen: () => void };
}) {
  const [pending, setPending] = useState<RunOperation>();
  const [preview, setPreview] = useState<RunOperationResult>();
  const [notice, setNotice] = useState('');
  const permitted = pending && actions.includes(pending) ? pending : undefined;
  if (!status && !fallback && !actions.length) return null;
  return (
    <section className="factory-run-state" data-testid="factory-runs-state" data-variant={status?.state}>
      {status ? <RunStateBanner status={status} live={live && !historical} /> : <p>{fallback}</p>}
      {publishedReport && (
        <div className="factory-run-state-description">
          <p data-testid="factory-runs-published-outcome">{publishedReport.outcome}</p>
          <button type="button" data-testid="factory-runs-attached-report" onClick={publishedReport.onOpen}>
            {publishedReport.label}
          </button>
        </div>
      )}
      {historical && (
        <p className="factory-muted" data-testid="factory-runs-state-read-only">
          Read-only run
        </p>
      )}
      {actions.length > 0 && (
        <div
          className="factory-run-state-actions"
          aria-label="Run operator controls"
          data-testid="factory-runs-operations"
        >
          {actions.map((action) => (
            <button
              key={action}
              type="button"
              onClick={() => setPending(action)}
              className="factory-node-evidence-button"
              data-testid="factory-runs-operation-open"
              data-variant={action}
            >
              {actionLabels[action]}
            </button>
          ))}
        </div>
      )}
      {notice && (
        <p className="factory-run-state-notice" role="status" data-testid="factory-runs-operation-notice">
          <CircleAlert aria-hidden="true" size={16} /> {notice}
        </p>
      )}
      {preview && (
        <details open className="factory-node-evidence-disclosure" data-testid="factory-runs-operation-preview">
          <summary data-testid="factory-runs-operation-preview-toggle">Proposed graph revision</summary>
          <StructuredData value={preview} />
        </details>
      )}
      {permitted && (
        <RunConfirmation
          key={permitted}
          action={permitted}
          resumeMode={resumeMode}
          run={onRun}
          onClose={() => setPending(undefined)}
          onComplete={(action, result) => {
            setPending(undefined);
            setPreview(action === 'revise-preview' ? result : undefined);
            setNotice(
              action === 'pause'
                ? 'Pause requested.'
                : action === 'resume'
                  ? result.pid
                    ? `Controller started (process ${result.pid}).`
                    : 'Operator pause cleared.'
                  : action === 'revise-apply'
                    ? 'Graph revision applied.'
                    : '',
            );
          }}
        />
      )}
    </section>
  );
}
