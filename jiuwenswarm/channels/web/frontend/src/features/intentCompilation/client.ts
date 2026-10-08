import { getApiBase } from '../../utils/env';

export interface IntentRun {
  run_id: string;
  state: string;
  verdict: string | null;
  reasons: string[];
  warnings: string[];
  accepted_intent: Record<string, unknown> | null;
  accepted_reference: Record<string, unknown> | null;
  evidence: { artifacts: unknown[] };
  durable: boolean;
}

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`${getApiBase()}/api/intent${path}`, {
    method,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-Jiuwen-Intent': '1' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    cache: 'no-store',
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.code || 'INTENT_CONNECTION_FAILED');
  return payload as T;
}

export const submitIntent = (text: string, correctsRunId?: string) =>
  request<{ run_id: string; state: string }>('/runs', 'POST', {
    text,
    ...(correctsRunId ? { corrects_run_id: correctsRunId } : {}),
  });
export const inspectIntent = (runId: string) => request<IntentRun>(`/runs/${encodeURIComponent(runId)}`);
export const cancelIntent = (runId: string) => request<IntentRun>(`/runs/${encodeURIComponent(runId)}/cancel`, 'POST');
