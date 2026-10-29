import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../../components/ui/Button/Button';
import { useCodexSubscription } from './state';
import { hasResearchSession, hasResearchConfiguration, hasLocalChat } from '../../utils/researchClient';
import './CodexSubscriptionPanel.css';
import { SettingRow } from '../settings/components/SettingRow';
import { Select } from '../../components/ui/Select/Select';

type Status = {
  state: string;
  error?: string;
  active_runs?: number;
  login_attempt_id?: string;
  auth_url?: string;
  user_code?: string;
};
type Model = { id: string; name: string; default: boolean };
type Props = {
  connected: boolean;
  request: (method: string, params?: Record<string, unknown>) => Promise<unknown>;
  showModelSelector?: boolean;
};

export function CodexSubscriptionConnection({ connected, request }: Props) {
  useEffect(() => {
    if (!connected) return;
    let disposed = false;
    const refresh = async () => {
      try {
        const status = (await request('codex.auth.status')) as Status;
        if (!disposed)
          useCodexSubscription
            .getState()
            .set({ state: status.state, ...(hasLocalChat() ? { model: 'gpt-6.1-sol' } : {}) });
      } catch {
        if (!disposed) useCodexSubscription.getState().set({ state: 'unavailable' });
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 10000);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [connected, request]);
  return null;
}

export function CodexSubscriptionPanel({ connected, request, showModelSelector = true }: Props) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<Status>({ state: 'checking' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [loginUrl, setLoginUrl] = useState('');
  const [userCode, setUserCode] = useState('');
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
      setUserCode(next.user_code || '');
      if (next.state === 'signing_in' && next.auth_url) {
        const url = new URL(next.auth_url);
        if (
          url.protocol === 'https:' &&
          ['auth.openai.com', 'auth0.openai.com', 'auth.chatgpt.com'].includes(url.hostname)
        ) {
          setLoginUrl(url.href);
        }
      }
      setError(next.error || '');
      useCodexSubscription.getState().set({ state: next.state });
      if (next.state === 'ready') {
        setLoginUrl('');
        if (hasLocalChat()) {
          setModels([{ id: 'gpt-6.1-sol', name: 'GPT-6.1 Sol', default: true }]);
          useCodexSubscription.getState().set({ model: 'gpt-6.1-sol' });
          return;
        }
        const catalog = (await request('codex.models.list')) as { models: Model[] };
        if (current === revision.current) {
          setModels(catalog.models);
        }
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
    setUserCode('');
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
    const loginWindow = kind === 'login' ? window.open('about:blank', '_blank') : null;
    if (loginWindow) loginWindow.opener = null;
    pending.current = true;
    const current = ++revision.current;
    setBusy(true);
    setError('');
    setLoginUrl('');
    setUserCode('');
    try {
      const result = (await request(
        `codex.auth.${kind}`,
        kind === 'cancel' ? { login_attempt_id: loginAttempt } : undefined,
      )) as Status & { auth_url?: string; login_attempt_id?: string };
      if (current !== revision.current) {
        loginWindow?.close();
        return;
      }
      if (kind === 'login') {
        const url = new URL(result.auth_url || '');
        if (
          url.protocol !== 'https:' ||
          !['auth.openai.com', 'auth0.openai.com', 'auth.chatgpt.com'].includes(url.hostname)
        )
          throw new Error('Invalid login URL');
        setLoginAttempt(result.login_attempt_id);
        setLoginUrl(url.href);
        setUserCode(result.user_code || '');
        if (loginWindow && !loginWindow.closed) loginWindow.location.replace(url.href);
        setStatus({ state: 'signing_in' });
        useCodexSubscription.getState().set({ state: 'signing_in' });
      } else {
        setStatus(result);
        useCodexSubscription.getState().set({ state: result.state, model: '' });
      }
    } catch {
      loginWindow?.close();
      if (current === revision.current) setError('action');
    } finally {
      if (current === revision.current) {
        pending.current = false;
        setBusy(false);
      }
    }
  };

  return (
    <div data-variant={status.state} data-testid="codex-subscription-panel" aria-label={t('codexSubscription.title')}>
      <SettingRow
        title={<span data-testid="codex-subscription-title">{t('codexSubscription.title')}</span>}
        meta={
          <span role="status" data-testid="codex-subscription-status" data-variant={status.state}>
            {t(`codexSubscription.states.${status.state}`)}
          </span>
        }
        description={
          <span data-testid="codex-subscription-scope">
            {t(
              !showModelSelector
                ? 'researchModels.chatgptDescription'
                : hasLocalChat()
                  ? 'codexSubscription.localChat'
                  : hasResearchSession() && !hasResearchConfiguration()
                    ? 'codexSubscription.setupRequired'
                    : 'codexSubscription.scope',
            )}
          </span>
        }
      >
        <div className="codex-subscription__actions">
          {status.state === 'ready' ? (
            <>
              {showModelSelector && (
                <Select
                  data-testid="codex-subscription-model"
                  aria-label={t('codexSubscription.model')}
                  value={model}
                  disabled={busy || !connected}
                  onChange={(value) => useCodexSubscription.getState().set({ model: value })}
                  options={[
                    ...(!hasLocalChat() ? [{ value: '', label: t('codexSubscription.defaultModel') }] : []),
                    ...models.map((item) => ({ value: item.id, label: item.name })),
                  ]}
                />
              )}
              <Button
                data-testid="codex-subscription-logout"
                size="sm"
                variant="quiet"
                disabled={busy || !connected}
                onClick={() => void action('logout')}
              >
                {t('codexSubscription.logout')}
              </Button>
            </>
          ) : status.state === 'signing_in' ? (
            <>
              {userCode && (
                <span className="codex-subscription__device" data-testid="codex-subscription-device-code">
                  {t('codexSubscription.deviceCode')} <code>{userCode}</code>
                </span>
              )}
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
          <Button
            size="sm"
            variant="quiet"
            data-testid="codex-subscription-refresh"
            disabled={busy || !connected}
            onClick={() => void refresh()}
          >
            {t('codexSubscription.refresh')}
          </Button>
        </div>
      </SettingRow>
      {error && (
        <p role="alert" className="codex-subscription__error" data-testid="codex-subscription-error">
          {t('codexSubscription.error')}
        </p>
      )}
    </div>
  );
}
