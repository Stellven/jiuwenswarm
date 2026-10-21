import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Select } from '../ui/Select/Select';
import { Button } from '../ui/Button/Button';
import '../../styles/research-shell.css';
import {
  bootstrapResearchSession,
  hasResearchInputs,
  hasLocalChat,
  researchInteraction,
  refreshResearchRuntime,
  selectResearchInteraction,
  type ResearchInteraction,
  markResearchUpload,
  researchRequest,
  researchWorkspace,
  selectedResearchInputs,
  updateResearchInputs,
  rememberResearchUploads,
  forgetResearchUpload,
  uploadResearchInput,
  type ResearchUpload,
} from '../../utils/researchClient';

/** Controlled inputs attach to the next native prompt; they never dispatch work. */
export function ResearchInputs({ sessionId }: { sessionId: string }) {
  const { t } = useTranslation();
  const [enabled, setEnabled] = useState(false);
  const [kind, setKind] = useState<ResearchUpload['kind']>('docs');
  const [files, setFiles] = useState<ResearchUpload[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [interaction, setInteraction] = useState<ResearchInteraction>(() => researchInteraction(sessionId));
  const generation = useRef(0);
  const configured = hasResearchInputs();
  useEffect(() => {
    const changed = () => setInteraction(researchInteraction(sessionId));
    changed();
    window.addEventListener('research.runtime.changed', changed);
    return () => window.removeEventListener('research.runtime.changed', changed);
  }, [sessionId, enabled]);
  const refresh = async () => {
    const attempt = generation.current;
    const value = await researchRequest<ResearchUpload[]>(
      `/api/v1/inputs?scope_id=${encodeURIComponent(researchWorkspace())}`,
    );
    if (attempt === generation.current) {
      rememberResearchUploads(value, true);
      setFiles(value.filter((item) => item.status === 'uploaded'));
    }
  };
  useEffect(() => {
    let current = true;
    generation.current += 1;
    setFiles([]);
    setBusy(false);
    setError('');
    setNotice('');
    setSelected(selectedResearchInputs(sessionId));
    const changed = (event: Event) => {
      const detail = (event as CustomEvent<{ sessionId: string; ids: string[] }>).detail;
      if (detail.sessionId === sessionId) setSelected(detail.ids);
    };
    window.addEventListener('research.inputs.changed', changed);
    void bootstrapResearchSession()
      .then(async (ready) => {
        if (!current) return;
        setEnabled(ready);
        if (ready) setInteraction(researchInteraction(sessionId));
        if (ready) void refreshResearchRuntime().catch(() => { /* Settings retains actual setup diagnostics. */ });
        if (ready && hasResearchInputs()) await refresh();
      })
      .catch(() => {
        if (current) setError('researchInputs.authFailed');
      });
    return () => {
      current = false;
      generation.current += 1;
      window.removeEventListener('research.inputs.changed', changed);
    };
  }, [sessionId]);
  const choose = (update: (ids: string[]) => string[]) => {
    updateResearchInputs(sessionId, update);
  };
  const perform = async (operation: () => Promise<void>) => {
    const attempt = generation.current;
    setBusy(true);
    markResearchUpload(sessionId, true);
    setError('');
    setNotice('');
    try {
      await operation();
    } catch (cause) {
      const failure = cause as Error & { status?: number };
      const code = failure?.message;
      const key = code === 'UPLOAD_DOCUMENT_TYPE' ? 'researchInputs.documentType'
        : code === 'UPLOAD_REPOSITORY_TYPE' ? 'researchInputs.repositoryType'
        : code === 'UPLOAD_TOO_LARGE' || failure?.status === 413 ? 'researchInputs.tooLarge'
        : failure?.status === 401 || failure?.status === 403 ? 'researchInputs.authFailed'
        : failure?.status === 409 ? 'researchInputs.conflict'
        : failure?.status === 422 ? 'researchInputs.unreadable'
        : 'researchInputs.failed';
      if (attempt === generation.current) setError(key);
    } finally {
      if (attempt === generation.current) setBusy(false);
      markResearchUpload(sessionId, false);
    }
  };
  if (!enabled) return null;
  return (
    <section className="research-inputs" data-testid="chat-panel-research-inputs">
      <div className="research-inputs__toolbar">
        {hasLocalChat() && <Select
          className="research-inputs__kind"
          value={interaction}
          aria-label={t('researchWorkflow.mode')}
          data-testid="chat-panel-research-interaction"
          options={(['conversation', 'research'] as const).map((value) => ({ value, label: t(`researchWorkflow.${value}`) }))}
          onChange={(value) => {
            const mode = value as ResearchInteraction;
            selectResearchInteraction(sessionId, mode);
            setInteraction(mode);
          }}
        />}
        <span data-testid="chat-panel-research-inputs-title">{t('researchInputs.title')}</span>
        <Select
          className="research-inputs__kind"
          value={kind}
          disabled={busy || !configured}
          data-testid="chat-panel-research-input-kind"
          aria-label={t('researchInputs.kind')}
          onChange={(value) => setKind(value as ResearchUpload['kind'])}
          options={(['docs', 'repo', 'datasets'] as const).map((value) => ({
            value,
            label: t(`researchInputs.${value}`),
          }))}
        />
        <label
          className="research-inputs__upload"
          data-disabled={busy || !configured}
          data-testid="chat-panel-research-upload-label"
        >
          {t('researchInputs.upload')}
          <input
            type="file"
            disabled={busy || !configured}
            data-testid="chat-panel-research-upload"
            accept={kind === 'docs' ? '.txt,.md,.markdown,.pdf' : kind === 'repo' ? '.zip' : undefined}
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = '';
              if (file)
                void perform(async () => {
                  const attempt = generation.current;
                  const uploaded = await uploadResearchInput(kind, file);
                  if (attempt !== generation.current) return;
                  if (uploaded.filename !== file.name) setNotice(t('researchInputs.savedAs', { name: uploaded.filename }));
                  choose((current) => [...current, uploaded.id]);
                  await refresh();
                });
            }}
          />
        </label>
        {files.some((file) => !selected.includes(file.id)) && <Select
          className="research-inputs__kind"
          value=""
          disabled={busy || !configured}
          aria-label={t('researchInputs.attachSaved')}
          data-testid="chat-panel-research-attach-saved"
          options={[
            { value: '', label: t('researchInputs.attachSaved'), disabled: true },
            ...files.filter((file) => !selected.includes(file.id)).map((file) => ({ value: file.id, label: file.filename })),
          ]}
          onChange={(id) => { if (id) choose((current) => [...current, id]); }}
        />}
        <Button
          size="sm"
          variant="quiet"
          type="button"
          disabled={busy || !configured}
          data-testid="chat-panel-research-input-refresh"
          onClick={() => void perform(refresh)}
        >
          {t('researchInputs.refresh')}
        </Button>
      </div>
      <p className="research-inputs__hint" data-testid="chat-panel-research-input-hint">
        {t(interaction === 'research' ? 'researchWorkflow.researchHint' : configured ? 'researchInputs.hint' : 'researchInputs.setupRequired')}
      </p>
      {error && (
        <p role="alert" className="text-warn" data-testid="chat-panel-research-input-error">
          {t(error)}
        </p>
      )}
      {notice && <p className="research-inputs__hint" role="status" data-testid="chat-panel-research-upload-notice">{notice}</p>}
      <ul className="research-inputs__list" data-testid="chat-panel-research-input-list">
        {files.filter((file) => selected.includes(file.id)).map((file) => (
          <li
            key={file.id}
            className="flex items-center gap-2"
            data-testid="chat-panel-research-input-item"
            data-variant={file.id}
          >
            <label data-testid="chat-panel-research-input-label" data-variant={file.id}>
              <input
                type="checkbox"
                checked={selected.includes(file.id)}
                disabled={busy}
                data-testid="chat-panel-research-input-selected"
                data-variant={file.id}
                onChange={(event) =>
                  choose((current) => event.target.checked ? [...current, file.id] : current.filter((id) => id !== file.id))
                }
              />
              {file.filename}
            </label>
            <Button
              size="sm"
              variant="quiet"
              type="button"
              disabled={busy}
              data-testid="chat-panel-research-input-delete"
              data-variant={file.id}
              onClick={() =>
                void perform(async () => {
                  const attempt = generation.current;
                  await researchRequest(`/api/v1/inputs/${encodeURIComponent(file.id)}`, { method: 'DELETE' });
                  forgetResearchUpload(file.id);
                  if (attempt !== generation.current) return;
                  choose((current) => current.filter((id) => id !== file.id));
                  await refresh();
                })
              }
            >
              {t('researchInputs.delete')}
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}
