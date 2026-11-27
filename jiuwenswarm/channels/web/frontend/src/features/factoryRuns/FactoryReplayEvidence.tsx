import { useCallback, useMemo, useState } from 'react';
import { factoryApi, type EvidenceFile, type JsonRecord, type RunDetail } from './api';
import { Loading } from './cc/CapsuleMaterial';
import { useCapsuleResource } from './cc/useCapsuleResource';
import { DataViewer } from './views/DataViewer';
import { ContractEvidence } from './views/NodeEvidence';
import { evidenceRecord, evidenceText } from './views/nodeEvidenceModel';
import type { CuratedReplay } from './views/storyModel';
import './factoryReplayEvidence.css';

type ContractVersion = {
  version: number;
  path: string;
  sha256: string;
  amendment?: string;
  reason?: string;
};

export function ReplayContractPanel({ detail, onOpenFile }: {
  detail: RunDetail;
  onOpenFile: (file: EvidenceFile) => void;
}) {
  const versions = (detail.curated as (CuratedReplay & { contract_versions?: ContractVersion[] }) | undefined)
    ?.contract_versions ?? [];
  const [activePath, setActivePath] = useState<string>();
  const active = versions.find((version) => version.path === activePath)
    ?? versions.find((version) => version.version === detail.contract.version)
    ?? versions.at(-1);
  const loadVersion = useCallback(async (path: string, signal: AbortSignal) => {
    const file = await factoryApi.file(detail.run.id, path, signal);
    if (file.truncated || file.integrity === 'mismatch' || file.sha256 !== active?.sha256) {
      throw new Error('The contract file does not match the recorded SHA-256.');
    }
    return file;
  }, [active?.sha256, detail.run.id]);
  const document = useCapsuleResource(active?.path, loadVersion);
  const raw = detail.files.find((file) => active
    ? file.path === active.path
    : file.path.split('/').at(-1) === String(detail.contract.contract_id) + '.json');
  return (
    <section className="factory-replay-evidence" data-testid="factory-runs-replay-contract">
      {versions.length > 0 && (
        <div className="factory-replay-evidence-controls" data-testid="factory-runs-contract-versions">
          {versions.map((version) => (
            <button
              key={version.path}
              type="button"
              className="factory-node-evidence-button"
              aria-pressed={version.path === active?.path}
              data-testid="factory-runs-contract-version"
              data-variant={version.version}
              onClick={() => setActivePath(version.path)}
            >
              Revision {version.version}{version.amendment && ' · ' + version.amendment}
            </button>
          ))}
        </div>
      )}
      {active?.reason && (
        <p data-testid="factory-runs-contract-amendment-reason">{active.reason}</p>
      )}
      {raw && (
        <button
          type="button"
          className="factory-node-evidence-button"
          data-testid="factory-runs-contract-open-file"
          onClick={() => onOpenFile(raw)}
        >
          Open raw contract
        </button>
      )}
      {active ? (
        document.data ? (
          <DataViewer
            key={active.path}
            name={active.path}
            file={document.data}
            source={document.data.content}
            initialMode="readable"
          />
        ) : <Loading {...document} />
      ) : (
        <DataViewer name={String(detail.contract.contract_id ?? 'Contract')} value={detail.contract} initialMode="readable" />
      )}
    </section>
  );
}

function recordedNodes(detail: RunDetail) {
  const rows = Array.isArray(detail.graph.nodes)
    ? detail.graph.nodes
    : Object.values(evidenceRecord(detail.graph.nodes) ?? {});
  const titles = new Map<string, string>();
  for (const row of rows) {
    const node = evidenceRecord(row);
    const id = evidenceText(node?.node_id);
    if (id) titles.set(id, evidenceText(node?.title) ?? id);
  }
  for (const id of Object.keys(detail.node_checks ?? {})) {
    if (!titles.has(id)) titles.set(id, id);
  }
  return [...titles];
}

export function ReplayNodeContractsPanel({ detail, selectedNode, onSelectNode, onOpenFile }: {
  detail: RunDetail;
  selectedNode?: string;
  onSelectNode?: (id: string) => void;
  onOpenFile?: (path: string) => void;
}) {
  const nodes = recordedNodes(detail);
  const [chosenNode, setChosenNode] = useState<string>();
  const selection = onSelectNode ? selectedNode : chosenNode ?? selectedNode;
  const node = nodes.find(([id]) => id === selection)?.[0] ?? nodes[0]?.[0];
  const loadNode = useCallback((id: string, signal: AbortSignal) => factoryApi.node(detail.run.id, id, signal),
    [detail.run.id]);
  const loaded = useCapsuleResource(node, loadNode);
  return (
    <section className="factory-replay-evidence" data-testid="factory-runs-replay-node-contracts">
      {node ? (
        <>
          <label className="factory-replay-evidence-controls">
            Node
            <select
              value={node}
              data-testid="factory-runs-node-contract-selector"
              onChange={(event) => {
                setChosenNode(event.target.value);
                onSelectNode?.(event.target.value);
              }}
            >
              {nodes.map(([id, title]) => <option value={id} key={id}>{detail.curated?.node_presentation?.[id]?.title ?? title}</option>)}
            </select>
          </label>
          {!loaded.data ? <Loading {...loaded} /> : (
            loaded.data.contract?.preliminary || loaded.data.contract?.final ? (
              <ContractEvidence key={node} contract={loaded.data.contract} files={detail.files} onOpenFile={onOpenFile} initiallyOpen />
            ) : <p className="factory-muted">No node contract is recorded for this node.</p>
          )}
        </>
      ) : <p className="factory-muted">No nodes are recorded for this run.</p>}
    </section>
  );
}

type RecordedEvent = { id: string; kind: string; summary: string; time?: number; raw: JsonRecord };

function timestamp(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) return value < 1e12 ? value * 1000 : value;
  if (typeof value === 'string' && Number.isFinite(Date.parse(value))) return Date.parse(value);
  return undefined;
}

function recordedEvents(detail: RunDetail): RecordedEvent[] {
  const events: RecordedEvent[] = [];
  const tables = [
    ['tasks', 'Task'],
    ['decisions', 'Decision'],
    ['observations', 'Observation'],
    ['attempts', 'Attempt'],
    ['evaluations', 'Evaluation'],
    ['uploads', 'Upload'],
  ] as const;
  for (const [table, category] of tables) {
    const rows = detail.records[table] ?? [];
    for (const [index, row] of rows.entries()) {
      const values = evidenceRecord(row.values);
      const id = evidenceText(row.obs_id ?? row.decision_id ?? row.attempt_id ?? row.eval_id ?? row.task_id);
      const kind = evidenceText(row.kind ?? row.action) ?? category;
      const actor = kind === 'node_check'
        ? 'Node verifier'
        : kind === 'node_contract_final' || kind === 'node_contract_refusal'
          ? 'Scheduler proposal'
          : undefined;
      const summary = [
        actor,
        evidenceText(values?.node_id ?? row.node_id ?? evidenceRecord(row.request)?.node_id),
        evidenceText(row.summary ?? row.reason_for_change ?? values?.summary ?? values?.rationale
          ?? values?.reason ?? values?.outcome ?? row.objective ?? row.state),
      ].filter(Boolean).join(' · ');
      events.push({
        id: table + '-' + (id ?? index) + '-' + index,
        kind,
        summary: summary || id || category,
        time: timestamp(row.created ?? row.started ?? row.ended),
        raw: row,
      });
    }
  }
  if (!events.length && !detail.curated) {
    events.push(...detail.events.map((row) => ({
      id: row.id,
      kind: row.kind,
      summary: row.summary,
      time: timestamp(row.created),
      raw: row,
    })));
  }
  return events.sort((a, b) => (a.time ?? Infinity) - (b.time ?? Infinity));
}

function EventRow({ row, initiallyOpen }: { row: RecordedEvent; initiallyOpen: boolean }) {
  const [open, setOpen] = useState(initiallyOpen);
  return (
    <li data-testid="factory-runs-recorded-event" data-variant={row.id}>
      <details open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
        <summary data-testid="factory-runs-recorded-event-toggle">
          {row.time !== undefined && <time dateTime={new Date(row.time).toISOString()}>{new Date(row.time).toISOString().replace('T', ' ').replace('Z', ' UTC')}</time>}
          <code>{row.kind}</code>
          <span>{row.summary}</span>
        </summary>
        {open && <DataViewer name={row.kind} value={row.raw} initialMode="raw" />}
      </details>
    </li>
  );
}

export function ReplayEventsPanel({ detail, recordId }: { detail: RunDetail; recordId?: string }) {
  const events = useMemo(() => recordedEvents(detail), [detail]);
  const [kind, setKind] = useState('');
  const [query, setQuery] = useState(recordId ?? '');
  const [visible, setVisible] = useState(50);
  const search = query.trim().toLowerCase();
  const kinds = [...new Set(events.map((event) => event.kind))].sort();
  const filtered = events.filter((event) => (!kind || event.kind === kind)
    && (query && query === recordId ? event.raw.obs_id === recordId : !search || (event.kind + ' ' + event.summary + ' ' + event.id).toLowerCase().includes(search)));
  return (
    <section className="factory-replay-evidence" data-testid="factory-runs-replay-events">
      <div className="factory-replay-evidence-controls">
        <label>
          Event type
          <select data-testid="factory-runs-event-type-filter" value={kind} onChange={(event) => {
            setKind(event.target.value);
            setVisible(50);
          }}>
            <option value="">All event types</option>
            {kinds.map((type) => <option value={type} key={type}>{type}</option>)}
          </select>
        </label>
        <label>
          Search events
          <input type="search" data-testid="factory-runs-event-search" value={query} onChange={(event) => {
            setQuery(event.target.value);
            setVisible(50);
          }} />
        </label>
      </div>
      <p className="factory-muted" data-testid="factory-runs-event-count">
        Showing {Math.min(visible, filtered.length)} of {filtered.length} recorded events
      </p>
      {filtered.length ? (
        <ol className="factory-replay-event-list" data-testid="factory-runs-recorded-events">
          {filtered.slice(0, visible).map((row) => <EventRow key={row.id} row={row} initiallyOpen={Boolean(recordId && row.raw.obs_id === recordId)} />)}
        </ol>
      ) : <p className="factory-muted">No recorded events match these filters.</p>}
      {visible < filtered.length && (
        <button
          type="button"
          className="factory-node-evidence-button"
          onClick={() => setVisible((count) => count + 50)}
          data-testid="factory-runs-events-show-more"
        >
          Show more events
        </button>
      )}
    </section>
  );
}
