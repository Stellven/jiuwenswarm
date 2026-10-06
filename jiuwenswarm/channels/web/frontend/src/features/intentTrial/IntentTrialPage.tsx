import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import './IntentTrialPage.css';

type TrialRun = {
  run_id: string;
  client_request_id: string;
  status: string;
  accepted_intent?: unknown;
  accepted_ref?: { sha256: string } | null;
  decision?: { reasons: string[]; verdict: string } | null;
  attention?: { attention_id?: string; reason: string[]; action: string }[];
  bundle_url: string;
  mock: boolean;
};
const terminal = new Set(['ACCEPTED', 'FAILED', 'ENVIRONMENT_BLOCKED', 'INCONCLUSIVE', 'CANCELLED', 'PAUSED']);
const pendingKey = 'intent-trial-pending-request';
type RequestError = Error & { status?: number; confirmedRejection?: boolean };

export function IntentTrialPage() {
  const { t } = useTranslation();
  const [token, setToken] = useState('');
  const [text, setText] = useState('');
  const [runs, setRuns] = useState<TrialRun[]>([]);
  const [selected, setSelected] = useState<TrialRun | null>(null);
  const [message, setMessage] = useState('');
  const [readiness, setReadiness] = useState('');
  const [loginUrl, setLoginUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [pendingRequest, setPendingRequest] = useState(() => localStorage.getItem(pendingKey));
  const [freshAvailable, setFreshAvailable] = useState(false);
  const selectedRunId = selected?.run_id;
  const selectedStatus = selected?.status;

  useEffect(() => {
    document.documentElement.classList.add('intent-trial-surface');
    return () => document.documentElement.classList.remove('intent-trial-surface');
  }, []);

  function clearPending() {
    localStorage.removeItem(pendingKey);
    setPendingRequest(null);
    setFreshAvailable(false);
  }

  const showRun = useCallback((run: TrialRun) => {
    setSelected(run);
    setRuns((previous) => [run, ...previous.filter((item) => item.run_id !== run.run_id)]);
  }, []);

  const api = useCallback(
    async (path: string, body?: unknown) => {
      const reply = await fetch(`/api/intent-trial${path}`, {
        method: body === undefined ? 'GET' : 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const value = await reply.json();
      if (!reply.ok) {
        const error = new Error(value.detail?.code || value.detail?.message || t('intentTrial.failed'));
        Object.assign(error, { status: reply.status, confirmedRejection: [400, 401, 403, 422].includes(reply.status) });
        throw error;
      }
      return value;
    },
    [token, t],
  );

  async function connect() {
    setBusy(true);
    try {
      const health = await api('/readiness');
      setReadiness(health.ready ? t('intentTrial.ready') : t('intentTrial.blocked'));
      const history: TrialRun[] = await api('/runs');
      setRuns(history);
      const pending = localStorage.getItem(pendingKey);
      if (pending) {
        setPendingRequest(pending);
        const known = history.find((run) => run.client_request_id === pending);
        if (known) setSelected(known);
        try {
          showRun(await api(`/requests/${encodeURIComponent(pending)}`));
          clearPending();
        } catch (error) {
          setFreshAvailable(true);
          setMessage(`${t('intentTrial.reconcileUnavailable')} ${String(error)}`);
          return;
        }
      }
      setMessage('');
    } catch (error) {
      setMessage(String(error));
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    const pending = localStorage.getItem(pendingKey);
    if (pending) {
      await connect();
      return;
    }
    setBusy(true);
    const requestId = crypto.randomUUID();
    localStorage.setItem(pendingKey, requestId);
    setPendingRequest(requestId);
    setFreshAvailable(false);
    try {
      const run = await api('/runs', {
        original_text: text,
        client_request_id: requestId,
        options: { mode: 'web' },
        predecessor_run_id: selected?.run_id || null,
      });
      showRun(run);
      clearPending();
      setMessage('');
    } catch (error) {
      if ((error as RequestError)?.confirmedRejection) {
        clearPending();
        setMessage(`${t('intentTrial.rejected')} ${String(error)}`);
      } else {
        setMessage(`${t('intentTrial.uncertain')} ${String(error)}`);
      }
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!selectedRunId || !selectedStatus || terminal.has(selectedStatus) || !token) return;
    let mounted = true;
    const timer = window.setInterval(() => {
      void api(`/runs/${selectedRunId}`)
        .then((run) => {
          if (mounted) showRun(run);
        })
        .catch((error) => {
          if (mounted) setMessage(String(error));
        });
    }, 750);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [selectedRunId, selectedStatus, token, api, showRun]);

  async function downloadBundle() {
    if (!selected) return;
    try {
      const reply = await fetch(selected.bundle_url, { headers: { Authorization: `Bearer ${token}` } });
      if (!reply.ok) throw new Error(t('intentTrial.failed'));
      const url = URL.createObjectURL(await reply.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = `intent-${selected.run_id}.zip`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessage(String(error));
    }
  }

  return (
    <main className="intent-trial" data-testid="intent-trial-page">
      <h1 data-testid="intent-trial-title">{t('intentTrial.title')}</h1>
      <p data-testid="intent-trial-description">{t('intentTrial.description')}</p>
      <section data-testid="intent-trial-session">
        <label htmlFor="trial-session" data-testid="intent-trial-session-label">
          {t('intentTrial.session')}
        </label>
        <input
          id="trial-session"
          type="password"
          autoComplete="off"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          data-testid="intent-trial-session-input"
        />
        <button onClick={() => void connect()} disabled={busy || !token} data-testid="intent-trial-connect-button">
          {t('intentTrial.connect')}
        </button>
        <p role="status" data-testid="intent-trial-readiness">
          {readiness}
        </p>
        <button
          data-testid="intent-trial-model-login-button"
          disabled={!token || busy}
          onClick={() => {
            void api('/model/login', {})
              .then((result) => setLoginUrl(result.auth_url))
              .catch((error) => setMessage(String(error)));
          }}
        >
          {t('intentTrial.login')}
        </button>
        {loginUrl && (
          <a href={loginUrl} target="_blank" rel="noopener noreferrer" data-testid="intent-trial-model-login-link">
            {t('intentTrial.openLogin')}
          </a>
        )}
      </section>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
        data-testid="intent-trial-form"
      >
        <label htmlFor="trial-objective" data-testid="intent-trial-objective-label">
          {t('intentTrial.objective')}
        </label>
        <textarea
          id="trial-objective"
          rows={7}
          value={text}
          onChange={(event) => setText(event.target.value)}
          data-testid="intent-trial-objective-input"
        />
        <button type="submit" disabled={busy || !token || !text.trim()} data-testid="intent-trial-submit-button">
          {t(pendingRequest ? 'intentTrial.reconcile' : 'intentTrial.submit')}
        </button>
      </form>
      {pendingRequest && (
        <section data-testid="intent-trial-pending-request">
          <p data-testid="intent-trial-pending-description">{t('intentTrial.pending')}</p>
          <p data-testid="intent-trial-pending-id">{pendingRequest}</p>
          {freshAvailable && (
            <button
              disabled={busy}
              data-testid="intent-trial-fresh-button"
              onClick={() => {
                clearPending();
                setMessage(t('intentTrial.freshPrepared'));
                document.getElementById('trial-objective')?.focus();
              }}
            >
              {t('intentTrial.fresh')}
            </button>
          )}
        </section>
      )}
      {message && (
        <p role="alert" data-testid="intent-trial-error">
          {message}
        </p>
      )}
      <section data-testid="intent-trial-run-history">
        <h2 data-testid="intent-trial-history-title">{t('intentTrial.history')}</h2>
        {runs.map((run) => (
          <button
            key={run.run_id}
            data-testid="intent-trial-run-button"
            data-variant={run.run_id}
            onClick={() => setSelected(run)}
          >
            {run.run_id.slice(0, 12)} — {run.status}
          </button>
        ))}
      </section>
      {selected && (
        <section data-testid="intent-trial-result" data-variant={selected.status}>
          <h2 data-testid="intent-trial-run-status">{selected.status}</h2>
          <p data-testid="intent-trial-run-id">{selected.run_id}</p>
          {selected.mock && <p data-testid="intent-trial-mock-label">{t('intentTrial.mock')}</p>}
          {selected.decision && <p data-testid="intent-trial-reason">{selected.decision.reasons.join('; ')}</p>}
          {selected.attention?.map((attention, index) => (
            <p
              key={attention.attention_id || `${selected.run_id}-${index}`}
              data-testid="intent-trial-attention"
              data-variant={attention.attention_id || `${selected.run_id}-${index}`}
            >
              {attention.action}
            </p>
          ))}
          {selected.accepted_ref && (
            <>
              <p data-testid="intent-trial-accepted-hash">{selected.accepted_ref.sha256}</p>
              <pre data-testid="intent-trial-accepted-output">{JSON.stringify(selected.accepted_intent, null, 2)}</pre>
            </>
          )}
          {!terminal.has(selected.status) && (
            <button
              data-testid="intent-trial-cancel-button"
              onClick={() => {
                void api(`/runs/${selected.run_id}/cancel`, {})
                  .then(showRun)
                  .catch((error) => setMessage(String(error)));
              }}
            >
              {t('intentTrial.cancel')}
            </button>
          )}
          <button data-testid="intent-trial-bundle-button" onClick={() => void downloadBundle()}>
            {t('intentTrial.bundle')}
          </button>
        </section>
      )}
    </main>
  );
}
