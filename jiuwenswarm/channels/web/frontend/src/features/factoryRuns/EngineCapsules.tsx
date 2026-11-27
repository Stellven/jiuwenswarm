import { Fragment, useCallback, useState } from 'react';
import { factoryApi, type CapsuleOverview, type JsonRecord, type RunDetail } from './api';
import { nodeHref, runHref } from './cc/navigation';
import { useCapsuleResource } from './cc/useCapsuleResource';

type Binding = CapsuleOverview & { nodes: string[] };

const loadLive = async () => {
  const listing = await factoryApi.list();
  const live = listing.runs.find((run) => run.featured);
  if (!live) throw new Error('The R8 run is unavailable.');
  return factoryApi.detail(live.id);
};

const nodeTitles: Record<string, string> = {
  pin_inputs: 'Pin inputs', ingest_nvfp4: 'Convert NVFP4', wire_expert_scales: 'Wire expert scales',
  build_base_engine: 'Build engine', requant_2bit: 'Compile mixed pack', size_prefill_batch: 'Plan prefill',
  build_image: 'Build image', deliver_to_lab: 'Deliver to lab',
};
const featured: Record<string, string> = {
  'weights.build_weight_pack_compiler': 'Quantization CC Q compiled the 267.2 GB mixed pack from the 528.9 GB NVFP4 pack.',
  'engine.size_prefill_batch': 'Prefill CC B raised the mixed-pack microbatch from 512 to 2048. NVFP4 kept its defaults.',
};

function CapsuleNode({ detail, node, capsule }: { detail: RunDetail; node: string; capsule: string }) {
  const [open, setOpen] = useState(false);
  const run = detail.run.id;
  const load = useCallback((id: string, signal: AbortSignal) => factoryApi.node(run, id, signal), [run]);
  const nodeDetails = useCapsuleResource(open ? node : undefined, load);
  const row = nodeDetails.data?.capsules.find((item) => item.id === capsule);

  return (
    <details data-testid="factory-runs-engine-capsule-node" data-variant={node} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary data-testid="factory-runs-engine-capsule-node-title"><code>{node}</code> · {nodeTitles[node]}</summary>
      {open && !nodeDetails.data && !nodeDetails.error && <p role="status">Loading node evidence…</p>}
      {nodeDetails.error && <p role="alert">{nodeDetails.error}</p>}
      {row && (
        <>
          <ul aria-label="Verifiers">
            {row.checks?.map((check) => (
              <li key={check.name} data-testid="factory-runs-engine-verifier" data-variant={check.name}>
                {check.name} · {check.verifier || 'Host check'} · {check.checks.some((result) => result.passed && !result.superseded) ? 'Passed' : 'See check record'}
              </li>
            ))}
            {!row.checks?.length && <li>No dedicated verifier recorded for this binding.</li>}
          </ul>
          <ul aria-label="Outputs">
            {row.outputs?.map((output) => (
              <li key={output.id} data-testid="factory-runs-engine-output" data-variant={output.id}>
                {output.name} · {output.kind}
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
              <li>{row.calls?.count ? `${row.calls.count} recorded calls` : 'No capsule output recorded at this node.'}</li>
            )}
          </ul>
        </>
      )}
      <a href={nodeHref(run, node)} data-testid="factory-runs-engine-capsule-open-node">Open node evidence and diffs →</a>
    </details>
  );
}

function SchedulerCapsule({ detail }: { detail: RunDetail }) {
  const latest = new Map<string, JsonRecord>();
  for (const record of detail.records.observations ?? []) {
    const value = record.values as JsonRecord | undefined;
    if (record.kind !== 'node_contract_final' || value?.by !== 'scheduler-agent' || typeof value.node_id !== 'string') continue;
    const previous = latest.get(value.node_id);
    if (!previous || Number(record.created) >= Number(previous.created)) latest.set(value.node_id, record);
  }
  if (!latest.size) return null;

  return (
    <article className="engine-capsule" data-testid="factory-runs-engine-capsule" data-variant="factory.scheduler">
      <h2>Node contract scheduler</h2>
      <code>factory.scheduler</code>
      <p>Finalizes engine node contracts and binds the capsules that can produce each output.</p>
      <p>The host checks that each proposal is at least as strict as its preliminary contract.</p>
      <ul aria-label="Final contract outputs">
        {[...latest].map(([node, record]) => (
          <li key={node}>
            <a href={nodeHref(detail.run.id, node, 'contract')} data-testid="factory-runs-engine-scheduler-output" data-variant={node}><code>{node}</code> · {nodeTitles[node]}</a>
            <div><code>{String(record.obs_id)}</code></div>
          </li>
        ))}
      </ul>
    </article>
  );
}

export function EngineCapsules() {
  const { data, error } = useCapsuleResource('live', loadLive);
  const byId = new Map<string, Binding>();
  for (const [node, bindings] of Object.entries(data?.cc_overview ?? {})) {
    for (const binding of bindings) {
      const row = byId.get(binding.id);
      if (row) row.nodes.push(node);
      else byId.set(binding.id, { ...binding, nodes: [node] });
    }
  }

  const cards = [...byId.values()].sort((a, b) => Number(!(a.id in featured)) - Number(!(b.id in featured)));
  return (
    <section className="engine-capsules" data-testid="factory-runs-engine-capsules">
      <h1>Capability Capsules</h1>
      <p>Capsules recorded in the R8 inference-engine run.</p>
      {!data && !error && <p role="status">Loading capsule evidence…</p>}
      {error && <p role="alert">{error}</p>}
      {data && (
        <div className="engine-capsule-list" data-testid="factory-runs-engine-capsule-list">
          {cards.map((capsule, index) => (
            <Fragment key={capsule.id}>
            {index === Object.keys(featured).length && <SchedulerCapsule detail={data} />}
            <article className="engine-capsule" key={capsule.id} data-testid="factory-runs-engine-capsule" data-variant={capsule.id}>
              <h2>{capsule.title || capsule.id}</h2>
              <code>{capsule.id}</code>
              {(featured[capsule.id] || capsule.purpose) && <p>{featured[capsule.id] || capsule.purpose}</p>}
              <ul aria-label="Recorded node bindings">
                {capsule.nodes.map((node) => (
                  <li key={node}><CapsuleNode detail={data} node={node} capsule={capsule.id} /></li>
                ))}
              </ul>
            </article>
            </Fragment>
          ))}
        </div>
      )}
    </section>
  );
}
