import { useCallback, useEffect, useRef, useState } from 'react';
import { cancelIntent, inspectIntent, submitIntent, type IntentRun } from './client';

const LAST_RUN = 'ai4r.intent.lastRun';
const terminal = (state: string) => ['ACCEPTED', 'HALTED', 'PAUSED'].includes(state);

export function useIntentCompilation(enabled: boolean) {
  const [run, setRun] = useState<IntentRun | null>(null);
  const [runId, setRunId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(LAST_RUN);
    } catch {
      return null;
    }
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const submitting = useRef(false);
  const correction = useRef<string | undefined>();

  useEffect(() => {
    if (!enabled || !runId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const observed = await inspectIntent(runId);
        if (stopped) return;
        setRun(observed);
        setBusy(!terminal(observed.state));
        setError('');
        if (!terminal(observed.state)) timer = setTimeout(poll, 500);
      } catch (reason) {
        if (stopped) return;
        setError(reason instanceof Error ? reason.message : 'INTENT_CONNECTION_FAILED');
        // Polling has no effects. Disconnect never cancels or resubmits work.
        timer = setTimeout(poll, 2000);
      }
    };
    void poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [enabled, runId]);

  const submit = useCallback(
    async (text: string) => {
      if (submitting.current || busy) return;
      submitting.current = true;
      setBusy(true);
      setError('');
      try {
        const submitted = await submitIntent(text, correction.current);
        correction.current = undefined;
        setRun(null);
        setRunId(submitted.run_id);
        try {
          localStorage.setItem(LAST_RUN, submitted.run_id);
        } catch {
          /* Inspection still works in memory. */
        }
      } catch (reason) {
        setBusy(false);
        setError(reason instanceof Error ? reason.message : 'INTENT_CONNECTION_FAILED');
      } finally {
        submitting.current = false;
      }
    },
    [busy],
  );

  const cancel = useCallback(async () => {
    if (!runId) return;
    try {
      setRun(await cancelIntent(runId));
      setBusy(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'INTENT_CONNECTION_FAILED');
    }
  }, [runId]);

  const prepareCorrection = useCallback(() => {
    correction.current = runId || undefined;
  }, [runId]);

  return { run, runId, busy, error, submit, cancel, prepareCorrection };
}
