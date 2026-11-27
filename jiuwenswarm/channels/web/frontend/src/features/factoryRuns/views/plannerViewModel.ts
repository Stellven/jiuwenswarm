import type { PlannerNode, PlannerPlan } from '../api';

export function draftChain(plan?: PlannerPlan | null) {
  const nodes = new Map(plan?.nodes.map((node) => [node.node_id, node]));
  return (plan?.plan_order ?? []).flatMap((id) => {
    const node = nodes.get(id);
    return node ? [node] : [];
  });
}

export function comparisonDraft(node?: PlannerNode, finalIndex?: number) {
  const final = finalIndex === undefined ? node?.finals.at(-1) : node?.finals[finalIndex];
  // A different draft from the planner's first graph can have a different digest.
  // When reviewing a finalization, only show the draft tied to that final.
  return {
    final,
    draft: final ? final.preliminary : node?.draft,
    source: final ? final.preliminary_source : node?.draft_source,
  };
}
