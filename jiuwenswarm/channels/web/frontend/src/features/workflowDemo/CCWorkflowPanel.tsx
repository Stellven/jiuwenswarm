import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { edgePath, layoutGraph } from './graphLayout';
import './cc-workflow.css';

interface CCNode {
  id: string;
  capability: string;
  state: string;
  inputs: Record<string, { node?: string; port?: string; value?: unknown }>;
  outputs: Record<string, unknown>;
  receipts: unknown[];
  lab: unknown;
}
interface CCRun {
  id: string;
  task_id: string;
  objective: string;
  status: string;
  revision: number;
  sequence: number;
  nodes: CCNode[];
  revisions: unknown[];
}
interface CCEvent {
  sequence: number;
  type: string;
  node_id?: string;
  nodes?: CCNode[];
  state?: string;
  receipt?: unknown;
  lab?: unknown;
  outputs?: Record<string, unknown>;
  node_states?: Record<string, string>;
}
interface Catalog {
  task_id: string;
  workflows: { id: string; name: string; inputs: Record<string, string> }[];
}
async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1/cc-workflows${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const value = await response.json();
  if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : JSON.stringify(value));
  return value;
}

export function CCWorkflowPanel() {
  const { t } = useTranslation();
  const label = (key: string) => t(`ccWorkflow.${key}`);
  const [catalog, setCatalog] = useState<Catalog>();
  const [workflow, setWorkflow] = useState('');
  const [objective, setObjective] = useState('');
  const [inputs, setInputs] = useState('{}');
  const [runId, setRunId] = useState('');
  const [run, setRun] = useState<CCRun>();
  const [events, setEvents] = useState<CCEvent[]>([]);
  const [cursor, setCursor] = useState<number | null>(null);
  const [selected, setSelected] = useState('');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    request<Catalog>('/catalog')
      .then(setCatalog)
      .catch((e) => setError(String(e)));
  }, []);
  const update = async (value: CCRun) => {
    setRun(value);
    setRunId(value.id);
    setEvents(await request<CCEvent[]>(`/runs/${encodeURIComponent(value.id)}/events`));
  };
  useEffect(() => {
    if (!running || !run) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const advance = async () => {
      try {
        const value = await request<CCRun>(`/runs/${encodeURIComponent(run.id)}/tick`, {});
        if (disposed) return;
        await update(value);
        if (['completed', 'failed', 'cancelled', 'needs_reconciliation'].includes(value.status)) setRunning(false);
        else timer = setTimeout(advance, 1000);
      } catch (e) {
        setError(String(e));
        setRunning(false);
      }
    };
    void advance();
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
    // One bounded advance loop per explicitly started run, not per snapshot.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, run?.id]);
  const nodes = useMemo(() => {
    if (cursor === null) return run?.nodes ?? [];
    const replay = new Map<string, CCNode>();
    for (const event of events.filter((item) => item.sequence <= cursor)) {
      for (const node of event.nodes ?? []) replay.set(node.id, { ...node, receipts: [...node.receipts] });
      const node = event.node_id ? replay.get(event.node_id) : undefined;
      if (node && event.type === 'cc.intent') node.state = 'calling';
      if (node && event.type === 'cc.transport_error') node.state = 'unknown';
      for (const [id, state] of Object.entries(event.node_states ?? {})) {
        const current = replay.get(id);
        if (current) current.state = state;
      }
      if (node && event.type === 'cc.receipt') {
        node.state = event.state ?? node.state;
        node.outputs = event.outputs ?? node.outputs;
        node.lab = event.lab;
        node.receipts.push(event.receipt);
      }
    }
    return [...replay.values()];
  }, [run, events, cursor]);
  const edges = nodes.flatMap((node) =>
    Object.entries(node.inputs).flatMap(([name, value]) =>
      value.node ? [{ from: value.node, to: node.id, data: name }] : [],
    ),
  );
  const { positions } = layoutGraph(nodes, edges);
  const height = Math.max(160, Math.ceil(nodes.length / 2) * 150);
  const detail = nodes.find((node) => node.id === selected);
  const act = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError('');
    try {
      await fn();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="cc-workflow" data-testid="workflow-demo-cc-panel">
      <h2>{label('title')}</h2>
      <p>{label('ownership')}</p>
      {error && (
        <p role="alert" data-testid="workflow-demo-cc-error">
          {error}
        </p>
      )}
      <label>
        {label('objective')}
        <input
          data-testid="workflow-demo-cc-objective"
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
        />
      </label>
      <label>
        {label('workflow')}
        <select data-testid="workflow-demo-cc-selection" value={workflow} onChange={(e) => setWorkflow(e.target.value)}>
          <option value="">{label('choose')}</option>
          {catalog?.workflows.map((flow) => (
            <option data-testid="workflow-demo-cc-option" data-variant={flow.id} key={flow.id} value={flow.id}>
              {flow.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        {label('inputs')}
        <textarea data-testid="workflow-demo-cc-inputs" value={inputs} onChange={(e) => setInputs(e.target.value)} />
      </label>
      <button
        data-testid="workflow-demo-cc-create"
        disabled={busy || running || !workflow || !objective.trim()}
        onClick={() =>
          void act(async () => {
            await update(await request<CCRun>('/runs', { workflow, objective, inputs: JSON.parse(inputs) }));
            setCursor(null);
          })
        }
      >
        {label('create')}
      </button>
      <label>
        {label('runId')}
        <input data-testid="workflow-demo-cc-run-id" value={runId} onChange={(e) => setRunId(e.target.value)} />
      </label>
      <button
        data-testid="workflow-demo-cc-load"
        disabled={busy || running || !runId}
        onClick={() =>
          void act(async () => {
            await update(await request<CCRun>(`/runs/${encodeURIComponent(runId)}`));
            setCursor(null);
          })
        }
      >
        {label('load')}
      </button>
      {run && (
        <>
          <p data-testid="workflow-demo-cc-status">
            {run.status} · {label('revision')} {run.revision} · {run.task_id}
          </p>
          <p>{label('acceptance')}</p>
          <button
            data-testid="workflow-demo-cc-advance"
            disabled={running || busy || cursor !== null}
            onClick={() => setRunning(true)}
          >
            {label('advance')}
          </button>
          <button
            data-testid="workflow-demo-cc-stop"
            disabled={busy || cursor !== null}
            onClick={() =>
              void act(async () => {
                await update(await request<CCRun>(`/runs/${encodeURIComponent(run.id)}/stop`, {}));
                setRunning(true);
              })
            }
          >
            {label('stop')}
          </button>
          <label>
            {label('replay')}
            <input
              data-testid="workflow-demo-cc-replay"
              aria-label={label('replay')}
              type="range"
              min={0}
              max={run.sequence}
              value={cursor ?? run.sequence}
              onChange={(e) => setCursor(Number(e.target.value))}
            />
          </label>
          <button data-testid="workflow-demo-cc-live" onClick={() => setCursor(null)}>
            {label('live')}
          </button>
          <div className="cc-workflow-graph-scroll">
            <svg
              data-testid="workflow-demo-cc-graph"
              viewBox={`0 0 800 ${height}`}
              role="img"
              aria-label={label('graph')}
            >
              {edges.map(
                (edge, index) =>
                  positions[edge.from] &&
                  positions[edge.to] && (
                    <path
                      key={index}
                      d={edgePath(positions[edge.from], positions[edge.to]).d}
                      fill="none"
                      stroke="currentColor"
                    />
                  ),
              )}
              {nodes.map((node) => (
                <g
                  data-testid="workflow-demo-cc-node"
                  data-variant={node.id}
                  key={node.id}
                  role="button"
                  tabIndex={0}
                  aria-label={node.capability}
                  onClick={() => setSelected(node.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') setSelected(node.id);
                  }}
                  transform={`translate(${positions[node.id].x},${positions[node.id].y})`}
                >
                  <rect x={-128} y={-34} width={256} height={68} rx={8} />
                  <text textAnchor="middle" y={-4}>
                    {node.capability}
                  </text>
                  <text textAnchor="middle" y={20}>
                    {node.state}
                  </text>
                </g>
              ))}
            </svg>
          </div>
          {detail && (
            <>
              <pre data-testid="workflow-demo-cc-evidence">
                {JSON.stringify(
                  { state: detail.state, inputs: detail.inputs, outputs: detail.outputs, lab: detail.lab },
                  null,
                  2,
                )}
              </pre>
              <details data-testid="workflow-demo-cc-receipts">
                <summary>{label('receipts')}</summary>
                <pre>{JSON.stringify(detail.receipts, null, 2)}</pre>
              </details>
            </>
          )}
          <details data-testid="workflow-demo-cc-revisions">
            <summary>{label('decisions')}</summary>
            <pre>{JSON.stringify(run.revisions, null, 2)}</pre>
          </details>
        </>
      )}
    </section>
  );
}
