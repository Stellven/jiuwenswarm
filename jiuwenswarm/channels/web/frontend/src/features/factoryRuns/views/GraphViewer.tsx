import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
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
import { Box, ChevronsDownUp, ChevronsUpDown, ClipboardList, FileText, GitBranch, Layers3, Maximize, Minus, Plus, Workflow, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { GraphLink, GraphModel, GraphNode, GraphReplay } from './graphModel';
import { collapsibleNodes, graphChildren, graphProgress, hiddenUnder, visibleGraphNodes } from './graphModel';
import type { KeyFile } from './storyModel.ts';
import { MembershipEdge } from './MembershipEdge';
import { checkBadge, nodeHold, primaryCapsule, type CheckBadge } from './checkModel';
import { NodeChecks } from './NodeChecks';
import { ReplayLabel } from './NodeEvidence';
import { replayLabel } from './nodeEvidenceModel';
import { atlasTitle } from '../cc/atlasNames';
import { layoutOntologyGroups, type GraphPlacement } from './ontologyLayout';
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
    expandAll: 'Expand all',
    collapseAll: 'Collapse all',
    expand: 'Expand children',
    collapse: 'Collapse children',
    purpose: 'Purpose',
    status: 'Status',
    records: 'Linked records',
    files: 'Linked files',
    keyFiles: 'Key files',
    steps: 'Replay steps',
    allFields: 'All recorded fields',
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
    expandAll: '全部展开',
    collapseAll: '全部折叠',
    expand: '展开子节点',
    collapse: '折叠子节点',
    purpose: '目的',
    status: '状态',
    records: '关联记录',
    files: '关联文件',
    keyFiles: '关键文件',
    steps: '回放步骤',
    allFields: '全部字段',
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
const nodeHeight = 82;
const fitOptions = { padding: 0.18, maxZoom: 1, minZoom: 0.1 };
type Phase = 'current' | 'seen' | 'upcoming';
type FlowNode = Node<
  {
    node: GraphNode;
    phase?: Phase;
    state?: string;
    grouped?: boolean;
    member?: boolean;
    childCount: number;
    hiddenCount: number;
    check?: CheckBadge;
    cc?: string;
    held?: boolean;
    replayOrigin?: string;
    collapsed: boolean;
    select: (id: string) => void;
    toggle: (id: string) => void;
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
  const { node, state, phase, grouped, member, select, toggle, childCount, hiddenCount, collapsed, check, cc, held } = data;
  const Icon = icons[node.kind];
  const status = statusText(state, phase, text);
  return (
    <div className="factory-graph-card" data-grouped={grouped || undefined} data-member={member || undefined}>
      <Handle type="target" position={Position.Left} isConnectable={false} className="factory-graph-handle" />
      <button
        type="button"
        className="factory-graph-node-button nodrag nopan"
        data-testid="factory-runs-graph-node"
        data-variant={node.id}
        data-kind={node.kind}
        data-phase={phase}
        data-node-state={state}
        data-held={held || undefined}
        data-check={check?.tone}
        aria-pressed={selected}
        aria-expanded={childCount ? !collapsed : undefined}
        onClick={() => {
          select(node.id);
          if (childCount) toggle(node.id);
        }}
        title={node.label}
      >
        <Icon size={17} aria-hidden="true" />
        <span className="factory-graph-node-copy">
          <span className="factory-graph-node-kind">
            {typeof node.details.label_kind === 'string' ? node.details.label_kind : text.kind[node.kind]}
            {cc && (
              <span className="factory-graph-node-cc" data-testid="factory-runs-graph-node-cc" title={cc}>
                {atlasTitle(cc) ?? cc.split('.').pop()}
              </span>
            )}
            {data.replayOrigin && (
              <small className="factory-graph-node-replay" title={data.replayOrigin} data-testid="factory-runs-graph-node-replay">
                Replayed
              </small>
            )}
          </span>
          <strong>{node.label}</strong>
        </span>
        {(status || check) && (
          <span className="factory-graph-node-state" data-testid="factory-runs-graph-node-status">
            {status}
            {check && (
              <span className="factory-graph-check-badge" data-tone={check.tone} data-testid="factory-runs-graph-check-badge">
                {check.text}
              </span>
            )}
          </span>
        )}
        {childCount > 0 && (
          <span
            className="factory-graph-node-toggle"
            data-testid="factory-runs-graph-node-toggle"
            data-variant={collapsed ? 'collapsed' : 'expanded'}
            title={collapsed ? text.expand : text.collapse}
          >
            {collapsed ? `▸ +${hiddenCount}` : `▾ ${childCount}`}
          </span>
        )}
      </button>
      <Handle
        type="source"
        position={grouped ? Position.Bottom : Position.Right}
        isConnectable={false}
        className={grouped ? 'factory-graph-handle factory-graph-membership-origin' : 'factory-graph-handle'}
      />
    </div>
  );
}

const nodeTypes = { factoryNode: GraphCard };
const edgeTypes = { membership: MembershipEdge };

function layout(graph: GraphModel): { placement: GraphPlacement[]; links: GraphLink[] } {
  const positions = new dagre.graphlib.Graph()
    .setGraph({ rankdir: 'LR', nodesep: 34, ranksep: 120, acyclicer: 'greedy' })
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

function ZoomControls({
  grouped,
  onExpandAll,
  onCollapseAll,
}: {
  grouped: boolean;
  onExpandAll?: () => void;
  onCollapseAll?: () => void;
}) {
  const { fitView, setViewport, zoomIn, zoomOut } = useReactFlow();
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
        onClick={() => {
          if (grouped) void setViewport({ x: 0, y: 0, zoom: 1 }, { duration: 220 });
          else void fitView({ ...fitOptions, duration: 220 });
        }}
      >
        <Maximize size={15} aria-hidden="true" />
      </button>
      {onExpandAll && (
        <button
          type="button"
          aria-label={text.expandAll}
          title={text.expandAll}
          data-testid="factory-runs-graph-expand-all"
          onClick={onExpandAll}
        >
          <ChevronsUpDown size={16} aria-hidden="true" />
        </button>
      )}
      {onCollapseAll && (
        <button
          type="button"
          aria-label={text.collapseAll}
          title={text.collapseAll}
          data-testid="factory-runs-graph-collapse-all"
          onClick={onCollapseAll}
        >
          <ChevronsDownUp size={16} aria-hidden="true" />
        </button>
      )}
    </Panel>
  );
}

/** Zoom to the current replay step so its nodes are readable, not the whole graph at fit. */
function FocusCurrent({ ids }: { ids: string }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    if (!ids) return;
    const timer = window.setTimeout(() => {
      void fitView({ nodes: ids.split('|').map((id) => ({ id })), padding: 0.5, maxZoom: 1, duration: 300 });
    }, 50);
    return () => window.clearTimeout(timer);
  }, [fitView, ids]);
  return null;
}

function NodeDetails({
  node,
  details,
  phase,
  links,
  nodeLabels,
  onClose,
  replay,
}: {
  node: GraphNode;
  details: GraphNode['details'];
  phase?: Phase;
  links: GraphLink[];
  nodeLabels: Map<string, string>;
  onClose: () => void;
  replay?: GraphReplay;
}) {
  const text = useLabels();
  const linked = nodeRecords(details);
  const steps = (replay?.curated?.steps ?? []).filter((step) =>
    (step.graph_nodes ?? []).some((id) => id === node.id || id === node.planId),
  );
  const evidenceNode = steps.find((step) => step.node_id)?.node_id ?? node.planId;
  const stepRecordIds = steps.flatMap((step) => (step.records ?? []).map((row) => row.id));
  const recordIds = [...linked, ...stepRecordIds];
  const files = (replay?.files ?? []).filter((file) =>
    (file.artifact_ids ?? []).some((id) => recordIds.some((record) => id === record || id.startsWith(record + ':'))),
  );
  const keys: KeyFile[] = steps.flatMap((step) => step.key_files.map((key) => ({ ...key, step: step.step })));
  const purpose = [details.title, details.objective, details.reason, details.kind]
    .filter((value): value is string => typeof value === 'string' && value.trim() !== '')
    .filter((value, index, all) => all.indexOf(value) === index);
  const state = typeof details.state === 'string' ? details.state : node.state;
  const incoming = links.filter((link) => link.target === node.id);
  const outgoing = links.filter((link) => link.source === node.id);
  return (
    <aside className="factory-graph-inspector" aria-label={node.label} data-testid="factory-runs-graph-inspector">
      <div className="factory-graph-inspector-heading">
        <div>
          <small>{typeof node.details.label_kind === 'string' ? node.details.label_kind : text.kind[node.kind]}</small>
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
          <section className="factory-graph-summary-fields" data-testid="factory-runs-graph-node-summary">
            {purpose.length > 0 && (
              <p data-testid="factory-runs-graph-purpose">
                <small>{text.purpose}</small> {purpose.join(' · ')}
              </p>
            )}
            <p data-testid="factory-runs-graph-status">
              <small>{text.status}</small> {statusText(state, phase, text) || '—'}
            </p>
            <ReplayLabel value={evidenceNode ? replay?.replayByNode?.get(evidenceNode) : undefined} />
            {evidenceNode && replay?.onOpenNode && (
              <button type="button" className="factory-node-evidence-button" data-testid="factory-runs-graph-open-node-evidence"
                onClick={() => replay.onOpenNode?.(evidenceNode)}>
                View node evidence
              </button>
            )}
            {steps.length > 0 && (
              <p data-testid="factory-runs-graph-steps">
                <small>{text.steps}</small> {steps.map((step) => `${step.step}. ${step.presentation_title}`).join(' · ')}
              </p>
            )}
          </section>
          {node.kind === 'step' && node.planId && (replay?.checks || replay?.operator) && (
            <NodeChecks
              view={replay?.checks?.[node.planId]}
              node={node.details}
              files={replay?.files}
              onOpenFile={replay?.onOpenFile}
              operator={replay?.operator}
            />
          )}
          {keys.length > 0 && (
            <section data-testid="factory-runs-graph-key-files">
              <h5>★ {text.keyFiles}</h5>
              <ul>
                {keys.map((key) => (
                  <li key={`${key.step}:${key.path}`}>
                    <button
                      type="button"
                      className="factory-graph-file-link"
                      data-testid="factory-runs-graph-key-file"
                      data-variant={key.path}
                      title={key.why}
                      onClick={() => replay?.onOpenFile?.(key.path)}
                    >
                      ★ {key.label}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {linked.length > 0 && (
            <section data-testid="factory-runs-graph-records">
              <h5>{text.records}</h5>
              <ul>
                {linked.map((id) => (
                  <li key={id}>
                    <code>{id}</code>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {files.length > 0 && (
            <section data-testid="factory-runs-graph-files">
              <h5>{text.files}</h5>
              <ul>
                {files.slice(0, 12).map((file) => (
                  <li key={file.path}>
                    <button
                      type="button"
                      className="factory-graph-file-link"
                      data-testid="factory-runs-graph-file"
                      onClick={() => replay?.onOpenFile?.(file.path)}
                    >
                      {file.display_path || file.path}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
          <details>
            <summary>{text.allFields}</summary>
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
          </details>
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

function nodeRecords(details: GraphNode['details']) {
  return [
    ...(Array.isArray(details.evidence_ids) ? details.evidence_ids : []),
    ...(Array.isArray(details.attempt_ids) ? details.attempt_ids : []),
  ].filter((id): id is string => typeof id === 'string');
}

export function GraphViewer({ graph: fullGraph, replay }: { graph: GraphModel; replay?: GraphReplay }) {
  const text = useLabels();
  const [selectedId, setSelectedId] = useState('');
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  const collapsible = fullGraph.kind !== 'ontology';
  const children = useMemo(() => graphChildren(fullGraph), [fullGraph]);
  const visibleIds = useMemo(() => visibleGraphNodes(fullGraph, collapsed), [fullGraph, collapsed]);
  const graph = useMemo<GraphModel>(
    () => ({
      ...fullGraph,
      nodes: fullGraph.nodes.filter((node) => visibleIds.has(node.id)),
      links: fullGraph.links.filter((link) => visibleIds.has(link.source) && visibleIds.has(link.target)),
    }),
    [fullGraph, visibleIds],
  );
  const toggle = useCallback(
    (id: string) =>
      setCollapsed((old) => {
        const next = new Set(old);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      }),
    [],
  );
  const view = useRef<HTMLElement>(null);
  const [width, setWidth] = useState(760);
  useLayoutEffect(() => {
    const element = view.current;
    if (!element || graph.kind !== 'ontology') return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0) setWidth(Math.floor(entry.contentRect.width) - 2);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [graph]);
  const grouped = useMemo(() => layoutOntologyGroups(graph, width), [graph, width]);
  const geometry = useMemo(() => grouped ?? layout(graph), [graph, grouped]);
  const nodeLabels = useMemo(() => new Map(fullGraph.nodes.map((node) => [node.id, node.label])), [fullGraph.nodes]);
  const progress = useMemo(() => (replay ? graphProgress(fullGraph, replay) : undefined), [fullGraph, replay]);
  const nodes = useMemo<FlowNode[]>(
    () =>
      geometry.placement.map(({ node, position, width, height, parentId, grouped }) => {
        const mark = progress?.get(node.id);
        const state =
          mark?.phase === 'upcoming' ? undefined : String(mark?.details?.state ?? node.state ?? '') || undefined;
        const checks = node.planId ? replay?.checks?.[node.planId] : undefined;
        const shown = node.kind === 'step' && mark?.phase !== 'upcoming';
        return {
          id: node.id,
          type: 'factoryNode',
          position,
          width,
          height,
          parentId,
          selected: selectedId === node.id,
          data: {
            node,
            state,
            grouped,
            member: Boolean(parentId),
            phase: mark?.phase,
            select: setSelectedId,
            toggle,
            childCount: collapsible ? (children.get(node.id)?.length ?? 0) : 0,
            hiddenCount: collapsed.has(node.id) ? hiddenUnder(fullGraph, node.id, visibleIds) : 0,
            collapsed: collapsed.has(node.id),
            check: shown ? checkBadge(checks, node.details) : undefined,
            cc: shown ? primaryCapsule(checks, node.details.capability) : undefined,
            held: shown && Boolean(nodeHold(node.details)),
            replayOrigin: node.planId ? replayLabel(replay?.replayByNode?.get(node.planId)) : undefined,
          },
        };
      }),
    [geometry, progress, selectedId, toggle, collapsible, children, collapsed, fullGraph, visibleIds, replay?.checks, replay?.replayByNode],
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
        const membership = Boolean(grouped && link.kind === 'member');
        const edgeClass = !reached ? 'factory-graph-edge-upcoming' : current ? 'factory-graph-edge-current' : undefined;
        return {
          id: `graph-edge-${index}`,
          source: link.source,
          target: link.target,
          type: membership ? 'membership' : 'smoothstep',
          zIndex: membership ? 1 : undefined,
          className: edgeClass,
          label: link.kind === 'relation' || link.kind === 'superseded' ? linkText(link, text) : undefined,
          markerEnd: membership
            ? { type: MarkerType.ArrowClosed, width: 12, height: 12, color: 'var(--color-text-link)' }
            : { type: MarkerType.ArrowClosed, width: 17, height: 17 },
          style: link.kind === 'superseded' ? { strokeDasharray: '5 4' } : undefined,
        };
      }),
    [geometry.links, grouped, progress, text, visibleLinks],
  );
  const selected = fullGraph.nodes.find((node) => node.id === selectedId);
  const selectedProgress = selected ? progress?.get(selected.id) : undefined;
  const showReplayLegend = Boolean(replay && graph.kind !== 'ontology');
  if (!nodes.length)
    return (
      <p className="factory-graph-empty" data-testid="factory-runs-graph-empty">
        {text.empty}
      </p>
    );

  return (
    <section
      ref={view}
      className="factory-graph-view"
      aria-label={text.title[graph.kind]}
      data-testid="factory-runs-graph"
    >
      <div className="factory-graph-summary">
        <strong data-testid="factory-runs-graph-title">{text.title[graph.kind]}</strong>
        <span data-testid="factory-runs-graph-count">
          {graph.nodes.length}
          {graph.nodes.length !== fullGraph.nodes.length ? ` / ${fullGraph.nodes.length}` : ''} {text.nodeCount} ·{' '}
          {graph.links.length} {text.linkCount}
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
      <div className="factory-graph-canvas" style={grouped ? { height: grouped.height + 2 } : undefined}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          elevateNodesOnSelect={!grouped}
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
          zoomOnScroll={!grouped}
          preventScrolling={!grouped}
          fitView={!grouped}
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
          {replay && !grouped && (
            <FocusCurrent
              ids={graph.nodes
                .filter((node) => progress?.get(node.id)?.phase === 'current')
                .map((node) => node.id)
                .join('|')}
            />
          )}
          <ZoomControls
            grouped={Boolean(grouped)}
            onExpandAll={collapsible ? () => setCollapsed(new Set()) : undefined}
            onCollapseAll={collapsible ? () => setCollapsed(collapsibleNodes(fullGraph)) : undefined}
          />
        </ReactFlow>
        {selected && (
          <NodeDetails
            node={selected}
            details={selectedProgress?.details ?? selected.details}
            phase={selectedProgress?.phase}
            links={[...visibleLinks]}
            nodeLabels={nodeLabels}
            onClose={() => setSelectedId('')}
            replay={replay}
          />
        )}
      </div>
    </section>
  );
}
