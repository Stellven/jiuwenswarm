import { useMemo } from 'react';
import { GitBranch, FileCode2 } from 'lucide-react';
import type { CcNode } from '../ccTypes';
import { ccLineage } from '../ccLineage';
import { nodeStatus, statusTone } from '../consoleModel';
import { ConsoleDialog } from './ConsoleDialog';

export function ConsoleLineage({
  nodes,
  selectedId,
  onSelect,
  onInspect,
  onClose,
}: {
  nodes: CcNode[];
  selectedId: string;
  onSelect: (id: string) => void;
  onInspect: () => void;
  onClose: () => void;
}) {
  const rows = useMemo(() => ccLineage(nodes), [nodes]);
  const selected = nodes.find((node) => node.id === selectedId);
  const positions = new Map<string, { x: number; y: number }>();
  const childRows = new Map<string, typeof rows>();
  for (const row of rows) {
    if (row.node.parent_id) childRows.set(row.node.parent_id, [...(childRows.get(row.node.parent_id) ?? []), row]);
  }
  let leaf = 0;
  for (const { node, depth } of rows) {
    if (!childRows.has(node.id)) positions.set(node.id, { x: depth * 260 + 24, y: leaf++ * 112 + 40 });
  }
  for (const { node, depth } of [...rows].reverse()) {
    if (positions.has(node.id)) continue;
    const children = (childRows.get(node.id) ?? []).flatMap((row) =>
      positions.has(row.node.id) ? [positions.get(row.node.id)!] : [],
    );
    positions.set(node.id, {
      x: depth * 260 + 24,
      y: children.length ? (children[0].y + children[children.length - 1].y) / 2 : leaf++ * 112 + 40,
    });
  }
  const activatedPath = new Set<string>();
  const byId = new Map(nodes.map((node) => [node.id, node]));
  for (const node of nodes.filter((item) => /^active$/i.test(item.activation_status))) {
    let current: CcNode | undefined = node;
    while (current && !activatedPath.has(current.id)) {
      activatedPath.add(current.id);
      current = current.parent_id ? byId.get(current.parent_id) : undefined;
    }
  }
  const width = Math.max(760, ...rows.map((row) => row.depth * 260 + 284));
  const height = Math.max(380, leaf * 112 + 80);
  return (
    <ConsoleDialog title="Capsule lineage" onClose={onClose}>
      <div className="rc-lineage-layout">
        <div className="rc-lineage-scroll" data-testid="rsi-console-lineage-tree">
          {rows.length === 0 ? (
            <p className="rc-empty">Lineage will appear when the engine publishes capsule nodes.</p>
          ) : (
            <div className="rc-lineage-canvas" style={{ width, height }}>
              <svg width={width} height={height} aria-hidden="true">
                {rows.map(({ node }) => {
                  const parent = node.parent_id ? positions.get(node.parent_id) : undefined;
                  const point = positions.get(node.id)!;
                  if (!parent) return null;
                  return (
                    <path
                      key={node.id}
                      className={activatedPath.has(node.id) ? 'rc-activated-path' : undefined}
                      d={`M${parent.x + 216},${parent.y + 37} C${parent.x + 238},${parent.y + 37} ${point.x - 22},${point.y + 37} ${point.x},${point.y + 37}`}
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    />
                  );
                })}
              </svg>
              {rows.map(({ node, depth }) => (
                <button
                  key={node.id}
                  className="rc-tree-node"
                  style={{ left: positions.get(node.id)!.x, top: positions.get(node.id)!.y }}
                  data-testid="rsi-console-lineage-node"
                  data-variant={node.id}
                  aria-pressed={selectedId === node.id}
                  onClick={() => onSelect(node.id)}
                >
                  <span className="rc-eyebrow">
                    GEN {depth} · {nodeStatus(node)}
                  </span>
                  <strong>{node.label}</strong>
                  <span className="rc-mono">{node.hash.slice(0, 12)}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <aside className="rc-lineage-inspector">
          <GitBranch size={22} />
          <h3>{selected?.label ?? 'Select a node'}</h3>
          {selected && (
            <>
              <span className={`rc-pill ${statusTone(nodeStatus(selected))}`}>{nodeStatus(selected)}</span>
              <dl className="rc-kv">
                <dt>Capsule</dt>
                <dd>{selected.target_id}</dd>
                <dt>Parent</dt>
                <dd>{selected.parent_id ?? 'Root'}</dd>
                <dt>Evaluation</dt>
                <dd>{selected.evaluation_status}</dd>
                <dt>Activation</dt>
                <dd>{selected.activation_status}</dd>
              </dl>
              <button className="rc-button" data-testid="rsi-console-lineage-inspect" onClick={onInspect}>
                <FileCode2 size={15} /> Inspect files
              </button>
              <p className="rc-hint">Branches and activation states come from recorded lineage.</p>
            </>
          )}
        </aside>
      </div>
    </ConsoleDialog>
  );
}
