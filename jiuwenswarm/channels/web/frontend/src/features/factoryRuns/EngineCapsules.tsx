import { useCallback, useState } from 'react';
import { factoryApi, type CapsuleOverview, type JsonRecord, type RunDetail } from './api';
import { atlasName } from './cc/atlasNames';
import { capsuleHref, nodeHref, runHref } from './cc/navigation';
import { capsuleStage, demoCapsuleIds, inferenceCapsules, prefixReuseId } from './cc/inferenceCapsuleCopy';
import { PrefixReuseEvidence } from './cc/PrefixReuseEvidence';
import { useCapsuleResource } from './cc/useCapsuleResource';

type NodeBinding = { detail: RunDetail; node: string };
type Binding = CapsuleOverview & { nodes: NodeBinding[] };

const loadDemos = async () => {
  const { runs } = await factoryApi.list();
  const featured = runs.filter((run) => run.demo).sort((a, b) => (a.demo_order ?? 0) - (b.demo_order ?? 0));
  return Promise.all((featured.length ? featured : runs.filter((run) => run.featured)).map(({ id }) => factoryApi.detail(id)));
};

const nodeTitles: Record<string, string> = {
  pin_inputs: 'Pin build inputs',
  ingest_nvfp4: 'Prepare weight format',
  wire_expert_scales: 'Wire scales for quantized experts',
  build_base_engine: 'Compile and smoke-test the base engine',
  requant_2bit: 'Build and verify the weight pack',
  size_prefill_batch: 'Size prefill to the device budget',
  plan_prefix_store: 'Plan the prompt cache configuration',
  build_image: 'Build and verify the image',
  deliver_to_lab: 'Seal the lab request',
  measure_engine: 'Evaluate the delivered engine on the target',
  release_gate: 'Check factory and runtime evidence for release',
};

function runLabel(detail: RunDetail) {
  return typeof detail.run.demo_order === 'number' ? `Run ${detail.run.demo_order}` : 'Recorded run';
}

function checkMethod(output: string) {
  if (output === 'image' || output === 'base_engine' || output === 'factory_stage') return 'Checks the artifact identity and approved build settings.';
  if (output === 'measurements') return 'Applies the delivered test requirements for speed, reuse and accuracy on the target.';
  if (output === 'smoke') return 'Checks a real-model response on the target.';
  if (output === 'batch_plan') return 'Checks the proposed batch sizes and device budget against measurement evidence.';
  if (output === 'lab_package' || output === 'lab_request') return 'Checks that the sealed package carries the build and lab contract.';
  if (output === 'release') return 'Checks that factory and runtime evidence jointly satisfy the release rule.';
  return 'Checks the output against its sealed contract.';
}

function CapsuleNode({ detail, node, capsule }: NodeBinding & { capsule: string }) {
  const [open, setOpen] = useState(false);
  const run = detail.run.id;
  const load = useCallback((id: string, signal: AbortSignal) => factoryApi.node(run, id, signal), [run]);
  const nodeDetails = useCapsuleResource(open ? node : undefined, load);
  const row = nodeDetails.data?.capsules.find((item) => item.id === capsule);

  return (
    <details data-testid="factory-runs-engine-capsule-node" data-variant={node} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary data-testid="factory-runs-engine-capsule-node-title">{nodeTitles[node] ?? node.replaceAll('_', ' ')} · {runLabel(detail)}</summary>
      {open && !nodeDetails.data && !nodeDetails.error && <p role="status">Loading node evidence…</p>}
      {nodeDetails.error && <p role="alert">{nodeDetails.error}</p>}
      {row && (
        <>
          <ul aria-label="Checks">
            {row.checks?.map((check) => (
              <li key={check.name} data-testid="factory-runs-engine-verifier" data-variant={check.name}>
                <strong>{capsuleStage(check.name, node)} · {node === 'measure_engine' ? 'Lab acceptance' : 'Node verifier'} · {check.name.replaceAll('_', ' ')}</strong>
                <p>{checkMethod(check.name)}</p>
                <small>In this run: {check.checks.some((result) => result.passed && !result.superseded) ? 'passed' : 'see check record'}</small>
              </li>
            ))}
            {!row.checks?.length && <li>This binding has no dedicated check record.</li>}
          </ul>
          <ul aria-label="Outputs">
            {row.outputs?.map((output) => (
              <li key={output.id} data-testid="factory-runs-engine-output" data-variant={output.id}>
                {output.name.replaceAll('_', ' ')} · {output.kind}
                {detail.files.filter((file) => file.artifact_ids?.some((id) => output.artifact_ids?.includes(id))).map((file) => (
                  <div key={file.path}>
                    <a href={runHref(run, file.path)} data-testid="factory-runs-engine-output-file" data-variant={file.path}>
                      {file.display_path || file.path}
                    </a>
                  </div>
                ))}
              </li>
            ))}
            {!row.outputs?.length && (
              <li>{row.calls?.count ? `${row.calls.count} recorded calls` : 'This binding has no dedicated output record.'}</li>
            )}
          </ul>
        </>
      )}
      <a href={nodeHref(run, node)} data-testid="factory-runs-engine-capsule-open-node">Open node evidence and diffs →</a>
    </details>
  );
}

function SchedulerCapsule({ runs }: { runs: RunDetail[] }) {
  const groups = runs.flatMap((detail) => {
    const latest = new Map<string, JsonRecord>();
    for (const record of detail.records.observations ?? []) {
      const value = record.values as JsonRecord | undefined;
      if (record.kind !== 'node_contract_final' || value?.by !== 'scheduler-agent' || typeof value.node_id !== 'string') continue;
      const previous = latest.get(value.node_id);
      if (!previous || Number(record.created) >= Number(previous.created)) latest.set(value.node_id, record);
    }
    return latest.size ? [{ detail, latest }] : [];
  });
  if (!groups.length) return null;

  return (
    <article className="engine-capsule" data-testid="factory-runs-engine-capsule" data-variant="factory.scheduler">
      <h2>Node contract scheduler</h2>
      <p>Writes the node contract and binds capsules to their outputs. A node verifier checks that the output meets that contract.</p>
      <p><strong>Factory stage.</strong> The host checks that the scheduler's final requirements preserve the preliminary contract.</p>
      {groups.map(({ detail, latest }) => (
        <details key={detail.run.id}>
          <summary>In this run: {runLabel(detail)} · {latest.size} finalized contracts</summary>
          <ul aria-label="Final contract outputs">
            {[...latest.keys()].map((node) => (
              <li key={node}>
                <a href={nodeHref(detail.run.id, node, 'contract')} data-testid="factory-runs-engine-scheduler-output" data-variant={node}>
                  {nodeTitles[node] ?? node.replaceAll('_', ' ')}
                </a>
              </li>
            ))}
          </ul>
        </details>
      ))}
    </article>
  );
}

export function EngineCapsules({ name }: { name?: string }) {
  const { data, error } = useCapsuleResource('demo-runs', loadDemos);
  const byId = new Map<string, Binding>(
    demoCapsuleIds.map((id) => [id, { id, title: inferenceCapsules[id].title, nodes: [] }]),
  );
  for (const detail of data ?? []) {
    for (const [node, bindings] of Object.entries(detail.cc_overview ?? {})) {
      for (const binding of bindings) {
        const card = byId.get(binding.id);
        if (card) card.nodes.push({ detail, node });
        else byId.set(binding.id, { ...binding, nodes: [{ detail, node }] });
      }
    }
  }

  const selected = name && byId.get(atlasName(name)?.capsule_id ?? name);
  const cards = name ? (selected ? [selected] : []) : [...byId.values()];
  return (
    <section className="engine-capsules" data-testid="factory-runs-engine-capsules">
      <h1>{selected ? inferenceCapsules[selected.id]?.title ?? selected.title ?? selected.id : 'Capability Capsules'}</h1>
      {name ? <a href={capsuleHref()} data-testid="factory-runs-engine-capsules-back">Back to Capability Capsules</a> : (
        <>
          <p>Methods for building and checking inference engines, with evidence from their recorded runs.</p>
          <p>CC verifiers check how each capsule was applied. The factory hands the image and its test requirements to a lab agent for target acceptance.</p>
        </>
      )}
      {!data && !error && <p role="status">Loading capsule evidence…</p>}
      {error && <p role="alert">{error}</p>}
      {name && !selected && data && <p role="status">This capsule has no published evidence.</p>}
      <div className="engine-capsule-list" data-testid="factory-runs-engine-capsule-list">
        {cards.map((capsule) => {
          const copy = inferenceCapsules[capsule.id];
          return (
            <article className="engine-capsule" key={capsule.id} data-testid="factory-runs-engine-capsule" data-variant={capsule.id}>
              {!name && <h2><a href={capsuleHref(capsule.id)}>{copy?.title ?? capsule.title ?? capsule.id}</a></h2>}
              <p>{copy?.method ?? capsule.purpose ?? 'Records its inputs, outputs and verification work for the engine contract.'}</p>
              {copy && <p><strong>In this run.</strong> {copy.evidence}</p>}
              {capsule.id === prefixReuseId && <PrefixReuseEvidence />}
              {capsule.nodes.length > 0 && (
                <ul aria-label="Recorded node bindings">
                  {capsule.nodes.map(({ detail, node }) => (
                    <li key={detail.run.id + '/' + node}><CapsuleNode detail={detail} node={node} capsule={capsule.id} /></li>
                  ))}
                </ul>
              )}
            </article>
          );
        })}
        {!name && data && <SchedulerCapsule runs={data} />}
      </div>
    </section>
  );
}
