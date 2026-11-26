import { useEffect, useState } from 'react';

type LoadResult<T> = { data?: T; error?: string };
export function useCapsuleResource<T>(key: string | undefined, load: (key: string, signal: AbortSignal) => Promise<T>, refresh?: unknown) {
  const [result, setResult] = useState<LoadResult<T> & { key?: string; attempt?: number }>({});
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (key === undefined) return;
    const controller = new AbortController();
    load(key, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setResult({ key, attempt, data });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setResult({ key, attempt, error: error instanceof Error ? error.message : String(error) });
        }
      });
    return () => controller.abort();
  }, [key, load, attempt, refresh]);

  const current = result.key === key && result.attempt === attempt ? result : {};
  return { ...current, retry: () => setAttempt((previous) => previous + 1) };
}
