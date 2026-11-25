import { useState } from 'react';
import type { EvidenceFile } from '../api';
import {
  attemptsOf,
  summarizeNode,
  type NodeCheckView,
  type NodeOperator,
  type OperatorOp,
  type OutputSummary,
  type PlanNode,
} from './checkModel';
import './nodeChecks.css';

const opLabel: Record<OperatorOp, string> = { hold: 'Hold', release: 'Release', reopen: 'Reopen' };
const opHint: Record<OperatorOp, string> = {
  hold: 'The node will not start or close until released. Upstream outputs are kept.',
  release: 'Lift the hold; the scheduler can run or close the node again.',
  reopen: 'Send this node and its descendants back to proposed. Earlier attempts and checks no longer count; upstream outputs are kept.',
};
const statusLabel = { passed: 'passed', failed: 'failed', running: 'running', unchecked: 'no check yet', stale: 'needs a new check' };

function fileFor(files: readonly EvidenceFile[] | undefined, artifact: string | undefined) {
  if (!artifact) return undefined;
  return files?.find((file) => (file.artifact_ids ?? []).some((id) => id === artifact));
}

function OutputCheck({
  row,
  files,
  onOpenFile,
}: {
  row: OutputSummary;
  files?: readonly EvidenceFile[];
  onOpenFile?: (path: string) => void;
}) {
  const { output, latest } = row;
  const older = row.history.slice(0, -1).reverse();
  const evidence = [
    ['review packet', latest?.review?.packet_artifact],
    ['review reply', latest?.review?.reply_artifact],
    ...(latest?.artifacts ?? []).map((id) => ['checked record', id]),
  ]
    .map(([label, id]) => ({ label, file: fileFor(files, id) }))
    .filter((entry, index, all) => entry.file && all.findIndex((other) => other.file?.path === entry.file?.path) === index);
  return (
    <li className="factory-check-output" data-testid="factory-runs-check-output" data-variant={output.name} data-status={row.status}>
      <div className="factory-check-output-head">
        <strong>{output.name}</strong>
        <small>
          {output.kind ?? 'output'}
          {output.required ? '' : ' · optional'}
          {output.declared ? '' : ' · no longer declared'}
        </small>
        <span className="factory-check-pill" data-status={row.status} data-testid="factory-runs-check-status">
          {statusLabel[row.status]}
        </span>
      </div>
      <p className="factory-check-how">
        {output.verifier ? <code>{output.verifier}</code> : <span>host record check</span>}
        {output.review && <span> + independent review</span>}
        {output.criteria && output.criteria.length > 0 && <span> · {output.criteria.length} criteria</span>}
      </p>
      {(row.stageRequired || row.stageReached) && (
        <p className="factory-check-stage" data-testid="factory-runs-check-stage" data-met={row.stageMet === undefined ? undefined : String(row.stageMet)}>
          <small>Stage</small> reached <b>{row.stageReached ?? '—'}</b> · required <b>{row.stageRequired ?? 'any'}</b>
        </p>
      )}
      {output.inputs && (
        <p className="factory-check-how">
          <small>Pinned verifier inputs</small> {Object.keys(output.inputs).join(', ')}
        </p>
      )}
      {latest && latest.reason && latest.reason !== 'passed' && (
        <p className="factory-check-reason" data-testid="factory-runs-check-reason">
          {latest.reason}
        </p>
      )}
      {row.verifierChecks.length > 0 && (
        <ul className="factory-check-list" data-testid="factory-runs-verifier-checks">
          {row.verifierChecks.map((check, index) => (
            <li key={`${check.name}:${index}`} data-status={(check.status ?? '').toLowerCase()} data-testid="factory-runs-verifier-check">
              <span className="factory-check-mark">{check.status ?? '?'}</span>
              <span>
                <b>{check.name ?? 'check'}</b>
                {check.stage && <small> · {check.stage}</small>}
                {check.detail && <span className="factory-check-detail"> {check.detail}</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
      {latest?.review && (
        <div className="factory-check-review" data-testid="factory-runs-review" data-verdict={latest.review.verdict ?? 'none'}>
          <p>
            <small>Reviewer</small> <b>{latest.review.verdict ?? 'no verdict'}</b>
            {latest.review.summary && <span> · {latest.review.summary}</span>}
          </p>
          {row.findings.length > 0 && (
            <ul className="factory-check-list">
              {row.findings.map((finding, index) => (
                <li key={index} data-status={finding.severity === 'blocker' ? 'fail' : finding.severity} data-testid="factory-runs-review-finding">
                  <span className="factory-check-mark">{finding.severity ?? '?'}</span>
                  <span>
                    {finding.file && (
                      <code>
                        {finding.file}
                        {finding.line ? `:${finding.line}` : ''}
                      </code>
                    )}{' '}
                    {finding.problem}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {latest && (
        <p className="factory-check-meta">
          <code title="node_check observation">{latest.obs_id}</code>
          {latest.cited && <span> · cited by the node</span>}
          {latest.reused_from && <span> · same work as {latest.reused_from}</span>}
          {typeof latest.seconds === 'number' && <span> · {latest.seconds.toFixed(0)} s</span>}
        </p>
      )}
      {evidence.length > 0 && (
        <p className="factory-check-meta">
          {evidence.map(({ label, file }) => (
            <button key={file?.path} type="button" className="factory-graph-file-link" onClick={() => file && onOpenFile?.(file.path)}>
              {label}
            </button>
          ))}
        </p>
      )}
      {older.length > 0 && (
        <details className="factory-check-older">
          <summary>{older.length} earlier check{older.length === 1 ? '' : 's'}</summary>
          <ul>
            {older.map((check) => (
              <li key={check.obs_id} data-superseded={check.superseded || undefined}>
                <code>{check.obs_id}</code> · {check.state !== 'finished' ? check.state : check.passed ? 'passed' : 'failed'}
                {check.superseded && <small> · superseded by an operator reopen</small>}
                {check.reason && check.reason !== 'passed' && <span> · {check.reason}</span>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </li>
  );
}

function OperatorActions({ node, operator }: { node: PlanNode; operator: NodeOperator }) {
  const actions = operator.actions(node);
  const [pending, setPending] = useState<OperatorOp>();
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (!actions.length || typeof node.node_id !== 'string') return null;
  const nodeId = node.node_id;
  const submit = async () => {
    if (!pending || !reason.trim()) return;
    setBusy(true);
    setError('');
    try {
      await operator.run(nodeId, pending, reason.trim());
      setPending(undefined);
      setReason('');
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="factory-node-operator" data-testid="factory-runs-node-operator">
      <h5>Operator</h5>
      <div className="factory-node-operator-buttons">
        {actions.map((op) => (
          <button
            key={op}
            type="button"
            className="factory-node-operator-button"
            data-testid="factory-runs-node-operator-action"
            data-variant={op}
            aria-pressed={pending === op}
            disabled={busy}
            onClick={() => {
              setPending(pending === op ? undefined : op);
              setError('');
            }}
          >
            {opLabel[op]}
          </button>
        ))}
      </div>
      {pending && (
        <form
          className="factory-node-operator-form"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <small>{opHint[pending]}</small>
          <input
            type="text"
            data-testid="factory-runs-node-operator-reason"
            placeholder={`Reason to ${pending} ${nodeId}`}
            value={reason}
            maxLength={500}
            autoFocus
            onChange={(event) => setReason(event.target.value)}
          />
          <div className="factory-node-operator-buttons">
            <button
              type="submit"
              className="factory-node-operator-button"
              data-variant="confirm"
              data-testid="factory-runs-node-operator-confirm"
              disabled={busy || !reason.trim()}
            >
              {busy ? 'Recording…' : `${opLabel[pending]} ${nodeId}`}
            </button>
            <button type="button" className="factory-node-operator-button" onClick={() => setPending(undefined)} disabled={busy}>
              Cancel
            </button>
          </div>
        </form>
      )}
      {error && (
        <p className="factory-check-reason" role="alert" data-testid="factory-runs-node-operator-error">
          {error}
        </p>
      )}
    </section>
  );
}

export function NodeChecks({
  view,
  node,
  files,
  onOpenFile,
  operator,
}: {
  view?: NodeCheckView;
  node: PlanNode;
  files?: readonly EvidenceFile[];
  onOpenFile?: (path: string) => void;
  operator?: NodeOperator;
}) {
  const summary = summarizeNode(view, node);
  const attempts = attemptsOf(node);
  const superseded = attempts.filter((attempt) => attempt.superseded);
  const ccs = [...new Set([...(view?.helpful_ccs ?? [])])];
  return (
    <>
      {operator && <OperatorActions node={node} operator={operator} />}
      {(view || summary.gate) && (
        <section className="factory-node-checks" data-testid="factory-runs-node-checks">
          <h5>How this node is checked</h5>
          {summary.gate && (
            <p className="factory-check-gate" data-kind={summary.gate.kind} data-testid="factory-runs-check-gate">
              {summary.gate.text}
            </p>
          )}
          {view && (ccs.length > 0 || view.capability) && (
            <p className="factory-check-how" data-testid="factory-runs-check-ccs">
              <small>Capsules</small> {ccs.map((cc) => <code key={cc}>{cc}</code>)}
              {view.capability && (
                <>
                  {' '}
                  <small>capability</small> <code>{view.capability}</code>
                </>
              )}
            </p>
          )}
          {view?.node_contract && (
            <p className="factory-check-how">
              <small>Node contract</small> <code>{view.node_contract}</code>
              {view.requirement_ids && view.requirement_ids.length > 0 && <span> · covers {view.requirement_ids.join(', ')}</span>}
            </p>
          )}
          {summary.outputs.length > 0 && (
            <ul className="factory-check-outputs">
              {summary.outputs.map((row) => (
                <OutputCheck key={row.output.name} row={row} files={files} onOpenFile={onOpenFile} />
              ))}
            </ul>
          )}
          {superseded.length > 0 && (
            <p className="factory-check-meta" data-testid="factory-runs-superseded-attempts">
              {superseded.length} earlier attempt{superseded.length === 1 ? '' : 's'} superseded by an operator reopen:{' '}
              {superseded.map((attempt) => (
                <code key={attempt.id}>{attempt.id}</code>
              ))}
            </p>
          )}
        </section>
      )}
    </>
  );
}
