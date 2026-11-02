import type { CcNode } from './ccTypes';

/** Keep ancestors when filtering; failed/declined nodes are never status-filtered. */
export function ccLineage(nodes: CcNode[], runId?: string, currentOnly = false) {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const included = new Set<string>();
  for (const node of nodes) {
    if (currentOnly && node.run_id !== runId && node.run_id !== null) continue;
    let current: CcNode | undefined = node;
    while (current && !included.has(current.id)) {
      included.add(current.id);
      current = current.parent_id ? byId.get(current.parent_id) : undefined;
    }
  }
  const result: { node: CcNode; depth: number }[] = [];
  const visited = new Set<string>();
  const visit = (node: CcNode, depth: number) => {
    if (!included.has(node.id) || visited.has(node.id)) return;
    visited.add(node.id);
    result.push({ node, depth });
    for (const child of nodes) if (child.parent_id === node.id) visit(child, depth + 1);
  };
  for (const node of nodes) if (!node.parent_id || !byId.has(node.parent_id)) visit(node, 0);
  // Defensive finite fallback if a malformed upstream graph arrives.
  for (const node of nodes) visit(node, 0);
  return result;
}
