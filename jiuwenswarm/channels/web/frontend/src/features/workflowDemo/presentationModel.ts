import type {
  FactoryCatalog,
  FactoryNode,
  FactoryRecordingSummary,
  FactoryRequest,
  FactoryRun,
  FactoryEvent,
  StageDeclaration,
  Artifact,
} from './factoryClient';
import { stageLabels } from './copy.en';

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') {
    const object = value as Record<string, unknown>;
    return `{${Object.keys(object)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonical(object[key])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value) ?? 'undefined';
}

export function nextRecordedCursor(events: FactoryEvent[], cursor: number, received: unknown): number {
  const expected = events[cursor];
  if (!expected || canonical(expected) !== canonical(received))
    throw new Error('Replay stream does not match the next original recorded event');
  return cursor + 1;
}

export interface ReplayCheckpoint {
  cursor: number;
  sequence: number;
  label: string;
  kind: string;
  time: string;
}

const publicationLabels: Record<string, string> = {
  'source.checkout': 'Source acquired',
  'operator.native_inventory': 'Internal stages composed',
  'construction.cpp': 'C++ source published',
  'construction.native_cpp': 'Ascend C++ source published',
  'construction.native_sources': 'Native source bundle published',
  'construction.cpu_validation': 'CPU validation report published',
  'construction.build': 'Build report published',
  'construction.execution': 'Arithmetic report published',
  'construction.package': 'Source ZIP published',
  'construction.portability': 'Package rebuild report published',
  'value.report': 'Assessment report published',
};

export function replayCheckpoints(events: FactoryEvent[]): ReplayCheckpoint[] {
  return events.flatMap((event, index) => {
    if (event.type === 'stage.verified' && Array.isArray(event.payload.outputs)) {
      const candidates = event.payload.outputs.filter(
        (value: unknown) =>
          value &&
          typeof value === 'object' &&
          typeof (value as { kind?: unknown }).kind === 'string' &&
          publicationLabels[(value as { kind: string }).kind],
      ) as { kind: string }[];
      const artifact =
        candidates.find((item) => item.kind === 'construction.native_cpp') ||
        candidates.find((item) => item.kind === 'construction.native_sources') ||
        candidates[0];
      if (artifact)
        return [
          {
            cursor: index + 1,
            sequence: event.sequence,
            label: publicationLabels[artifact.kind],
            kind: artifact.kind,
            time: event.time,
          },
        ];
    }
    if (/^run\.(completed|failed|blocked|cancelled)$/.test(event.type))
      return [
        {
          cursor: index + 1,
          sequence: event.sequence,
          label: `Recorded outcome: ${event.type.slice(4)}`,
          kind: event.type,
          time: event.time,
        },
      ];
    return [];
  });
}

export function displayName(value: string): string {
  return value.replace(/[_.-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function stageLabel(stage: { id?: string; stage_id?: string; name: string }): string {
  return stageLabels[stage.stage_id || stage.id || ''] || stage.name;
}

export function productionPath(run: FactoryRun) {
  const requested = run.artifacts.filter((artifact) => run.request.goals.includes(artifact.kind));
  const endpointKinds = new Set([
    'source.checkout',
    'operator.native_inventory',
    'construction.cpp',
    'construction.native_cpp',
    'construction.native_sources',
    'construction.source',
    'construction.package',
    'construction.cpu_validation',
    'construction.build',
    'construction.execution',
    'construction.portability',
  ]);
  const preferredKinds = run.request.goals.includes('construction.native_sources')
    ? ['construction.cpu_validation', 'construction.native_sources']
    : run.request.goals.includes('construction.package')
      ? ['construction.package']
      : [];
  const preferred = preferredKinds
    .map((kind) =>
      run.artifacts
        .slice()
        .reverse()
        .find((artifact) => artifact.kind === kind),
    )
    .find(Boolean);
  const published =
    preferred ||
    requested
      .slice()
      .reverse()
      .find((artifact) => endpointKinds.has(artifact.kind)) ||
    run.artifacts
      .slice()
      .reverse()
      .find((artifact) => endpointKinds.has(artifact.kind));
  const target = published && run.nodes.find((node) => node.id === published.producer);
  if (!target)
    return { nodes: [] as FactoryNode[], ancestors: [] as FactoryNode[], endpoint: undefined as Artifact | undefined };
  const ancestors = new Set<string>();
  const visit = (id: string) => {
    if (ancestors.has(id)) return;
    ancestors.add(id);
    run.edges.filter((edge) => edge.to === id).forEach((edge) => visit(edge.from));
  };
  visit(target.id);
  const longest = (node: FactoryNode, seen: Set<string>): FactoryNode[] => {
    const path = new Set([...seen, node.id]);
    const inputs = run.edges.filter((edge) => edge.to === node.id && !path.has(edge.from));
    let best: FactoryNode[] = [];
    for (const edge of inputs) {
      const source = run.nodes.find((item) => item.id === edge.from);
      if (!source) continue;
      const candidate = longest(source, path);
      if (candidate.length > best.length) best = candidate;
    }
    return [...best, node];
  };
  return {
    nodes: longest(target, new Set()),
    ancestors: run.nodes.filter((node) => ancestors.has(node.id)),
    endpoint: published,
  };
}

export function nodePoolRef(node: FactoryNode): string {
  return node.pool_origin?.full_ref || node.workflow_path || '';
}

export function publishedSourceProducer(run: FactoryRun): string {
  const preferred = run.request.target_backend === 'ascend' ? 'construction.native_cpp' : 'construction.cpp';
  const artifact =
    run.artifacts.find((item) => item.kind === preferred) ||
    run.artifacts.find((item) => item.kind === 'construction.cpp');
  return artifact && run.nodes.some((node) => node.id === artifact.producer) ? artifact.producer : '';
}

export function nodeOperationIdentity(node: FactoryNode, run: FactoryRun): string | null {
  const declared = node.parameters?.operation_id;
  if (typeof declared === 'string' && declared) return declared;
  const receipt = node.attempts
    .flatMap((attempt) => attempt.inputs)
    .find(
      (artifact) =>
        artifact.kind === 'source.operator' &&
        run.artifacts.some((published) =>
          ['id', 'kind', 'path', 'sha256', 'size', 'producer'].every(
            (field) => published[field as keyof typeof published] === artifact[field as keyof typeof artifact],
          ),
        ),
    );
  const producer = receipt && run.nodes.find((item) => item.id === receipt.producer);
  const operation = producer && producer.parameters?.operation_id;
  return typeof operation === 'string' && operation ? operation : null;
}

export function catalogFromStages(stages: StageDeclaration[]): FactoryCatalog {
  const groups = [...new Set(stages.map((stage) => stage.workflow_id))].map((id) => ({ id, name: displayName(id) }));
  const subworkflows: FactoryCatalog['subworkflows'] = [];
  for (const stage of stages) {
    let group = subworkflows.find((item) => item.id === stage.subworkflow_id && item.workflow_id === stage.workflow_id);
    if (!group) {
      group = {
        id: stage.subworkflow_id,
        name: displayName(stage.subworkflow_id),
        workflow_id: stage.workflow_id,
        stages: [],
      };
      subworkflows.push(group);
    }
    group.stages.push(stage);
  }
  return { goals: [], groups, subworkflows, stages };
}

export function recordingTitle(recording: FactoryRecordingSummary): string {
  if (recording.label) return recording.label;
  const task = recording.request.task;
  if (recording.request.goals.includes('construction.native_sources')) return 'Ascend source + CPU reference';
  if (task?.acceptance.native_execution || task?.acceptance.full_model_inference) return 'Native target';
  if (task?.oracle) return 'Mixed operators';
  if (task?.capabilities?.some((item) => /normal/i.test(item))) return 'Normalization';
  if (['routing', 'activation', 'aggregation'].every((item) => task?.capabilities?.includes(item)))
    return 'Core source';
  return task?.capabilities?.join(', ') || task?.description || recording.id;
}

export function requestScope(request: FactoryRequest): string {
  const criteria = request.task?.acceptance;
  if (!criteria) return request.goals.join(', ');
  const labels = Object.entries(criteria)
    .filter(([, required]) => required)
    .map(([name]) => name.replace(/_/g, ' '));
  if (request.goals.includes('construction.native_sources')) labels.unshift('Ascend source generation');
  if (request.goals.includes('construction.cpu_validation') && !criteria.cpu_validation)
    labels.push('CPU reference validation');
  return labels.join(' · ');
}

export function compositionCounts(nodes: FactoryNode[]) {
  return {
    stages: nodes.length,
    workflows: new Set(nodes.map((node) => nodePoolRef(node).split('/')[0] || node.workflow_id)).size,
    subworkflows: new Set(
      nodes.map((node) =>
        nodePoolRef(node)
          ? nodePoolRef(node).split('/').slice(0, 2).join('/')
          : `${node.workflow_id}/${node.subworkflow_id}`,
      ),
    ).size,
    implementations: nodes.filter((node) => node.stage_id.startsWith('lower.')).length,
  };
}
