import { useLayoutEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { BoundCapsules } from '../cc/BoundCapsules';
import type { TaskGraphTimelineNode } from './graphModel';
import './demoTaskChain.css';

const minCardWidth = 140;

export function DemoTaskChain({
  nodes,
  selectedNode,
  onOpenNode,
}: {
  nodes: readonly TaskGraphTimelineNode[];
  selectedNode?: string;
  onOpenNode: (id: string) => void;
}) {
  const { t } = useTranslation();
  const list = useRef<HTMLOListElement>(null);
  const [columns, setColumns] = useState(1);
  const hasNodes = nodes.length > 0;

  useLayoutEffect(() => {
    const container = list.current;
    if (!container) return;
    const gap = parseFloat(getComputedStyle(container).columnGap);
    const measure = (width: number) => setColumns(Math.max(1, Math.floor((width + gap) / (minCardWidth + gap))));
    measure(container.clientWidth);
    const observer = new ResizeObserver(([entry]) => measure(entry.contentRect.width));
    observer.observe(container);
    return () => observer.disconnect();
  }, [hasNodes]);

  if (!hasNodes) {
    return <p data-testid="factory-runs-demo-task-chain-empty">{t('factoryRuns.demoTaskChain.empty')}</p>;
  }

  const rows = Math.ceil(nodes.length / columns);
  const tracks = Math.ceil(nodes.length / rows);
  return (
    <ol
      ref={list}
      className="factory-demo-task-chain"
      dir="ltr"
      role="list"
      aria-label={t('factoryRuns.graph')}
      data-testid="factory-runs-demo-task-chain"
      style={{ gridTemplateColumns: `repeat(${tracks}, minmax(0, 1fr))` }}
    >
      {nodes.map((node, index) => {
        const id = node.planId ?? node.id;
        const row = Math.floor(index / tracks);
        const offset = index % tracks;
        const forward = row % 2 === 0;
        const column = forward ? offset + 1 : tracks - offset;
        const arrow =
          index === nodes.length - 1 ? undefined : offset + 1 === tracks ? 'down' : forward ? 'right' : 'left';
        return (
          <li
            key={node.id}
            className="factory-demo-task-card"
            style={{ gridRow: row + 1, gridColumn: column }}
            data-arrow={arrow}
            data-testid="factory-runs-demo-task-card"
            data-variant={id}
          >
            <button
              type="button"
              className="factory-demo-task-node"
              data-testid="factory-runs-demo-task-node"
              data-variant={id}
              data-graph-state={node.replayState}
              aria-current={node.replayState === 'current' ? 'step' : undefined}
              aria-expanded={selectedNode === id}
              onClick={() => onOpenNode(id)}
            >
              <strong>{node.planId ?? node.label}</strong>
              <span className="factory-demo-task-state" data-testid="factory-runs-demo-task-node-status">
                {t(`factoryRuns.demoTaskChain.state.${node.replayState}`)}
              </span>
            </button>
            <BoundCapsules ids={node.boundCCs} compact />
          </li>
        );
      })}
    </ol>
  );
}
