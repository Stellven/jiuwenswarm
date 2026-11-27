import { useLayoutEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { PlannerNode, PlannerPlan } from '../api';
import { BoundCapsules, type ActivityLink } from '../cc/BoundCapsules';
import type { TaskGraphTimelineNode } from './graphModel';
import { contractObjective, PlannerCapsules } from './PlannerEvidence';
import type { NodeExecutionFacts } from './ccActivityModel';
import { draftChain } from './plannerViewModel';
import { NodeVerifier } from './TimelineVerifier';
import './demoTaskChain.css';

const minCardWidth = 164;
export type DemoGraphMode = 'plan' | 'run';

function PlanExecution({
  execution,
  onOpenSource,
  onOpenRecord,
}: {
  execution?: NodeExecutionFacts;
  onOpenSource?: ActivityLink;
  onOpenRecord: (id: string) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return execution ? (
    <details
      className="factory-plan-execution"
      data-testid="factory-runs-plan-execution"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary data-testid="factory-runs-plan-execution-toggle">
        {t('factoryRuns.ccActivity.recordedExecution')}
      </summary>
      {open && (
        <>
          <BoundCapsules facts={execution.capsuleFacts} onOpenSource={onOpenSource} compact />
          <NodeVerifier result={execution.nodeVerifier} onOpenRecord={onOpenRecord} compact />
        </>
      )}
    </details>
  ) : null;
}
function ChangeBadge({ node }: { node?: PlannerNode }) {
  const { t } = useTranslation();
  if (!node || node.change === 'unchanged') return null;
  return (
    <span className="factory-demo-task-change" data-testid="factory-runs-demo-task-change" data-variant={node.change}>
      {t(`factoryRuns.planner.change.${node.change}`)}
    </span>
  );
}

export function DemoTaskChain({
  nodes,
  planner,
  mode,
  onModeChange,
  selectedNode,
  onOpenNode,
  onOpenDraft,
  onOpenPlan,
  onOpenRecord,
  onOpenActivity,
}: {
  nodes: readonly TaskGraphTimelineNode[];
  planner?: PlannerPlan | null;
  mode: DemoGraphMode;
  onModeChange: (mode: DemoGraphMode) => void;
  selectedNode?: string;
  onOpenNode: (id: string) => void;
  onOpenDraft: (id: string) => void;
  onOpenPlan: (path: string) => void;
  onOpenRecord: (id: string) => void;
  onOpenActivity?: ActivityLink;
}) {
  const { t } = useTranslation();
  const list = useRef<HTMLOListElement>(null);
  const [columns, setColumns] = useState(1);
  const planning = mode === 'plan';
  const plannerNodes = new Map(planner?.nodes.map((node) => [node.node_id, node]));
  const items = planning
    ? draftChain(planner).map((draft) => ({ id: draft.node_id, draft, run: undefined }))
    : nodes.map((run) => {
        const id = run.planId ?? run.id;
        return { id, draft: plannerNodes.get(id), run };
      });
  const executionByNode = new Map(nodes.map((node) => [node.planId ?? node.id, node]));
  const shown = new Set(items.map((item) => item.id));
  const outside =
    planner?.nodes.filter((node) => !shown.has(node.node_id) && node.change === (planning ? 'added' : 'removed')) ?? [];
  const hasNodes = items.length > 0;

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

  const rows = Math.max(1, Math.ceil(items.length / columns));
  const tracks = Math.ceil(items.length / rows);
  return (
    <>
      <div className="factory-demo-task-mode" data-testid="factory-runs-demo-task-mode" data-variant={mode}>
        <div role="group" aria-label={t('factoryRuns.graph')}>
          {(['plan', 'run'] as const).map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={mode === value}
              data-testid="factory-runs-demo-task-mode-option"
              data-variant={value}
              onClick={() => onModeChange(value)}
            >
              {t(`factoryRuns.planner.${value}`)}
            </button>
          ))}
        </div>
        {planning && planner && (
          <button
            type="button"
            data-testid="factory-runs-planner-open-plan"
            onClick={() => onOpenPlan(planner.artifact.path)}
          >
            {t('factoryRuns.planner.openPlan')}
          </button>
        )}
      </div>
      {!hasNodes ? (
        <p data-testid="factory-runs-demo-task-chain-empty">
          {t(planning && !planner ? 'factoryRuns.planner.noPlan' : 'factoryRuns.demoTaskChain.empty')}
        </p>
      ) : (
        <ol
          ref={list}
          className="factory-demo-task-chain"
          dir="ltr"
          role="list"
          aria-label={t('factoryRuns.graph')}
          data-testid="factory-runs-demo-task-chain"
          data-variant={mode}
          style={{ gridTemplateColumns: `repeat(${tracks}, minmax(0, 1fr))` }}
        >
          {items.map(({ id, draft, run }, index) => {
            const row = Math.floor(index / tracks);
            const offset = index % tracks;
            const forward = row % 2 === 0;
            const column = forward ? offset + 1 : tracks - offset;
            const arrow =
              index === items.length - 1 ? undefined : offset + 1 === tracks ? 'down' : forward ? 'right' : 'left';
            return (
              <li
                key={id}
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
                  data-graph-state={run?.replayState}
                  aria-current={run?.replayState === 'current' ? 'step' : undefined}
                  aria-expanded={planning ? undefined : selectedNode === id}
                  onClick={() => (planning ? onOpenDraft(id) : onOpenNode(id))}
                >
                  <strong>{planning ? (draft?.title ?? id) : (run?.planId ?? run?.label)}</strong>
                  {run && (
                    <span className="factory-demo-task-state" data-testid="factory-runs-demo-task-node-status">
                      {t(`factoryRuns.demoTaskChain.state.${run.replayState}`)}
                    </span>
                  )}
                </button>
                <ChangeBadge node={draft} />
                {planning && draft && (
                  <>
                    <p className="factory-demo-task-draft" data-testid="factory-runs-demo-task-draft">
                      {draft.draft ? contractObjective(draft.draft) : t('factoryRuns.planner.noDraft')}
                    </p>
                    {draft.draft && <PlannerCapsules ids={draft.suggested_ccs} kind="suggested" />}
                    <PlanExecution
                      execution={executionByNode.get(id)}
                      onOpenSource={onOpenActivity}
                      onOpenRecord={onOpenRecord}
                    />
                  </>
                )}
                {run && (
                  <>
                    <BoundCapsules facts={run.capsuleFacts} onOpenSource={onOpenActivity} compact />
                    <NodeVerifier result={run.nodeVerifier} onOpenRecord={onOpenRecord} compact />
                  </>
                )}
              </li>
            );
          })}
        </ol>
      )}
      {outside.length > 0 && (
        <section className="factory-demo-task-outside" data-testid="factory-runs-demo-task-outside">
          <h3>{t(planning ? 'factoryRuns.planner.added' : 'factoryRuns.planner.removed')}</h3>
          <ul role="list">
            {outside.map((node) => (
              <li key={node.node_id} data-testid="factory-runs-demo-task-outside-node" data-variant={node.node_id}>
                <button
                  type="button"
                  data-testid="factory-runs-demo-task-open-outside-draft"
                  onClick={() => onOpenDraft(node.node_id)}
                >
                  {node.title ?? node.node_id}
                </button>
                <ChangeBadge node={node} />
              </li>
            ))}
          </ul>
        </section>
      )}
      <p className="factory-cc-activity-legend" data-testid="factory-runs-cc-activity-legend">
        {t('factoryRuns.ccActivity.legend')}
      </p>
    </>
  );
}
