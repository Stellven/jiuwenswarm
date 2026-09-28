import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../../components/ui/Button/Button';
import { useCodexSubscription } from './state';
import './CodexSubscriptionPanel.css';

type Status = { state: string; error?: string; active_runs?: number; login_attempt_id?: string };
type Model = { id: string; name: string; default: boolean };
type Props = {
  connected: boolean;
  request: (method: string, params?: Record<string, unknown>) => Promise<unknown>;
};

export function CodexSubscriptionPanel({ connected, request }: Props) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<Status>({ state: 'checking' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [loginUrl, setLoginUrl] = useState('');
  const [loginAttempt, setLoginAttempt] = useState<string>();
  const [models, setModels] = useState<Model[]>([]);
  const revision = useRef(0);
  const pending = useRef(false);
  const model = useCodexSubscription((s) => s.model);

  const refresh = useCallback(async () => {
    if (!connected || pending.current) return;
    const current = revision.current;
    try {
      const next = (await request('codex.auth.status')) as Status;
      if (current !== revision.current) return;
      setStatus(next);
      setLoginAttempt(next.login_attempt_id);
      setError(next.error || '');
      useCodexSubscription.getState().set({ state: next.state });
      if (next.state === 'ready') {
        setLoginUrl('');
        const catalog = (await request('codex.models.list')) as { models: Model[] };
        if (current === revision.current) setModels(catalog.models);
      } else if (next.state !== 'signing_in') {
        setLoginUrl('');
        setModels([]);
      }
    } catch {
      if (current !== revision.current) return;
      setError('connection');
      setStatus({ state: 'unavailable' });
      useCodexSubscription.getState().set({ state: 'unavailable' });
    }
  }, [connected, request]);

  useEffect(() => {
    revision.current++;
    pending.current = false;
    setBusy(false);
    setLoginUrl('');
    if (!connected) {
      setStatus({ state: 'disconnected' });
      useCodexSubscription.getState().set({ state: 'disconnected' });
      return;
    }
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => {
      revision.current++;
      window.clearInterval(timer);
    };
  }, [connected, refresh]);

  const action = async (kind: 'login' | 'cancel' | 'logout') => {
    if (pending.current || !connected) return;
    pending.current = true;
    const current = ++revision.current;
    setBusy(true);
    setError('');
    setLoginUrl('');
    try {
      const result = (await request(
        `codex.auth.${kind}`,
        kind === 'cancel' ? { login_attempt_id: loginAttempt } : undefined,
      )) as Status & { auth_url?: string; login_attempt_id?: string };
      if (current !== revision.current) return;
      if (kind === 'login') {
        const url = new URL(result.auth_url || '');
        if (
          url.protocol !== 'https:' ||
          !['auth.openai.com', 'auth0.openai.com', 'auth.chatgpt.com'].includes(url.hostname)
        )
          throw new Error('Invalid login URL');
        setLoginAttempt(result.login_attempt_id);
        setLoginUrl(url.href);
        setStatus({ state: 'signing_in' });
        useCodexSubscription.getState().set({ state: 'signing_in' });
      } else {
        setStatus(result);
        useCodexSubscription.getState().set({ state: result.state, model: '' });
      }
    } catch {
      if (current === revision.current) setError('action');
    } finally {
      if (current === revision.current) {
        pending.current = false;
        setBusy(false);
      }
    }
  };

  return (
    <section
      className="codex-subscription"
      data-testid="codex-subscription-panel"
      aria-label={t('codexSubscription.title')}
    >
      <div className="codex-subscription__summary">
        <strong data-testid="codex-subscription-title">{t('codexSubscription.title')}</strong>
        <span role="status" data-testid="codex-subscription-status" data-variant={status.state}>
          {t(`codexSubscription.states.${status.state}`)}
        </span>
        <span className="codex-subscription__hint" data-testid="codex-subscription-scope">
          {t('codexSubscription.scope')}
        </span>
      </div>
      <div className="codex-subscription__actions">
        {status.state === 'ready' ? (
          <>
            <select
              data-testid="codex-subscription-model"
              aria-label={t('codexSubscription.model')}
              value={model}
              disabled={busy || !connected}
              onChange={(event) => useCodexSubscription.getState().set({ model: event.target.value })}
            >
              <option value="">{t('codexSubscription.defaultModel')}</option>
              {models.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            <Button
              data-testid="codex-subscription-logout"
              disabled={busy || !connected}
              onClick={() => void action('logout')}
            >
              {t('codexSubscription.logout')}
            </Button>
          </>
        ) : status.state === 'signing_in' ? (
          <>
            {loginUrl && (
              <a
                data-testid="codex-subscription-login-link"
                href={loginUrl}
                target="_blank"
                rel="noopener noreferrer"
                referrerPolicy="no-referrer"
              >
                {t('codexSubscription.openLogin')}
              </a>
            )}
            <Button
              data-testid="codex-subscription-cancel"
              disabled={busy || !connected}
              onClick={() => void action('cancel')}
            >
              {t('codexSubscription.cancel')}
            </Button>
          </>
        ) : (
          <Button
            data-testid="codex-subscription-login"
            variant="primary"
            disabled={busy || !connected || status.state === 'checking'}
            onClick={() => void action('login')}
          >
            {t('codexSubscription.login')}
          </Button>
        )}
        <Button data-testid="codex-subscription-refresh" disabled={busy || !connected} onClick={() => void refresh()}>
          {t('codexSubscription.refresh')}
        </Button>
      </div>
      {error && (
        <p role="alert" className="codex-subscription__error" data-testid="codex-subscription-error">
          {t('codexSubscription.error')}
        </p>
      )}
    </section>
  );
}
