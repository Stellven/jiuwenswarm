import { useContext } from 'react';
import { useTranslation } from 'react-i18next';
import type { NativeActivitySource } from '../api';
import type { CapsuleFacts } from '../views/ccActivityModel';
import { CapsuleLinksContext } from './CapsuleChips';
import { capsuleDisplayTitle } from './capsuleModel';
import { capsuleHref } from './navigation';

export type ActivitySource = NativeActivitySource & { kind?: string };
export type ActivityLink = (record: ActivitySource) => void;

export function transcriptActivity(source: ActivitySource) {
  return source.kind === 'worker-call' || source.source_kind === 'worker-call';
}

export function CapsuleFactStatus({ fact, onOpenSource }: { fact: CapsuleFacts; onOpenSource?: ActivityLink }) {
  const { t } = useTranslation();
  const use = fact.uses.at(-1);
  const check = fact.checks[0];
  const status = (
    label: 'use' | 'verifier',
    value: CapsuleFacts['use'] | CapsuleFacts['verifier'],
    source?: Parameters<ActivityLink>[0],
  ) => (
    <span className="factory-cc-fact" data-testid={`factory-runs-cc-${label}`} data-variant={value}>
      <span>{t(`factoryRuns.ccActivity.${label}`)}</span>
      {source && onOpenSource && (!transcriptActivity(source) || source.path) ? (
        <button
          type="button"
          className="factory-demo-verifier-link"
          data-testid="factory-runs-cc-fact-source"
          data-variant={source.id}
          title={source.id}
          onClick={() => onOpenSource(source)}
        >
          {t(`factoryRuns.ccActivity.${value}`)}
        </button>
      ) : (
        <strong title={source?.id}>{t(`factoryRuns.ccActivity.${value}`)}</strong>
      )}
    </span>
  );
  return (
    <div className="factory-cc-facts" data-testid="factory-runs-cc-facts" data-variant={fact.id}>
      {status('use', fact.use, use)}
      {status('verifier', fact.verifier, check)}
    </div>
  );
}

export function BoundCapsules({
  facts,
  compact = false,
  onOpenSource,
}: {
  facts: readonly CapsuleFacts[];
  compact?: boolean;
  onOpenSource?: ActivityLink;
}) {
  const { t } = useTranslation();
  const catalog = useContext(CapsuleLinksContext);
  const visible = compact ? facts.slice(0, 3) : facts;
  const hiddenCount = facts.length - visible.length;
  const testId = compact ? 'factory-runs-demo-task-node-cc' : 'factory-runs-node-bound-cc';
  return (
    <div className="factory-bound-capsules" data-testid={testId}>
      <span data-testid={`${testId}-count`}>
        {facts.length
          ? t('factoryRuns.demoTaskChain.ccCount', { count: facts.length })
          : t('factoryRuns.demoTaskChain.noCC')}
      </span>
      {visible.length > 0 && (
        <ul role="list" data-testid={`${testId}-list`}>
          {visible.map((fact) => {
            const capsule = catalog.find((entry) => entry.id === fact.id) ?? { id: fact.id, name: fact.id };
            return (
              <li key={fact.id} className="factory-bound-capsule" data-testid={`${testId}-row`} data-variant={fact.id}>
                <a href={capsuleHref(capsule.name)} data-testid={`${testId}-link`} data-variant={fact.id}>
                  {capsuleDisplayTitle(capsule)}
                </a>
                <CapsuleFactStatus fact={fact} onOpenSource={onOpenSource} />
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
