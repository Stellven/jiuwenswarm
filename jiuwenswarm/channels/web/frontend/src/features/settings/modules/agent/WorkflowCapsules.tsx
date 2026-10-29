import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../../../../components/ui';
import { hasResearchSession, refreshResearchRuntime, type ResearchRuntime } from '../../../../utils/researchClient';
import { SettingRow } from '../../components';

interface WorkflowRuntime extends ResearchRuntime {
  configured: boolean;
  ready: boolean;
  plan_source: 'static' | 'planned' | null;
  capsules: { stage: string; name: string; version: string; standing: string; eligible: boolean; checks: string[]; criteria: string[] }[];
  diagnostics: { code: string; detail: string }[];
  prerequisites: { name: string; status: string; reason: string }[];
}

/** Installed library observation, not a prompt preset or an activation control. */
export function WorkflowCapsules() {
  const { t } = useTranslation();
  const [runtime, setRuntime] = useState<WorkflowRuntime | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const enabled = hasResearchSession();
  const refresh = () => {
    setBusy(true);
    setError(false);
    void refreshResearchRuntime({ force: true })
      .then((value) => setRuntime(value as WorkflowRuntime)).catch(() => setError(true)).finally(() => setBusy(false));
  };
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    void refreshResearchRuntime()
      .then((value) => { if (live) setRuntime(value as WorkflowRuntime); })
      .catch(() => { if (live) setError(true); });
    return () => { live = false; };
  }, [enabled]);
  if (!enabled) return null;
  return <>
    <SettingRow
      title={t('researchWorkflow.title')}
      description={t(runtime?.ready ? 'researchWorkflow.ready' : runtime?.configured ? 'researchWorkflow.blocked' : 'researchWorkflow.setupRequired')}
      subSettings={runtime && <div data-testid="settings-workflow-prerequisites">
        {[...runtime.diagnostics.map((item) => ({ id: item.code, text: `${item.code}: ${item.detail}` })),
          ...runtime.prerequisites.filter((item) => item.status !== 'ready').map((item) => ({ id: item.name, text: `${item.name}: ${item.reason}` }))]
          .map((item) => <p key={item.id} className="text-warn break-words" data-testid="settings-workflow-prerequisite" data-variant={item.id}>{item.text}</p>)}
        <p data-testid="settings-workflow-plan-mode">{t('researchWorkflow.planMode', { mode: runtime.plan_source ?? t('researchWorkflow.unconfigured') })}</p>
      </div>}
    >
      <Button disabled={busy} loading={busy} onClick={refresh} data-testid="settings-workflow-refresh">{t('researchInputs.refresh')}</Button>
    </SettingRow>
    {error && <p role="alert" className="text-warn" data-testid="settings-workflow-error">{t('researchShell.operationFailed')}</p>}
    {runtime?.capsules.map((capsule) => <SettingRow
      key={capsule.stage}
      title={<span data-testid="settings-workflow-capsule-name" data-variant={capsule.stage}>{t(`researchWorkflow.stages.${capsule.stage}`)}</span>}
      description={`${capsule.name} · ${capsule.version}`}
      meta={<span data-testid="settings-workflow-capsule-status" data-variant={capsule.stage}>{t(capsule.eligible ? 'researchWorkflow.admitted' : 'researchWorkflow.notInstalled')}</span>}
      subSettings={capsule.eligible && <p data-testid="settings-workflow-capsule-checks" data-variant={capsule.stage}>
        {t('researchWorkflow.checkCounts', { checks: capsule.checks.length, criteria: capsule.criteria.length })}
      </p>}
    />)}
  </>;
}
