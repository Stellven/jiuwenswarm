import { useMemo, useState } from 'react';
import {
  Background,
  Handle,
  MarkerType,
  Panel,
  Position,
  ReactFlow,
  useReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react';
import dagre from '@dagrejs/dagre';
import { Box, ClipboardList, FileText, GitBranch, Layers3, Maximize, Minus, Plus, Workflow, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { GraphLink, GraphModel, GraphNode, GraphReplay } from './graphModel';
import { graphProgress } from './graphModel';
import '@xyflow/react/dist/style.css';
import './graphViewer.css';

const labels = {
  en: {
    title: { taskgraph: 'Run task graph', ontology: 'Ontology graph', contract: 'Contract graph' },
    kind: {
      contract: 'Contract',
      task: 'Task',
      step: 'Plan step',
      capsule: 'Capability Capsule',
      entity: 'Entity',
      group: 'Group',
    },
    state: {
      proposed: 'Proposed',
      ready: 'Ready',
      running: 'Running',
      blocked: 'Blocked',
      done: 'Done',
      failed: 'Failed',
      cancelled: 'Cancelled',
      superseded: 'Superseded',
    },
    link: {
      dependency: 'Precedes',
      superseded: 'Superseded by',
      contract: 'Governs',
      step: 'Starts with',
      capsule: 'References capsule',
      relation: 'Relates to',
      member: 'Contains',
    },
    nodeCount: 'Nodes',
    linkCount: 'Links',
    zoomIn: 'Zoom in',
    zoomOut: 'Zoom out',
    fit: 'Fit graph',
    close: 'Close node details',
    current: 'Current event',
    seen: 'Reached',
    upcoming: 'Upcoming',
    incoming: 'Incoming links',
    outgoing: 'Outgoing links',
    empty: 'No task graph nodes are available.',
    upcomingDetail: 'This plan step has yet to appear at the current replay position.',
  },
  zh: {
    title: { taskgraph: '运行任务图', ontology: '本体关系图', contract: '契约关系图' },
    kind: { contract: '契约', task: '任务', step: '计划步骤', capsule: '能力胶囊', entity: '实体', group: '分组' },
    state: {
      proposed: '已提议',
      ready: '就绪',
      running: '运行中',
      blocked: '受阻',
      done: '已完成',
      failed: '失败',
      cancelled: '已取消',
      superseded: '已取代',
    },
    link: {
      dependency: '先于',
      superseded: '被取代',
      contract: '约束',
      step: '始于',
      capsule: '引用胶囊',
      relation: '关联',
      member: '包含',
    },
    nodeCount: '节点',
    linkCount: '连线',
    zoomIn: '放大',
    zoomOut: '缩小',
    fit: '适应视图',
    close: '关闭节点详情',
    current: '当前事件',
    seen: '已到达',
    upcoming: '尚未到达',
    incoming: '入向连线',
    outgoing: '出向连线',
    empty: '没有可用的任务图节点。',
    upcomingDetail: '当前回放位置尚未出现此计划步骤。',
  },
} as const;

function useLabels() {
  const { i18n } = useTranslation();
  return i18n.language?.toLowerCase().startsWith('zh') ? labels.zh : labels.en;
}

const icons = {
  contract: FileText,
  task: ClipboardList,
  step: Workflow,
  capsule: Box,
  entity: GitBranch,
  group: Layers3,
};
const nodeWidth = 216;
const nodeHeight = 70;
const fitOptions = { padding: 0.18, maxZoom: 1, minZoom: 0.1 };
type Phase = 'current' | 'seen' | 'upcoming';
type FlowNode = Node<
  {
    node: GraphNode;
    phase?: Phase;
    state?: string;
    grouped?: boolean;
    select: (id: string) => void;
  },
  'factoryNode'
>;

function statusText(state: string | undefined, phase: Phase | undefined, text: ReturnType<typeof useLabels>) {
  if (phase === 'upcoming') return text.upcoming;
  const localizedState = state ? (text.state[state as keyof typeof text.state] ?? state) : '';
  if (phase === 'current') return localizedState ? `${localizedState} · ${text.current}` : text.current;
  return localizedState;
}

function linkText(link: GraphLink, text: ReturnType<typeof useLabels>) {
  return link.label?.replace(/_/g, ' ') ?? text.link[link.kind];
}

function GraphCard({ data, selected }: NodeProps<FlowNode>) {
  const text = useLabels();
  const { node, state, phase, grouped, select } = data;
  const Icon = icons[node.kind];
  const status = statusText(state, phase, text);
  return (
    <div className="factory-graph-card" data-grouped={grouped || undefined}>
      <Handle type="target" position={Position.Left} isConnectable={false} className="factory-graph-handle" />
      <button
        type="button"
        className="factory-graph-node-button nodrag nopan"
        data-testid="factory-runs-graph-node"
        data-variant={node.id}
        data-kind={node.kind}
        data-phase={phase}
        data-node-state={state}
        aria-pressed={selected}
        onClick={() => select(node.id)}
        title={node.label}
      >
        <Icon size={17} aria-hidden="true" />
        <span className="factory-graph-node-copy">
          <span className="factory-graph-node-kind">{text.kind[node.kind]}</span>
          <strong>{node.label}</strong>
        </span>
        {status && (
          <span className="factory-graph-node-state" data-testid="factory-runs-graph-node-status">
            {status}
          </span>
        )}
      </button>
      <Handle type="source" position={Position.Right} isConnectable={false} className="factory-graph-handle" />
    </div>
  );
}

const nodeTypes = { factoryNode: GraphCard };

type Placement = {
  node: GraphNode;
  position: { x: number; y: number };
  width: number;
  height: number;
  parentId?: string;
  grouped?: boolean;
};

function groupLayout(graph: GraphModel): Placement[] | null {
  const groups = graph.nodes.filter((node) => node.kind === 'group');
  const members = graph.nodes.filter((node) => node.kind !== 'group');
  const links = graph.links.filter((link) => link.kind === 'member');
  const memberIds = new Set(links.map((link) => link.target));
  if (!groups.length || links.length !== graph.links.length || members.length !== links.length) return null;
  if (members.some((node) => !memberIds.has(node.id))) return null;

  const columns = Math.min(3, groups.length);
  const step = nodeHeight + 9;
  const width = nodeWidth + 24;
  const height =
    step * (Math.max(...groups.map((group) => links.filter((link) => link.source === group.id).length)) + 1) + 15;
  return groups.flatMap((group, index) => [
    {
      node: group,
      position: { x: (index % columns) * (width + 18), y: Math.floor(index / columns) * (height + 18) },
      width,
      height,
      grouped: true,
    },
    ...members
      .filter((member) => links.some((link) => link.source === group.id && link.target === member.id))
      .map((node, memberIndex) => ({
        node,
        position: { x: 12, y: step * (memberIndex + 1) + 8 },
        width: nodeWidth,
        height: nodeHeight,
        parentId: group.id,
      })),
  ]);
}

function layout(graph: GraphModel): { placement: Placement[]; links: GraphLink[] } {
  const groups = groupLayout(graph);
  if (groups) return { placement: groups, links: [] };
  const positions = new dagre.graphlib.Graph()
    .setGraph({ rankdir: 'LR', nodesep: 22, ranksep: 112, acyclicer: 'greedy' })
    .setDefaultEdgeLabel(() => ({}));
  for (const node of graph.nodes) positions.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  for (const link of graph.links) positions.setEdge(link.source, link.target);
  dagre.layout(positions);
  return {
    placement: graph.nodes.map((node) => {
      const { x, y } = positions.node(node.id);
      return { node, position: { x: x - nodeWidth / 2, y: y - nodeHeight / 2 }, width: nodeWidth, height: nodeHeight };
    }),
    links: graph.links,
  };
}

function ZoomControls() {
  const { fitView, zoomIn, zoomOut } = useReactFlow();
  const text = useLabels();
  return (
    <Panel position="top-right" className="factory-graph-controls">
      <button
        type="button"
        aria-label={text.zoomIn}
        title={text.zoomIn}
        data-testid="factory-runs-graph-zoom-in"
        onClick={() => void zoomIn({ duration: 150 })}
      >
        <Plus size={17} aria-hidden="true" />
      </button>
      <button
        type="button"
        aria-label={text.zoomOut}
        title={text.zoomOut}
        data-testid="factory-runs-graph-zoom-out"
        onClick={() => void zoomOut({ duration: 150 })}
      >
        <Minus size={17} aria-hidden="true" />
      </button>
      <button
        type="button"
        aria-label={text.fit}
        title={text.fit}
        data-testid="factory-runs-graph-fit"
        onClick={() => void fitView({ ...fitOptions, duration: 220 })}
      >
        <Maximize size={15} aria-hidden="true" />
      </button>
    </Panel>
  );
}

function NodeDetails({
  node,
  details,
  phase,
  links,
  nodeLabels,
  onClose,
}: {
  node: GraphNode;
  details: GraphNode['details'];
  phase?: Phase;
  links: GraphLink[];
  nodeLabels: Map<string, string>;
  onClose: () => void;
}) {
  const text = useLabels();
  const incoming = links.filter((link) => link.target === node.id);
  const outgoing = links.filter((link) => link.source === node.id);
  return (
    <aside className="factory-graph-inspector" aria-label={node.label} data-testid="factory-runs-graph-inspector">
      <div className="factory-graph-inspector-heading">
        <div>
          <small>{text.kind[node.kind]}</small>
          <h4>{node.label}</h4>
        </div>
        <button type="button" aria-label={text.close} onClick={onClose} data-testid="factory-runs-graph-close-details">
          <X size={17} aria-hidden="true" />
        </button>
      </div>
      {phase === 'upcoming' && node.kind === 'step' ? (
        <p data-testid="factory-runs-graph-upcoming">{text.upcomingDetail}</p>
      ) : (
        <>
          <dl data-testid="factory-runs-graph-node-details">
            {Object.entries(details)
              .filter(([, value]) => value !== undefined && value !== '')
              .map(([name, value]) => (
                <div key={name} data-testid="factory-runs-graph-detail-field" data-variant={name}>
                  <dt>{name}</dt>
                  <dd>
                    {name === 'state' && typeof value === 'string' ? (
                      statusText(value, undefined, text)
                    ) : typeof value === 'object' ? (
                      <pre>{JSON.stringify(value, null, 2)}</pre>
                    ) : (
                      String(value)
                    )}
                  </dd>
                </div>
              ))}
          </dl>
          {(
            [
              ['incoming', incoming],
              ['outgoing', outgoing],
            ] as const
          ).map(
            ([direction, edges]) =>
              edges.length > 0 && (
                <section key={direction} data-testid={`factory-runs-graph-${direction}-links`}>
                  <h5>{text[direction]}</h5>
                  <ul>
                    {edges.map((link) => {
                      const other = direction === 'incoming' ? link.source : link.target;
                      const label = linkText(link, text);
                      return (
                        <li
                          key={JSON.stringify([link.kind, other, label])}
                          data-testid="factory-runs-graph-link-detail"
                          data-variant={other}
                        >
                          {nodeLabels.get(other)} <small>· {label}</small>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ),
          )}
        </>
      )}
    </aside>
  );
}

export function GraphViewer({ graph, replay }: { graph: GraphModel; replay?: GraphReplay }) {
  const text = useLabels();
  const [selectedId, setSelectedId] = useState('');
  const geometry = useMemo(() => layout(graph), [graph]);
  const nodeLabels = useMemo(() => new Map(graph.nodes.map((node) => [node.id, node.label])), [graph.nodes]);
  const progress = useMemo(() => (replay ? graphProgress(graph, replay) : undefined), [graph, replay]);
  const nodes = useMemo<FlowNode[]>(
    () =>
      geometry.placement.map(({ node, position, width, height, parentId, grouped }) => {
        const mark = progress?.get(node.id);
        const state =
          mark?.phase === 'upcoming' ? undefined : String(mark?.details?.state ?? node.state ?? '') || undefined;
        return {
          id: node.id,
          type: 'factoryNode',
          position,
          width,
          height,
          parentId,
          selected: selectedId === node.id,
          data: { node, state, grouped, phase: mark?.phase, select: setSelectedId },
        };
      }),
    [geometry, progress, selectedId],
  );
  const visibleLinks = useMemo(
    () =>
      new Set(
        graph.links.filter((link) => {
          const source = progress?.get(link.source);
          const target = progress?.get(link.target);
          if (source?.phase === 'upcoming' || target?.phase === 'upcoming') return false;
          if (link.kind === 'dependency' && Array.isArray(target?.details?.depends_on)) {
            return target.details.depends_on.includes(link.source.replace(/^step:/, ''));
          }
          if (link.kind === 'superseded' && source?.details) {
            return source.details.superseded_by === link.target.replace(/^step:/, '');
          }
          return true;
        }),
      ),
    [graph.links, progress],
  );
  const edges = useMemo<Edge[]>(
    () =>
      geometry.links.map((link, index) => {
        const current =
          progress?.get(link.source)?.phase === 'current' || progress?.get(link.target)?.phase === 'current';
        const reached = visibleLinks.has(link);
        const edgeClass = !reached ? 'factory-graph-edge-upcoming' : current ? 'factory-graph-edge-current' : undefined;
        return {
          id: `graph-edge-${index}`,
          source: link.source,
          target: link.target,
          type: 'smoothstep',
          className: edgeClass,
          label: link.kind === 'relation' || link.kind === 'superseded' ? linkText(link, text) : undefined,
          markerEnd: { type: MarkerType.ArrowClosed, width: 17, height: 17 },
          style: link.kind === 'superseded' ? { strokeDasharray: '5 4' } : undefined,
        };
      }),
    [geometry.links, progress, text, visibleLinks],
  );
  const selected = graph.nodes.find((node) => node.id === selectedId);
  const selectedProgress = selected ? progress?.get(selected.id) : undefined;
  const showReplayLegend = Boolean(replay && graph.kind !== 'ontology');
  if (!nodes.length)
    return (
      <p className="factory-graph-empty" data-testid="factory-runs-graph-empty">
        {text.empty}
      </p>
    );

  return (
    <section className="factory-graph-view" aria-label={text.title[graph.kind]} data-testid="factory-runs-graph">
      <div className="factory-graph-summary">
        <strong data-testid="factory-runs-graph-title">{text.title[graph.kind]}</strong>
        <span data-testid="factory-runs-graph-count">
          {graph.nodes.length} {text.nodeCount} · {graph.links.length} {text.linkCount}
        </span>
        {showReplayLegend && (
          <div className="factory-graph-replay-key" data-testid="factory-runs-graph-replay-key">
            {(['current', 'seen', 'upcoming'] as const).map((phase) => (
              <span key={phase} data-phase={phase}>
                <i aria-hidden="true" />
                {text[phase]}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="factory-graph-canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          nodesDraggable={false}
          nodesConnectable={false}
          nodesFocusable={false}
          edgesFocusable={false}
          deleteKeyCode={null}
          multiSelectionKeyCode={null}
          selectionKeyCode={null}
          minZoom={0.1}
          maxZoom={2}
          defaultMarkerColor="var(--color-text-secondary)"
          fitView
          fitViewOptions={fitOptions}
          onPaneClick={() => setSelectedId('')}
          onKeyDown={(event) => {
            if (event.key === 'Escape') setSelectedId('');
          }}
          proOptions={{ hideAttribution: true }}
          aria-label={text.title[graph.kind]}
          data-testid="factory-runs-graph-canvas"
        >
          <Background gap={19} size={1.2} color="var(--color-border-default)" />
          <ZoomControls />
        </ReactFlow>
        {selected && (
          <NodeDetails
            node={selected}
            details={selectedProgress?.details ?? selected.details}
            phase={selectedProgress?.phase}
            links={[...visibleLinks]}
            nodeLabels={nodeLabels}
            onClose={() => setSelectedId('')}
          />
        )}
      </div>
    </section>
  );
}
