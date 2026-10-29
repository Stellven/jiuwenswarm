import '../../styles/research-shell.css';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, MarkdownPane, Select } from '../ui';
import { downloadResearchExport, researchFetch, researchRequest } from '../../utils/researchClient';
import type { ResearchStatus } from './researchWorkflow';
import { researchExecutionDetails } from './researchWorkflow';
import { ResearchArtifactView } from './ResearchArtifactView';
import type { ResearchArtifact } from './researchArtifacts';
import { ResearchTimeline } from './ResearchTimeline';

export function ResearchRunControls({ run }: { run: ResearchStatus }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [cancelRequested, setCancelRequested] = useState(false);
  const [error, setError] = useState(false);
  const [inspection, setInspection] = useState<{ runId: string; files: Record<string, ResearchArtifact> } | null>(null);
  const [selected, setSelected] = useState('');
  const currentRun = useRef(run.run_id);
  currentRun.current = run.run_id;
  const files = inspection?.runId === run.run_id ? inspection.files : {};
  const artifact = files[selected];
  const execution = researchExecutionDetails(run);
  useEffect(() => {
    setBusy(false);
    setCancelRequested(false);
    setError(false);
    setSelected('');
  }, [run.run_id]);

  const perform = (action: () => Promise<void>) => {
    if (busy) return;
    const runId = run.run_id;
    setBusy(true);
    setError(false);
    void action()
      .catch(() => {
        if (currentRun.current === runId) setError(true);
      })
      .finally(() => {
        if (currentRun.current === runId) setBusy(false);
      });
  };
  const inspect = async () => {
    const runId = run.run_id;
    const response = await researchFetch(`/api/v1/runs/${encodeURIComponent(run.run_id)}/export`, {
      headers: { Accept: 'application/zip' },
    });
    const { default: JSZip } = await import('jszip');
    const archive = await JSZip.loadAsync(await response.arrayBuffer());
    const entry = archive.file('client_retrieval.json');
    if (!entry) throw new Error('Export manifest is unavailable');
    const manifest = JSON.parse(await entry.async('string')) as {
      run_id: string;
      audience: string;
      files: { path: string; media_type: string; audience: string; artifact_ref: { id: string; sha256: string } }[];
    };
    if (manifest.run_id !== run.run_id || manifest.audience !== 'researcher') throw new Error('Export scope differs');
    const visible: Record<string, ResearchArtifact> = Object.create(null);
    for (const file of manifest.files) {
      if (
        file.audience !== manifest.audience ||
        !/^[a-zA-Z0-9_][a-zA-Z0-9_./-]*$/.test(file.path) ||
        file.path.split('/').includes('..') ||
        !file.artifact_ref ||
        typeof file.artifact_ref.id !== 'string' ||
        !file.artifact_ref.id ||
        !/^[a-f0-9]{64}$/.test(file.artifact_ref.sha256)
      )
        throw new Error('Unsafe export member');
      if (!['text/markdown', 'text/plain', 'text/x-python', 'application/json'].includes(file.media_type)) continue;
      const member = archive.file(file.path);
      if (!member) throw new Error('Export member is unavailable');
      visible[file.path] = {
        path: file.path,
        mediaType: file.media_type,
        ref: file.artifact_ref,
        content: await member.async('string'),
      };
    }
    if (currentRun.current !== runId) return;
    setInspection({ runId, files: visible });
    setSelected(
      Object.keys(visible).find((path) => path.endsWith('research_report.md')) ??
        Object.keys(visible).find((path) => path.endsWith('research_brief.json')) ??
        Object.keys(visible).find((path) => path.endsWith('intent_ir.json')) ??
        Object.keys(visible)[0] ??
        '',
    );
  };
  return (
    <div className="research-inspection" data-testid="team-area-research-inspection" data-variant={run.run_id}>
      <p role="status" data-testid="team-area-research-status">
        {t('researchShell.status', { status: run.status })}
      </p>
      <dl className="research-inspection__details" data-testid="team-area-research-execution-details">
        <div data-testid="team-area-research-stage-detail">
          <dt className="font-medium" data-testid="team-area-research-stage-label">
            {t('researchShell.currentOrLastStage')}
          </dt>
          <dd
            className="whitespace-pre-wrap break-words"
            data-testid="team-area-research-stage"
            data-variant={execution.stage === null ? 'unavailable' : 'recorded'}
          >
            {execution.stage ?? t('researchShell.stageUnavailable')}
          </dd>
        </div>
        <div data-testid="team-area-research-reasons-detail">
          <dt className="font-medium" data-testid="team-area-research-reasons-label">
            {t('researchShell.executionReasons')}
          </dt>
          <dd>
            {execution.reasons.length > 0 ? (
              <ul className="space-y-1" data-testid="team-area-research-reasons">
                {execution.reasons.map((reason, index) => (
                  <li
                    key={`${index}:${reason}`}
                    className="whitespace-pre-wrap break-words"
                    data-testid="team-area-research-reason"
                    data-variant={index}
                  >
                    {reason || t('researchShell.reasonUnavailable')}
                  </li>
                ))}
              </ul>
            ) : (
              <p data-testid="team-area-research-reason-unavailable">{t('researchShell.reasonUnavailable')}</p>
            )}
          </dd>
        </div>
      </dl>
      <ResearchTimeline runId={run.run_id} revision={run.revision} />
      <p className="research-inspection__counts" data-testid="team-area-research-artifact-counts">
        {t('researchShell.artifactCounts', {
          accepted: run.accepted_refs.length,
          candidates: run.candidate_refs.length,
        })}
      </p>
      <div className="research-inspection__actions">
        <Button
          variant="primary"
          loading={busy}
          onClick={() => perform(inspect)}
          data-testid="team-area-research-inspect-btn"
        >
          {t('researchShell.inspect')}
        </Button>
        <Button
          disabled={busy}
          onClick={() => perform(() => downloadResearchExport(run.run_id))}
          data-testid="team-area-research-export-btn"
        >
          {t('researchShell.export')}
        </Button>
        {(run.status === 'in_progress' || run.status === 'paused') && (
          <Button
            variant="danger"
            disabled={busy || cancelRequested}
            data-testid="team-area-research-cancel-btn"
            onClick={() =>
              perform(async () => {
                await researchRequest(`/api/v1/runs/${encodeURIComponent(run.run_id)}/cancel`, {
                  method: 'POST',
                  body: JSON.stringify({ request_id: `cancel:${Date.now()}:${Math.random().toString(36).slice(2)}` }),
                });
                if (currentRun.current === run.run_id) setCancelRequested(true);
              })
            }
          >
            {t(cancelRequested ? 'researchShell.cancelRequested' : 'researchShell.cancel')}
          </Button>
        )}
      </div>
      {error && (
        <p role="alert" className="text-warn" data-testid="team-area-research-inspection-error">
          {t('researchShell.operationFailed')}
        </p>
      )}
      {Object.keys(files).length > 0 && (
        <>
          <Select
            value={selected}
            options={Object.keys(files).map((path) => ({ value: path, label: path }))}
            onChange={(value) => setSelected(String(value))}
            aria-label={t('researchShell.artifact')}
            data-testid="team-area-research-artifact-select"
          />
          {artifact &&
            (selected.endsWith('.md') ? (
              <MarkdownPane content={artifact.content} testId="team-area-research-report" />
            ) : (
              <ResearchArtifactView
                key={`${artifact.path}:${artifact.ref.sha256}`}
                artifact={artifact}
                accepted={run.accepted_refs}
                candidates={run.candidate_refs}
              />
            ))}
        </>
      )}
    </div>
  );
}
