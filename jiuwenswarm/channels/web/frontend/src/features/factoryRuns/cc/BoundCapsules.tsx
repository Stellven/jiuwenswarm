import { useContext } from 'react';
import { useTranslation } from 'react-i18next';
import type { TimelineVerifierResult } from '../views/graphModel';
import { VerifierStatus } from '../views/TimelineVerifier';
import { CapsuleLinksContext } from './CapsuleChips';
import { capsuleDisplayTitle } from './capsuleModel';
import { capsuleHref } from './navigation';

export function BoundCapsules({
  ids,
  results,
  compact = false,
}: {
  ids: readonly string[];
  results: Readonly<Record<string, TimelineVerifierResult>>;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  const catalog = useContext(CapsuleLinksContext);
  const visibleIds = compact ? ids.slice(0, 3) : ids;
  const hiddenCount = ids.length - visibleIds.length;
  const testId = compact ? 'factory-runs-demo-task-node-cc' : 'factory-runs-node-bound-cc';
  return (
    <div className="factory-bound-capsules" data-testid={testId}>
      <span data-testid={`${testId}-count`}>
        {ids.length
          ? t('factoryRuns.demoTaskChain.ccCount', { count: ids.length })
          : t('factoryRuns.demoTaskChain.noCC')}
      </span>
      {visibleIds.length > 0 && (
        <ul role="list" data-testid={`${testId}-list`}>
          {visibleIds.map((id) => {
            const capsule = catalog.find((entry) => entry.id === id) ?? { id, name: id };
            return (
              <li key={id} className="factory-demo-verifier-row" data-testid={`${testId}-row`} data-variant={id}>
                <a href={capsuleHref(capsule.name)} data-testid={`${testId}-link`} data-variant={id}>
                  {capsuleDisplayTitle(capsule)}
                </a>
                <VerifierStatus status={results[id]?.status} />
              </li>
            );
          })}
        </ul>
      )}
      {hiddenCount > 0 && (
        <span data-testid={`${testId}-more`}>{t('factoryRuns.demoTaskChain.moreCCs', { count: hiddenCount })}</span>
      )}
    </div>
  );
}
