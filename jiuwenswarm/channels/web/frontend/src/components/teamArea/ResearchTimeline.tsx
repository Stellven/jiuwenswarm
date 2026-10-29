import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../ui';
import { researchRequest } from '../../utils/researchClient';

interface Check { check_id?: string; criterion_id?: string; outcome: string; reason: string }
interface Entry {
  kind: 'invocation' | 'model_call' | 'gate';
  ref: { id: string };
  node_id: string;
  subnode_id: string | null;
  scope?: string;
  outcome?: string;
  verdict?: string;
  action?: string;
  reason?: string;
  effective_model?: string | null;
  requested_model?: string | null;
  function?: string;
  route_source?: string | null;
  checks?: Check[];
  findings?: Check[];
}

export function ResearchTimeline({ runId, revision }: { runId: string; revision: number }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [events, setEvents] = useState<Entry[]>([]);
  const [error, setError] = useState(false);
  useEffect(() => {
    setEvents([]);
    setError(false);
  }, [runId]);
  useEffect(() => {
    if (!expanded) return;
    let live = true;
    void researchRequest<{ run_id: string; events: Entry[] }>(`/api/v1/runs/${encodeURIComponent(runId)}/timeline`)
      .then((value) => { if (live && value.run_id === runId) { setEvents(value.events); setError(false); } })
      .catch(() => { if (live) setError(true); });
    return () => { live = false; };
  }, [runId, revision, expanded]);
  return <div data-testid="team-area-research-timeline">
    <Button variant="quiet" aria-expanded={expanded} onClick={() => setExpanded(!expanded)} data-testid="team-area-research-timeline-toggle">
      {t(expanded ? 'researchWorkflow.hideChecks' : 'researchWorkflow.showChecks')}
    </Button>
    {expanded && <ol className="research-timeline" data-testid="team-area-research-timeline-events">
      {events.map((entry) => <li key={entry.ref.id} data-testid="team-area-research-timeline-event" data-variant={entry.ref.id}>
        <div className="research-timeline__heading">
          <strong>{entry.subnode_id ?? entry.node_id}</strong>
          <span>{entry.kind === 'gate' ? `${t('researchWorkflow.gate')}: ${entry.verdict} · ${entry.action}` : entry.kind === 'model_call' ? t('researchWorkflow.modelCall', { outcome: entry.outcome }) : entry.outcome}</span>
        </div>
        {entry.kind === 'model_call' && <p className="text-text-secondary" data-testid="team-area-research-model-route" data-variant={entry.ref.id}>
          {t('researchWorkflow.modelRoute', { model: entry.effective_model ?? t('researchWorkflow.modelUnobserved'), route: entry.requested_model ?? t('researchWorkflow.unconfigured') })}
        </p>}
        {entry.reason && <p className="text-warn">{entry.reason}</p>}
        {[...(entry.checks ?? []), ...(entry.findings ?? [])].map((check) => <div key={check.check_id ?? check.criterion_id} className="research-timeline__check" data-testid="team-area-research-check" data-variant={check.check_id ?? check.criterion_id}>
          <span>{check.check_id ?? check.criterion_id}</span><strong>{check.outcome}</strong>
          {check.outcome !== 'PASS' && <p className="text-warn">{check.reason}</p>}
        </div>)}
      </li>)}
      {!events.length && !error && <li data-testid="team-area-research-timeline-empty">{t('researchWorkflow.noChecks')}</li>}
    </ol>}
    {expanded && error && <p role="alert" className="text-warn" data-testid="team-area-research-timeline-error">{t('researchShell.operationFailed')}</p>}
  </div>;
}
