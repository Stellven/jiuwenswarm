import { useTranslation } from 'react-i18next';
import type { TimelineVerifierResult } from './graphModel';

export function VerifierStatus({ status = 'no-node-check' }: { status?: 'pass' | 'fail' | 'no-node-check' }) {
  const { t } = useTranslation();
  return (
    <span
      className="factory-demo-verifier-status"
      data-testid="factory-runs-demo-verifier-status"
      data-variant={status}
    >
      {t(`factoryRuns.demoTaskChain.verifier.${status}`)}
    </span>
  );
}

export function NodeVerifier({
  result,
  onOpenRecord,
  compact = false,
}: {
  result: TimelineVerifierResult;
  onOpenRecord: (id: string) => void;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  const label = t('factoryRuns.demoTaskChain.nodeVerifier');
  const primary = result.records[0];
  const closure = result.closure;
  return (
    <div className="factory-demo-node-verifier" data-testid="factory-runs-demo-node-verifier">
      <div className="factory-demo-verifier-row">
        {compact && primary ? (
          <button
            className="factory-demo-verifier-link"
            type="button"
            data-testid="factory-runs-demo-task-node-verifier-link"
            data-variant={primary.id}
            onClick={() => onOpenRecord(primary.id)}
          >
            {label}
          </button>
        ) : (
          <span>{label}</span>
        )}
        {!closure && (
          <VerifierStatus
            status={result.status === 'pass' || result.status === 'fail' ? result.status : 'no-node-check'}
          />
        )}
      </div>
      {closure && (
        <p
          className="factory-demo-node-closure"
          data-testid="factory-runs-node-verifier-closure"
          data-variant={result.status}
        >
          {t(
            result.status === 'closed-by-decision'
              ? 'factoryRuns.demoTaskChain.closedByDecision'
              : 'factoryRuns.demoTaskChain.closedByUpdate',
          )}{' '}
          <button
            className="factory-demo-verifier-link"
            type="button"
            data-testid="factory-runs-node-verifier-record-link"
            data-variant={closure.decision_id ?? closure.id}
            onClick={() => onOpenRecord(closure.decision_id ?? closure.id)}
          >
            {closure.decision_id ?? closure.id}
          </button>
          {' · '}
          {t('factoryRuns.demoTaskChain.verifier.no-node-check')}
        </p>
      )}
      {!compact && result.records.length > 0 && (
        <ul role="list" data-testid="factory-runs-node-verifier-records">
          {result.records.map((record) => (
            <li key={record.id}>
              <button
                className="factory-demo-verifier-link"
                type="button"
                data-testid="factory-runs-node-verifier-record-link"
                data-variant={record.id}
                onClick={() => onOpenRecord(record.id)}
              >
                {record.output ?? record.id}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
