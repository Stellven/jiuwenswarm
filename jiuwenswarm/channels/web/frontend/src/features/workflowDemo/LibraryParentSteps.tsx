import type { LibraryPart, LibraryWorkflow } from './libraryClient';
import { expectedFileForPort } from './libraryNarrative';

export function LibraryParentSteps({
  workflow,
  selected,
  onSelect,
}: {
  workflow: LibraryWorkflow;
  selected: string;
  onSelect: (part: LibraryPart) => void;
}) {
  const definition = workflow.composition;
  if (!definition) return null;
  const parts = new Map(workflow.subworkflows.map((part) => [part.id, part]));
  const byId = new Map(definition.nodes.map((node) => [node.id, node]));
  return (
    <section className="wl-parent-definition" data-testid="workflow-demo-library-parent-steps">
      <h4 data-testid="workflow-demo-library-parent-graph-title">Steps saved with {workflow.name}</h4>
      <ul className="wl-parent-step-list">
        {definition.nodes.map((node) => {
          const part = parts.get(node.part);
          if (!part) return null;
          return (
            <li key={node.id} data-testid="workflow-demo-library-parent-step" data-variant={node.id}>
              <button
                type="button"
                onClick={() => onSelect(part)}
                aria-pressed={selected === part.id}
                data-testid="workflow-demo-library-parent-step-open"
                data-variant={part.id}
              >
                {part.name}
                {node.optional ? ' (optional)' : ''}
              </button>
              {Object.entries(node.bindings).map(([port, binding]) => {
                const producerNode = byId.get(binding.node);
                const producer = producerNode ? parts.get(producerNode.part) : undefined;
                const file = expectedFileForPort(part, 'inputs', port) || port;
                const origin = binding.node === '$input' ? 'Supplied from outside this workflow' : producer?.name;
                return (
                  <p
                    key={port}
                    className="wl-parent-step-input"
                    data-testid="workflow-demo-library-parent-step-input"
                    data-variant={`${part.id}/${port}`}
                  >
                    Reads <code>{file}</code>
                    {origin && <> · {origin}</>}
                  </p>
                );
              })}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
