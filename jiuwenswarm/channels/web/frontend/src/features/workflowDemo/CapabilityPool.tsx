import type { FactoryCatalog, FactoryNode, FactoryRun, WorkflowLibrary } from './factoryClient';
import { nodePoolRef, stageLabel } from './presentationModel';

export function CapabilityPool({
  catalog,
  nodes,
  selected,
  onSelect,
  onRefresh,
  library,
}: {
  catalog: FactoryCatalog | null;
  nodes: FactoryNode[];
  selected: string;
  onSelect: (id: string, fullRef?: string) => void;
  onRefresh: () => void;
  run: FactoryRun | null;
  library?: WorkflowLibrary | null;
}) {
  if (library) {
    const selectedRefs = new Set(nodes.map(nodePoolRef).filter(Boolean));
    return (
      <section
        className="wd-panel wd-pool"
        aria-label="Existing internal-stage pool"
        data-testid="workflow-demo-pool"
        data-library-schema={library.schema}
      >
        <div className="wd-panel-heading">
          <h2 data-testid="workflow-demo-pool-title">Existing internal-stage pool</h2>
          <button type="button" onClick={onRefresh} data-testid="workflow-demo-refresh-pool">
            Refresh
          </button>
        </div>
        <div className="wd-pool-scroll">
          {library.workflows.map((workflow) => (
            <section
              key={workflow.id}
              className="wd-workflow-group"
              data-testid="workflow-demo-workflow-group"
              data-variant={workflow.id}
            >
              <h3>{workflow.name}</h3>
              <div className="wd-pool-stages">
                {workflow.subworkflows.map((instance) => {
                  const definition = library.subworkflows.find((item) => item.id === instance.definition);
                  if (!definition) return null;
                  const parentRef = `${workflow.id}/${instance.id}`;
                  return (
                    <div
                      className="wd-pool-subworkflow"
                      key={parentRef}
                      data-testid="workflow-demo-pool-subworkflow"
                      data-variant={parentRef}
                    >
                      <span data-testid="workflow-demo-pool-subworkflow-label">{definition.name}</span>
                      <div>
                        {definition.stages.map((child) => {
                          const fullRef = `${parentRef}/${child.id}`;
                          const declaration = catalog?.stages.find((item) => item.id === child.stage_id);
                          return (
                            <button
                              type="button"
                              key={fullRef}
                              className="wd-pool-card"
                              aria-label={`${workflow.name} / ${definition.name} / ${declaration?.name || child.id}`}
                              data-testid="workflow-demo-pool-card"
                              data-variant={fullRef}
                              data-stage-id={child.stage_id}
                              data-selection={selectedRefs.has(fullRef) ? 'selected' : 'idle'}
                              aria-pressed={selected === fullRef}
                              onClick={() => onSelect(child.stage_id, fullRef)}
                            >
                              {stageLabel(declaration || { id: child.stage_id, name: child.id })}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      </section>
    );
  }
  const groups = catalog?.groups ?? [];
  return (
    <section className="wd-panel wd-pool" aria-label="Recorded stage declarations" data-testid="workflow-demo-pool">
      <div className="wd-panel-heading">
        <h2 data-testid="workflow-demo-pool-title">Recorded stage declarations</h2>
        <button type="button" onClick={onRefresh} data-testid="workflow-demo-refresh-pool">
          Refresh
        </button>
      </div>
      <div className="wd-pool-scroll">
        {groups.map((group) => (
          <section
            className="wd-workflow-group"
            key={group.id}
            data-testid="workflow-demo-workflow-group"
            data-variant={group.id}
            data-selection={nodes.some((node) => node.workflow_id === group.id) ? 'selected' : 'idle'}
          >
            <h3>{group.name}</h3>
            <div className="wd-pool-stages" data-testid="workflow-demo-pool-group" data-variant={group.id}>
              {catalog?.subworkflows
                .filter((item) => item.workflow_id === group.id)
                .map((subworkflow) => (
                  <div
                    className="wd-pool-subworkflow"
                    key={subworkflow.id}
                    data-testid="workflow-demo-pool-subworkflow"
                    data-variant={subworkflow.id}
                  >
                    <span data-testid="workflow-demo-pool-subworkflow-label">{subworkflow.name}</span>
                    <div>
                      {subworkflow.stages.map((stage) => (
                        <button
                          type="button"
                          key={stage.id}
                          className="wd-pool-card"
                          aria-label={`${group.name} / ${subworkflow.name} / ${stage.name}`}
                          data-testid="workflow-demo-pool-card"
                          data-variant={stage.id}
                          aria-pressed={selected === stage.id}
                          data-selection={nodes.some((node) => node.stage_id === stage.id) ? 'selected' : 'idle'}
                          onClick={() => onSelect(stage.id)}
                        >
                          {stageLabel(stage)}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}
