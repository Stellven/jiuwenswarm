import type { EdgeProps } from '@xyflow/react';

export function MembershipEdge({ sourceX, sourceY, targetX, targetY, source, target, markerEnd }: EdgeProps) {
  return (
    <path
      className="react-flow__edge-path factory-graph-membership-edge"
      data-testid="factory-runs-graph-membership-edge"
      data-variant={`${source} → ${target}`}
      d={`M ${sourceX} ${sourceY} V ${targetY} H ${targetX}`}
      fill="none"
      markerEnd={markerEnd}
    />
  );
}
