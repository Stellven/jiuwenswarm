import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Select } from '../ui/Select/Select';
import {
  bootstrapResearchSession,
  markResearchUpload,
  researchRequest,
  researchWorkspace,
  selectedResearchInputs,
  selectResearchInputs,
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
  const [error, setError] = useState(false);
  const refresh = async () => {
    const value = await researchRequest<ResearchUpload[]>(
      `/api/v1/inputs?scope_id=${encodeURIComponent(researchWorkspace())}`,
    );
    setFiles(value.filter((item) => item.status === 'uploaded'));
  };
  useEffect(() => {
    let current = true;
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
        if (ready) await refresh();
      })
      .catch(() => {
        if (current) setError(true);
      });
    return () => {
      current = false;
      window.removeEventListener('research.inputs.changed', changed);
    };
  }, [sessionId]);
  const choose = (ids: string[]) => {
    setSelected(ids);
    selectResearchInputs(sessionId, ids);
  };
  const perform = async (operation: () => Promise<void>) => {
    setBusy(true);
    markResearchUpload(sessionId, true);
    setError(false);
    try {
      await operation();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
      markResearchUpload(sessionId, false);
    }
  };
  if (!enabled) return null;
  return (
    <section className="flex flex-col gap-2 p-2 text-sm text-text-primary" data-testid="chat-panel-research-inputs">
      <div className="flex flex-wrap items-center gap-2">
        <span data-testid="chat-panel-research-inputs-title">{t('researchInputs.title')}</span>
        <Select
          value={kind}
          disabled={busy}
          data-testid="chat-panel-research-input-kind"
          aria-label={t('researchInputs.kind')}
          onChange={(value) => setKind(value as ResearchUpload['kind'])}
          options={(['docs', 'repo', 'datasets'] as const).map((value) => ({
            value,
            label: t(`researchInputs.${value}`),
          }))}
        />
        <label data-testid="chat-panel-research-upload-label">
          {t('researchInputs.upload')}
          <input
            type="file"
            disabled={busy}
            data-testid="chat-panel-research-upload"
            accept={kind === 'docs' ? '.txt,.md,.pdf' : kind === 'repo' ? '.zip' : undefined}
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = '';
              if (file)
                void perform(async () => {
                  const uploaded = await uploadResearchInput(kind, file);
                  choose([...selected, uploaded.id]);
                  await refresh();
                });
            }}
          />
        </label>
        <button
          type="button"
          disabled={busy}
          data-testid="chat-panel-research-input-refresh"
          onClick={() => void perform(refresh)}
        >
          {t('researchInputs.refresh')}
        </button>
      </div>
      <p className="text-text-secondary" data-testid="chat-panel-research-input-hint">
        {t('researchInputs.hint')}
      </p>
      {error && (
        <p role="alert" className="text-warn" data-testid="chat-panel-research-input-error">
          {t('researchInputs.failed')}
        </p>
      )}
      <ul data-testid="chat-panel-research-input-list">
        {files.map((file) => (
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
                  choose(event.target.checked ? [...selected, file.id] : selected.filter((id) => id !== file.id))
                }
              />
              {file.filename}
            </label>
            <button
              type="button"
              disabled={busy}
              data-testid="chat-panel-research-input-delete"
              data-variant={file.id}
              onClick={() =>
                void perform(async () => {
                  await researchRequest(`/api/v1/inputs/${encodeURIComponent(file.id)}`, { method: 'DELETE' });
                  choose(selected.filter((id) => id !== file.id));
                  await refresh();
                })
              }
            >
              {t('researchInputs.delete')}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
