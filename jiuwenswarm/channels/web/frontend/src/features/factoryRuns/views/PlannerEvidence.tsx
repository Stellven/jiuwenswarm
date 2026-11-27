import { useContext, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { EvidenceFile, JsonRecord, NodeContract, PlannerNode, PlannerSource } from '../api';
import { BoundCapsules, type ActivityLink } from '../cc/BoundCapsules';
import type { CapsuleFacts } from './ccActivityModel';
import { CapsuleLinksContext } from '../cc/CapsuleChips';
import { capsuleDisplayTitle } from '../cc/capsuleModel';
import { capsuleHref } from '../cc/navigation';
import { evidenceRecord, evidenceText } from './nodeEvidenceModel';
import { comparisonDraft } from './plannerViewModel';

export function PlannerCapsules({ ids, kind }: { ids: readonly string[]; kind: 'suggested' | 'bound' }) {
  const { t } = useTranslation();
  const catalog = useContext(CapsuleLinksContext);
  const label = t(`factoryRuns.planner.${kind}`);
  return (
    <div className="factory-planner-capsules" data-testid="factory-runs-planner-capsules" data-variant={kind}>
      <span>{label}</span>
      {ids.length ? (
        <ul role="list">
          {ids.map((id) => {
            const capsule = catalog.find((candidate) => candidate.id === id);
            const title = capsuleDisplayTitle(capsule ?? { id, name: id });
            return (
              <li key={id} data-testid="factory-runs-planner-capsule" data-variant={id}>
                {capsule ? (
                  <a href={capsuleHref(capsule.name)} data-testid="factory-runs-planner-capsule-link">
                    {title}
                  </a>
                ) : (
                  title
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p>{t('factoryRuns.planner.noCapsules')}</p>
      )}
    </div>
  );
}

export function contractObjective(document: JsonRecord | null | undefined) {
  return evidenceText(document?.objective) ?? evidenceText(evidenceRecord(document?.briefing)?.summary);
}

type Links = {
  files: readonly EvidenceFile[];
  onOpenFile: (path: string) => void;
  onOpenRecord?: (id: string) => void;
};

function RecordLink({ source, files, onOpenFile, onOpenRecord }: Links & { source?: PlannerSource | null }) {
  const { t } = useTranslation();
  const path = source?.path;
  const id = source?.id;
  const open =
    path && files.some((file) => file.path === path && file.integrity !== 'missing')
      ? () => onOpenFile(path)
      : id && onOpenRecord
        ? () => onOpenRecord(id)
        : undefined;
  return open ? (
    <button type="button" data-testid="factory-runs-planner-source" onClick={open} title={id}>
      {t('factoryRuns.planner.openSource')}
    </button>
  ) : id ? (
    <code className="factory-muted" data-testid="factory-runs-planner-source-id">
      {id}
    </code>
  ) : null;
}

function ContractDocument({
  document,
  kind,
  facts,
  onOpenActivity,
}: {
  document: JsonRecord;
  kind: 'suggested' | 'bound';
  facts?: readonly CapsuleFacts[];
  onOpenActivity?: ActivityLink;
}) {
  const { t } = useTranslation();
  const objective = contractObjective(document);
  const work = evidenceRecord(document.work);
  const capsules = kind === 'suggested' ? work?.helpful_ccs : work?.bound_ccs;
  const ids = Array.isArray(capsules) ? capsules.filter((id): id is string => typeof id === 'string') : [];
  const recorded = facts?.filter((fact) => ids.some((id) => id.split('@', 1)[0] === fact.id)) ?? [];
  const remaining = ids.filter((id) => !recorded.some((fact) => id.split('@', 1)[0] === fact.id));
  return (
    <>
      {objective && <p>{objective}</p>}
      {Array.isArray(capsules) && (!recorded.length || remaining.length > 0) && (
        <PlannerCapsules ids={remaining} kind={kind} />
      )}
      {recorded.length > 0 && <BoundCapsules facts={recorded} onOpenSource={onOpenActivity} />}
      <details className="factory-node-evidence-disclosure">
        <summary data-testid="factory-runs-planner-contract-json">{t('factoryRuns.planner.recordedJson')}</summary>
        <pre>{JSON.stringify(document, null, 2)}</pre>
      </details>
    </>
  );
}

function RecordedChanges({ changes }: { changes?: readonly JsonRecord[] | null }) {
  const { t } = useTranslation();
  return (
    <section className="factory-planner-diff" data-testid="factory-runs-planner-diff">
      <h3>{t('factoryRuns.planner.recordedDiff')}</h3>
      {!changes?.length ? (
        <p className="factory-muted">{t(changes ? 'factoryRuns.planner.noChanges' : 'factoryRuns.planner.noDiff')}</p>
      ) : (
        <dl>
          {changes.map((change, index) => {
            const path = evidenceText(change.path) ?? String(index + 1);
            return (
              <div key={path} data-testid="factory-runs-planner-diff-field" data-variant={path}>
                <dt>
                  <code>{path}</code>
                </dt>
                <dd>
                  <div className="factory-planner-diff-before">
                    <span>{t('factoryRuns.planner.before')}</span>
                    <pre>{change.before == null ? '—' : JSON.stringify(change.before, null, 2)}</pre>
                  </div>
                  <div className="factory-planner-diff-after">
                    <span>{t('factoryRuns.planner.after')}</span>
                    <pre>{change.after == null ? '—' : JSON.stringify(change.after, null, 2)}</pre>
                  </div>
                </dd>
              </div>
            );
          })}
        </dl>
      )}
    </section>
  );
}

export function PlannerNodeComparison({
  node,
  fallback,
  capsuleFacts,
  onOpenActivity,
  ...links
}: Links & {
  node?: PlannerNode;
  fallback?: NodeContract;
  capsuleFacts?: readonly CapsuleFacts[];
  onOpenActivity?: ActivityLink;
}) {
  const { t } = useTranslation();
  const [chosenFinal, setChosenFinal] = useState<number>();
  const { draft, source, final } = comparisonDraft(node, chosenFinal);
  const finalDocument = final?.final ?? (fallback?.final_source ? fallback.final : undefined);
  const result = final?.never_weaker.status ?? (node?.refusals.length ? 'refused' : 'missing');
  return (
    <section className="factory-planner-comparison" data-testid="factory-runs-planner-comparison">
      {node && node.finals.length > 1 && (
        <label className="factory-replay-evidence-controls">
          {t('factoryRuns.planner.finalizationRecord')}
          <select
            data-testid="factory-runs-planner-finalization-selector"
            value={chosenFinal ?? node.finals.length - 1}
            onChange={(event) => setChosenFinal(Number(event.target.value))}
          >
            {node.finals.map((record, index) => (
              <option key={record.id ?? index} value={index}>
                {record.digest ? record.digest.slice(0, 12) : index + 1}
              </option>
            ))}
          </select>
        </label>
      )}
      <div className="factory-planner-contract-grid">
        <section data-testid="factory-runs-planner-draft">
          <h3>{t('factoryRuns.planner.draft')}</h3>
          {draft ? (
            <ContractDocument document={draft} kind="suggested" />
          ) : (
            <p className="factory-muted">{t('factoryRuns.planner.noDraft')}</p>
          )}
          {final?.preliminary_digest && <code className="factory-muted">{final.preliminary_digest}</code>}
          <RecordLink {...links} source={source} />
        </section>
        <section data-testid="factory-runs-planner-final">
          <h3>{t('factoryRuns.planner.final')}</h3>
          {finalDocument ? (
            <ContractDocument
              document={finalDocument}
              kind="bound"
              facts={capsuleFacts}
              onOpenActivity={onOpenActivity}
            />
          ) : (
            <p className="factory-muted">{t('factoryRuns.planner.noFinal')}</p>
          )}
          {final?.rationale && <p data-testid="factory-runs-planner-rationale">{final.rationale}</p>}
          <RecordLink {...links} source={final} />
        </section>
        <section data-testid="factory-runs-planner-never-weaker" data-variant={result}>
          <h3>{t('factoryRuns.planner.neverWeaker')}</h3>
          <p>{t(result === 'missing' ? 'factoryRuns.planner.noAdmission' : `factoryRuns.planner.${result}`)}</p>
          <RecordLink {...links} source={final?.never_weaker.source} />
          {node?.refusals.map((refusal, index) => (
            <details
              key={refusal.id ?? index}
              className="factory-node-evidence-disclosure"
              data-testid="factory-runs-planner-refusal"
              data-variant={refusal.id}
            >
              <summary>{t('factoryRuns.planner.refused')}</summary>
              {refusal.rationale && <p>{refusal.rationale}</p>}
              {refusal.problems != null && <pre>{JSON.stringify(refusal.problems, null, 2)}</pre>}
              <RecordLink {...links} source={refusal} />
            </details>
          ))}
        </section>
      </div>
      <RecordedChanges changes={final?.diff} />
    </section>
  );
}
