import { useContext } from 'react';
import { useTranslation } from 'react-i18next';
import { CapsuleLinksContext } from './CapsuleChips';
import { capsuleDisplayTitle } from './capsuleModel';
import { capsuleHref } from './navigation';

export function BoundCapsules({ ids, compact = false }: { ids: readonly string[]; compact?: boolean }) {
  const { t } = useTranslation();
  const catalog = useContext(CapsuleLinksContext);
  const showNames = !compact || ids.length <= 3;
  const testId = compact ? 'factory-runs-demo-task-node-cc' : 'factory-runs-node-bound-cc';
  return (
    <div className="factory-bound-capsules" data-testid={testId}>
      <span data-testid={`${testId}-count`}>
        {ids.length
          ? t('factoryRuns.demoTaskChain.ccCount', { count: ids.length })
          : t('factoryRuns.demoTaskChain.noCC')}
      </span>
      {showNames && ids.length > 0 && (
        <ul role="list" data-testid={`${testId}-list`}>
          {ids.map((id) => {
            const capsule = catalog.find((entry) => entry.id === id) ?? { id, name: id };
            return (
              <li key={id}>
                <a href={capsuleHref(capsule.name)} data-testid={`${testId}-link`} data-variant={id}>
                  {capsuleDisplayTitle(capsule)}
                </a>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
