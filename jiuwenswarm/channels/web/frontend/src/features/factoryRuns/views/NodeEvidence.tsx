import { useCallback, useId, useState } from 'react';
import { GitCompareArrows, Layers3 } from 'lucide-react';
import {
  factoryApi,
  type CapsuleOverview,
  type CorrectionCounts,
  type NodeCapsule,
  type NodeContract,
  type NodeOutput,
} from '../api';
import { atlasTitle } from '../cc/atlasNames';
import { capsuleHref } from '../cc/navigation';
import { Loading, MaterialDialog, MaterialList, StructuredData } from '../cc/CapsuleMaterial';
import { readableName } from '../cc/capsuleModel';
import { useCapsuleResource } from '../cc/useCapsuleResource';
import { DiffViewer } from './DiffViewer';
import { NodeChecks } from './NodeChecks';
import { CorrectionSequence, CorrectionTally } from './CorrectionSequence';
import type { CorrectionCursor } from './correctionModel';
import { SourceLinks, type EvidenceLinks } from './SourceLinks';
import type { NodeCheckView, PlanNode } from './checkModel';
import {
  capsuleCard,
  contractDiff,
  evidenceRecord,
  evidenceText,
  replayLabel,
  unassignedOutputs,
} from './nodeEvidenceModel';
import '../cc/capsules.css';
import './nodeEvidence.css';

const emptyCapsules: CapsuleOverview[] = [];
const verdictLabel = (verdict: string) => (verdict === 'unchecked' ? 'No output check' : verdict);

function displayTimestamp(value: unknown) {
  const date =
    typeof value === 'number' ? new Date(value * 1000) : typeof value === 'string' ? new Date(value) : undefined;
  return date && Number.isFinite(date.getTime()) ? date.toLocaleString() : undefined;
}

export function ReplayLabel({ value }: { value: unknown }) {
  const label = replayLabel(value);
  return label ? (
    <span className="factory-replay-label" data-testid="factory-runs-replay-origin">
      {label}
    </span>
  ) : null;
}

function RecordFields({ label, value }: { label: string; value: unknown }) {
  if (
    value == null ||
    (Array.isArray(value) && !value.length) ||
    (evidenceRecord(value) && !Object.keys(evidenceRecord(value) ?? {}).length)
  )
    return null;
  return (
    <div className="factory-node-evidence-fields" data-testid="factory-runs-node-evidence-fields" data-variant={label}>
      <h5>{label}</h5>
      <StructuredData value={value} />
    </div>
  );
}

function ExpandableFields({ label, value }: { label: string; value: unknown }) {
  const [expanded, setExpanded] = useState(false);
  if (
    value == null ||
    (Array.isArray(value) && !value.length) ||
    (evidenceRecord(value) && !Object.keys(evidenceRecord(value) ?? {}).length)
  )
    return null;
  return (
    <details className="factory-node-evidence-disclosure" onToggle={(event) => setExpanded(event.currentTarget.open)}>
      <summary data-testid="factory-runs-node-evidence-expand" data-variant={label}>
        {label}
      </summary>
      {expanded && <StructuredData value={value} />}
    </details>
  );
}

function OutputDiff({
  runId,
  nodeId,
  outputId,
  ...links
}: EvidenceLinks & { runId: string; nodeId: string; outputId: string }) {
  const load = useCallback(
    (id: string, signal: AbortSignal) => factoryApi.diff(runId, nodeId, id, signal),
    [runId, nodeId],
  );
  const diff = useCapsuleResource(outputId, load);
  if (!diff.data) return <Loading {...diff} />;
  return (
    <>
      {(diff.data.base || diff.data.head) && (
        <p className="factory-muted" data-testid="factory-runs-output-diff-range">
          {diff.data.base && (
            <>
              Base <code>{diff.data.base}</code>
            </>
          )}
          {diff.data.base && diff.data.head && ' → '}
          {diff.data.head && <code>{diff.data.head}</code>}
        </p>
      )}
      <SourceLinks {...links} source={diff.data.source ?? diff.data.path} />
      {diff.data.truncated && <p role="status">Patch preview is truncated.</p>}
      {diff.data.content ? (
        <DiffViewer content={diff.data.content} />
      ) : (
        <p className="factory-muted">The recorded revisions have no changes in these files.</p>
      )}
    </>
  );
}

function OutputEvidence({
  runId,
  nodeId,
  output,
  ...links
}: EvidenceLinks & {
  runId: string;
  nodeId: string;
  output: NodeOutput;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <li className="factory-node-evidence-output" data-testid="factory-runs-node-output" data-variant={output.id}>
      <div className="factory-node-evidence-heading">
        <strong>{output.name}</strong>
        <span className="factory-node-evidence-kind">{output.kind}</span>
        <ReplayLabel value={output.replayed_from} />
      </div>
      {output.summary != null && Object.keys(evidenceRecord(output.summary) ?? { value: true }).length > 0 && (
        <StructuredData value={output.summary} />
      )}
      <SourceLinks
        {...links}
        source={output.source}
        ids={[...(output.artifact_ids ?? []), ...(output.evidence_ids ?? [])]}
      />
      {output.kind === 'diff' && (evidenceRecord(output.summary)?.diff_artifact_id || output.artifact_ids?.length) && (
        <details
          className="factory-node-evidence-disclosure"
          onToggle={(event) => setExpanded(event.currentTarget.open)}
        >
          <summary data-testid="factory-runs-output-diff-toggle">
            <GitCompareArrows aria-hidden size={15} /> Show recorded diff
          </summary>
          {expanded && <OutputDiff {...links} runId={runId} nodeId={nodeId} outputId={output.id} />}
        </details>
      )}
    </li>
  );
}

function ContractEvidence({ contract, ...links }: { contract: NodeContract } & EvidenceLinks) {
  const [expanded, setExpanded] = useState(false);
  const { before, after, patch } = contractDiff(contract);
  return (
    <details
      className="factory-node-contract"
      data-testid="factory-runs-node-contract"
      onToggle={(event) => setExpanded(event.currentTarget.open)}
    >
      <summary data-testid="factory-runs-node-contract-toggle">
        <GitCompareArrows aria-hidden size={16} /> Node contract
      </summary>
      {expanded && (
        <>
          <RecordFields label="Planner briefing" value={contract.briefing} />
          <RecordFields label="Finalization refusals" value={contract.refusals} />
          <RecordFields label="Scheduler model and briefing sections" value={contract.scheduler} />
          <RecordFields label="Scheduler rationale" value={contract.rationale} />
          <SourceLinks {...links} source={[contract.source, contract.final_source]} />
          {(before || after) && (
            <section className="factory-node-evidence-fields">
              <h5>Preliminary and final contract</h5>
              {patch ? (
                <DiffViewer content={patch} />
              ) : (
                <p className="factory-muted">
                  {before && after
                    ? 'The recorded contracts are identical.'
                    : after
                      ? 'Only the final contract is recorded.'
                      : 'Final contract pending.'}
                </p>
              )}
              <details className="factory-node-evidence-disclosure">
                <summary data-testid="factory-runs-node-contract-json-toggle">Recorded JSON</summary>
                {before && <pre aria-label="Preliminary contract">{before}</pre>}
                {after && before !== after && <pre aria-label="Final contract">{after}</pre>}
              </details>
            </section>
          )}
        </>
      )}
    </details>
  );
}

function CapsuleMaterials({ capsule, runId, nodeId }: { capsule: NodeCapsule; runId: string; nodeId: string }) {
  const [path, setPath] = useState<string>();
  const [expanded, setExpanded] = useState(false);
  const files = capsule.files ?? [];
  const material = Object.entries({ ...capsule.materials, ...capsule.sections });
  const loadSealed = useCallback(
    (relative: string, signal: AbortSignal) => factoryApi.material(runId, nodeId, capsule.id, relative, signal),
    [runId, nodeId, capsule.id],
  );
  if (!material.length && !files.length) return null;
  return (
    <details className="factory-node-evidence-disclosure" onToggle={(event) => setExpanded(event.currentTarget.open)}>
      <summary data-testid="factory-runs-node-capsule-materials">Method, reference code and helpers</summary>
      {(capsule.material_version || capsule.material_digest) && (
        <p className="factory-muted">
          {capsule.material_version} {capsule.material_digest && <code>{capsule.material_digest}</code>}
        </p>
      )}
      {material.length > 0 && (
        <ul className="factory-node-evidence-sources">
          {material.map(([label, relative]) => (
            <li key={label}>
              {files.some((file) => file.path === relative && file.integrity !== 'missing') ? (
                <button
                  className="factory-graph-file-link"
                  type="button"
                  onClick={() => setPath(relative)}
                  data-testid="factory-runs-node-material-open"
                  data-variant={label}
                >
                  {readableName(label)}
                </button>
              ) : (
                <span>
                  {readableName(label)} · <code>{relative}</code>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {expanded && files.length > 0 && <MaterialList files={files} onOpen={setPath} />}
      {path && (
        <MaterialDialog
          key={path}
          name={capsule.catalog_name ?? capsule.id}
          path={path}
          available={new Set(files.map((file) => file.path))}
          onOpen={setPath}
          onClose={() => setPath(undefined)}
          loadFile={capsule.material_source === 'sealed' ? loadSealed : undefined}
        />
      )}
    </details>
  );
}

function comparisonBody(value: unknown) {
  const row = evidenceRecord(value);
  return row
    ? Object.fromEntries(Object.entries(row).filter(([field]) => !['source', 'sources', 'citation'].includes(field)))
    : value;
}

function CappedRuns({ runs, ...links }: EvidenceLinks & { runs?: NodeCapsule['runs'] }) {
  if (!runs?.length) return null;
  return (
    <section className="factory-node-evidence-fields" data-testid="factory-runs-node-capsule-capped-runs">
      <h5>Capped runs</h5>
      {runs.map((run, index) => {
        const id = evidenceText(run.attempt_id ?? run.id);
        const title = [evidenceText(run.recipe ?? run.kind), evidenceText(run.state ?? run.outcome)]
          .filter(Boolean)
          .join(' · ');
        const details = Object.fromEntries(
          Object.entries(run).filter(
            ([name]) => !['replayed_from', 'replay_source', 'source', 'artifact_ids'].includes(name),
          ),
        );
        return (
          <div
            key={id ?? index}
            className="factory-node-capped-run"
            data-testid="factory-runs-node-capped-run"
            data-variant={id}
          >
            <p>{title}</p>
            <ReplayLabel value={run.replayed_from} />
            <SourceLinks
              {...links}
              source={run.source ?? run}
              ids={
                Array.isArray(run.artifact_ids)
                  ? run.artifact_ids.filter((id): id is string => typeof id === 'string')
                  : []
              }
            />
            <ExpandableFields label="Run receipt" value={details} />
          </div>
        );
      })}
    </section>
  );
}

export function NodeEvidence({
  runId,
  nodeId,
  node,
  checks,
  revision,
  correctionCursor,
  r8VerifierHelp,
  onClose,
  ...links
}: EvidenceLinks & {
  runId: string;
  nodeId: string;
  node?: PlanNode;
  checks?: NodeCheckView;
  revision: unknown;
  correctionCursor?: CorrectionCursor;
  r8VerifierHelp?: boolean;
  onClose?: () => void;
}) {
  const heading = useId();
  const load = useCallback((id: string, signal: AbortSignal) => factoryApi.node(runId, id, signal), [runId]);
  const evidence = useCapsuleResource(nodeId, load, revision);
  const assignedRuns = new Set(
    evidence.data?.capsules.flatMap((card) => (card.runs ?? []).map((run) => run.attempt_id)) ?? [],
  );
  const otherRuns = evidence.data?.runs?.filter((run) => !assignedRuns.has(run.attempt_id));
  const unassigned = evidence.data ? unassignedOutputs(evidence.data.outputs ?? [], evidence.data.capsules) : [];
  return (
    <section
      className="factory-node-evidence"
      aria-labelledby={heading}
      data-testid="factory-runs-node-evidence"
      data-variant={nodeId}
    >
      <header className="factory-node-evidence-header">
        <div>
          <small>Node evidence</small>
          <h3 id={heading}>{nodeId}</h3>
        </div>
        {onClose && (
          <button
            type="button"
            className="factory-node-evidence-button"
            onClick={onClose}
            data-testid="factory-runs-node-evidence-close"
          >
            Close
          </button>
        )}
      </header>
      {!evidence.data ? (
        <Loading {...evidence} />
      ) : (
        <>
          {evidence.data.contract && <ContractEvidence {...links} contract={evidence.data.contract} />}
          <div className="factory-node-evidence-cards" data-testid="factory-runs-node-capsules">
            {!evidence.data.capsules.length && (
              <p className="factory-muted">No capsule bindings are recorded for this node.</p>
            )}
            {evidence.data.capsules.map((capsule) => {
              const card = capsuleCard(capsule, checks);
              const comparison = evidenceRecord(card.comparison);
              return (
                <article
                  className="factory-node-capsule"
                  key={card.id}
                  data-testid="factory-runs-node-capsule-card"
                  data-variant={card.id}
                >
                  <header className="factory-node-capsule-header">
                    <div className="factory-node-evidence-heading">
                      <h4>
                        <a
                          data-testid="factory-runs-node-capsule-catalog"
                          href={capsuleHref(card.catalog_name ?? card.id)}
                        >
                          {card.title}
                        </a>
                      </h4>
                      {card.kind && <span className="factory-node-evidence-kind">{card.kind}</span>}
                      {card.verdict && (
                        <span className="factory-node-verdict" data-verdict={card.verdict}>
                          {card.verdict}
                        </span>
                      )}
                    </div>
                    <p className="factory-muted">
                      <code>{card.id}</code>
                      {card.version && <> · {card.version}</>}
                    </p>
                    {card.purpose && card.purpose !== card.title && <p>{card.purpose}</p>}
                  </header>
                  <CapsuleMaterials capsule={card} runId={runId} nodeId={nodeId} />
                  {card.calls && (
                    <section className="factory-node-evidence-fields" data-testid="factory-runs-node-capsule-calls">
                      <h5>Worker calls</h5>
                      <p>
                        {card.calls.count} recorded · {card.failures} failed
                      </p>
                      {card.calls.first != null && (
                        <p>First {displayTimestamp(card.calls.first) || evidenceText(card.calls.first)}</p>
                      )}
                      {card.calls.last != null && (
                        <p>Last {displayTimestamp(card.calls.last) || evidenceText(card.calls.last)}</p>
                      )}
                      <ExpandableFields label="Call records" value={card.calls.records} />
                    </section>
                  )}
                  <CappedRuns {...links} runs={card.runs} />
                  {!!card.outputs?.length && (
                    <ul className="factory-node-evidence-outputs" data-testid="factory-runs-node-capsule-outputs">
                      {card.outputs.map((output) => (
                        <OutputEvidence {...links} key={output.id} runId={runId} nodeId={nodeId} output={output} />
                      ))}
                    </ul>
                  )}
                  {card.checkView && (
                    <NodeChecks view={card.checkView} node={node ?? { node_id: nodeId }} {...links} outputOnly />
                  )}
                  {card.comparison != null && (
                    <section className="factory-node-comparison" data-testid="factory-runs-node-stock-comparison">
                      <h5>Stock vs changed</h5>
                      {comparison?.text ? (
                        <p>{evidenceText(comparison.text)}</p>
                      ) : (
                        <StructuredData value={comparisonBody(card.comparison)} />
                      )}
                      <SourceLinks
                        {...links}
                        source={comparison?.source ?? comparison?.sources ?? comparison?.citation}
                      />
                    </section>
                  )}
                  {card.comparison == null && card.evidence_fact && (
                    <section className="factory-node-comparison" data-testid="factory-runs-node-capsule-fact">
                      <h5>Recorded evidence</h5>
                      <p>{card.evidence_fact.text}</p>
                      <SourceLinks {...links} source={card.evidence_fact.source} />
                    </section>
                  )}
                </article>
              );
            })}
          </div>
          {evidence.data.corrections && (
            <CorrectionSequence {...links} corrections={evidence.data.corrections} cursor={correctionCursor} r8VerifierHelp={r8VerifierHelp} />
          )}
          <CappedRuns {...links} runs={otherRuns} />
          {unassigned.length > 0 && (
            <section className="factory-node-evidence-fields">
              <h5>Other node outputs</h5>
              <ul className="factory-node-evidence-outputs">
                {unassigned.map((output) => (
                  <OutputEvidence {...links} key={output.id} runId={runId} nodeId={nodeId} output={output} />
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </section>
  );
}

export function CapsuleOverviewStrip({
  nodes,
  labels,
  replayByNode,
  corrections,
  selected,
  onSelect,
}: {
  nodes?: Record<string, CapsuleOverview[]>;
  labels: Map<string, string>;
  replayByNode?: Map<string, unknown[]>;
  corrections?: Record<string, CorrectionCounts>;
  selected?: string;
  onSelect: (id: string) => void;
}) {
  const all = [...new Set([...labels.keys(), ...Object.keys(nodes ?? {})])];
  if (!nodes || !all.length) return null;
  return (
    <section className="factory-cc-overview" data-testid="factory-runs-cc-overview">
      <h3>
        <Layers3 aria-hidden size={17} /> Capsules by node
      </h3>
      <ul>
        {all.map((id) => {
          const capsules = nodes[id] ?? emptyCapsules;
          return (
            <li key={id} data-testid="factory-runs-cc-overview-node" data-variant={id}>
              <button
                type="button"
                aria-pressed={selected === id}
                className="factory-node-evidence-button"
                data-testid="factory-runs-cc-overview-select"
                title={labels.get(id)}
                onClick={() => onSelect(id)}
              >
                {readableName(id)}
              </button>
              {corrections?.[id] && <CorrectionTally counts={corrections[id]} />}
              <ReplayLabel value={replayByNode?.get(id)} />
              {capsules.map((capsule) => (
                <span
                  className="factory-cc-overview-chip"
                  key={capsule.id}
                  title={capsule.id}
                  data-testid="factory-runs-cc-overview-chip"
                  data-variant={capsule.id}
                >
                  {capsule.title ?? atlasTitle(capsule.id) ?? capsule.id}
                  {capsule.verdict && (
                    <small className="factory-node-verdict" data-verdict={capsule.verdict}>
                      {verdictLabel(capsule.verdict)}
                    </small>
                  )}
                </span>
              ))}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
