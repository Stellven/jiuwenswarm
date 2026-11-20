import type { GraphModel, GraphNode } from './graphModel';

export type GraphPlacement = {
  node: GraphNode;
  position: { x: number; y: number };
  width: number;
  height: number;
  parentId?: string;
  grouped?: boolean;
};

const GUTTER = 12;
const CONTROL_ROW = 40;
const HEADER = 40;
const MEMBER = 42;
const STEP = MEMBER + 5;

export function layoutOntologyGroups(graph: GraphModel, width: number) {
  if (graph.kind !== 'ontology') return null;
  const groups = graph.nodes.filter((node) => node.kind === 'group');
  const entities = new Map(graph.nodes.filter((node) => node.kind === 'entity').map((node) => [node.id, node]));
  if (!groups.length || graph.links.length !== entities.size) return null;

  const members = new Map(groups.map((group) => [group.id, [] as GraphNode[]]));
  for (const link of graph.links) {
    const children = members.get(link.source);
    const entity = entities.get(link.target);
    if (link.kind !== 'member' || !children || !entity) return null;
    children.push(entity);
    entities.delete(link.target);
  }

  const columns = Math.min(groups.length, 3, Math.max(1, Math.floor((width - GUTTER) / 242)));
  const columnWidth = Math.max(156, (width - GUTTER * (columns + 1)) / columns);
  const placement: GraphPlacement[] = [];
  let y = CONTROL_ROW + GUTTER;
  for (let row = 0; row < groups.length; row += columns) {
    const rowGroups = groups.slice(row, row + columns);
    let rowHeight = 0;
    rowGroups.forEach((group, column) => {
      const children = members.get(group.id) ?? [];
      const height = HEADER + children.length * STEP + 9;
      rowHeight = Math.max(rowHeight, height);
      placement.push({
        node: group,
        position: { x: GUTTER + column * (columnWidth + GUTTER), y },
        width: columnWidth,
        height,
        grouped: true,
      });
      children.forEach((node, index) => {
        placement.push({
          node,
          position: { x: 35, y: HEADER + index * STEP },
          width: columnWidth - 44,
          height: MEMBER,
          parentId: group.id,
        });
      });
    });
    y += rowHeight + GUTTER;
  }
  return { placement, links: graph.links, height: y };
}
