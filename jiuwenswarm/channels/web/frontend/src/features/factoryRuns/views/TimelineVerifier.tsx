import { useTranslation } from 'react-i18next';
import type { TimelineVerifierResult } from './graphModel';

export function VerifierStatus({ status = 'not-run' }: { status?: TimelineVerifierResult['status'] }) {
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
        <VerifierStatus status={result.status} />
      </div>
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
                {record.output}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
