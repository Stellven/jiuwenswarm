import { useId, useState, type FormEvent } from 'react';
import { Button } from '../../components/ui/Button/Button';
import { Dialog } from '../../components/ui/Dialog/Dialog';
import { factoryApi, type LaunchTemplate } from './api';
import { useSessionCopy } from './sessionLocale';
import './factorySession.css';

export function LaunchSessionDialog({
  enabled,
  templates,
  onClose,
  onLaunched,
}: {
  enabled: boolean;
  templates: LaunchTemplate[];
  onClose: () => void;
  onLaunched: (id: string) => void;
}) {
  const copy = useSessionCopy();
  const titleId = useId();
  const [templateId, setTemplateId] = useState('');
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState('');
  const template = templates.find((item) => item.id === templateId) ?? templates[0];
  const capsules = template?.capsules ?? [];

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (launching || !enabled || !template) return;
    setLaunching(true);
    setError('');
    try {
      const result = await factoryApi.launch(template.id);
      onLaunched(result.id);
      onClose();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLaunching(false);
    }
  }

  return (
    <Dialog open titleId={titleId} className="factory-session-dialog" onCancel={onClose} closeDisabled={launching}>
      <form
        className="factory-session-form"
        onSubmit={(event) => void submit(event)}
        data-testid="factory-runs-launch-dialog"
      >
        <h2 id={titleId} data-testid="factory-runs-launch-dialog-title">
          {copy.launch}
        </h2>
        {template ? (
          <>
            <label className="factory-session-field">
              <span>{copy.template}</span>
              <select
                data-testid="factory-runs-launch-template"
                value={template.id}
                onChange={(event) => {
                  setTemplateId(event.target.value);
                  setError('');
                }}
                disabled={launching}
              >
                {templates.map((item) => (
                  <option value={item.id} key={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <dl className="factory-session-launch-details">
              <div data-testid="factory-runs-launch-contract">
                <dt>{copy.contract}</dt>
                <dd>{template.contract_id ? <code>{template.contract_id}</code> : copy.noContract}</dd>
              </div>
              {template.objective && (
                <div data-testid="factory-runs-launch-objective">
                  <dt>{copy.objective}</dt>
                  <dd>{template.objective}</dd>
                </div>
              )}
              <div data-testid="factory-runs-launch-capsules">
                <dt>{copy.capsules}</dt>
                <dd>
                  {capsules.length ? (
                    <ul className="factory-session-capsule-list" data-testid="factory-runs-launch-capsule-list">
                      {capsules.map((capsule) => (
                        <li key={capsule} data-testid="factory-runs-launch-capsule" data-variant={capsule}>
                          <code>{capsule}</code>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    copy.noCapsules
                  )}
                </dd>
              </div>
            </dl>
          </>
        ) : (
          <p className="factory-session-note" data-testid="factory-runs-launch-no-templates">
            {copy.noTemplates}
          </p>
        )}
        {!enabled && (
          <p className="factory-session-note" data-testid="factory-runs-launch-disabled">
            {copy.disabled}
          </p>
        )}
        {error && (
          <p role="alert" className="factory-session-error" data-testid="factory-runs-launch-error">
            {error}
          </p>
        )}
        <footer className="factory-session-actions">
          <Button onClick={onClose} disabled={launching} data-testid="factory-runs-launch-cancel">
            {copy.cancel}
          </Button>
          <Button
            type="submit"
            variant="primary"
            loading={launching}
            disabled={!enabled || !template}
            data-testid="factory-runs-launch-confirm"
            data-variant={launching ? 'launching' : 'ready'}
          >
            {launching ? copy.launching : copy.start}
          </Button>
        </footer>
      </form>
    </Dialog>
  );
}
