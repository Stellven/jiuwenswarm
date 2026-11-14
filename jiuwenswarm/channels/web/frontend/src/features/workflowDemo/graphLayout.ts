import type { Artifact, FactoryEdge, FactoryNode } from './factoryClient';
import { replayEdgeStatus } from './replayProjection.js';

export type EdgeDeliveryStatus = 'pending' | 'running' | 'verified' | 'failed';

/** Color a dependency only from its downstream attempt's actual published input binding. */
export function edgeDeliveryStatus(
  edge: FactoryEdge,
  nodes: FactoryNode[],
  publications?: Artifact[],
): EdgeDeliveryStatus {
  return replayEdgeStatus(edge, { nodes, artifacts: publications });
}

export interface NodePosition {
  x: number;
  y: number;
}

/** Layout only: every node and dependency comes from a backend snapshot. */
export function layoutGraph(nodes: FactoryNode[], edges: FactoryEdge[]) {
  const remaining = [...nodes];
  const ordered: FactoryNode[] = [];
  const visited = new Set<string>();
  while (remaining.length) {
    const next = remaining.findIndex((node) =>
      edges
        .filter((edge) => edge.to === node.id && nodes.some((n) => n.id === edge.from))
        .every((edge) => visited.has(edge.from)),
    );
    // Recovery control paths may form a visual cycle; they do not schedule work here.
    const [node] = remaining.splice(next < 0 ? 0 : next, 1);
    ordered.push(node);
    visited.add(node.id);
  }
  const positions: Record<string, NodePosition> = {};
  ordered.forEach((node, index) => {
    const row = Math.floor(index / 2);
    const column = row % 2 === 0 ? index % 2 : 1 - (index % 2);
    positions[node.id] = { x: column === 0 ? 180 : 620, y: 70 + row * 150 };
  });
  return { positions, height: Math.max(360, Math.ceil(ordered.length / 2) * 150) };
}

export function edgePath(from: NodePosition, to: NodePosition) {
  if (from.y === to.y) {
    const direction = to.x > from.x ? 1 : -1;
    return {
      d: `M${from.x + direction * 128} ${from.y} H${to.x - direction * 128}`,
      labelX: (from.x + to.x) / 2,
      labelY: from.y - 12,
    };
  }
  const downward = to.y > from.y;
  const startY = from.y + (downward ? 34 : -34);
  const endY = to.y + (downward ? -34 : 34);
  const middleY = (startY + endY) / 2;
  return {
    d: `M${from.x} ${startY} V${middleY} H${to.x} V${endY}`,
    labelX: from.x === to.x ? from.x + 58 : (from.x + to.x) / 2,
    labelY: middleY - 10,
  };
}
