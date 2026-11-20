import { useState } from 'react';
import { Button } from '../../components/ui/Button/Button';
import { pretty } from './factoryClient';
import type { LibraryJob, LibraryPart } from './libraryClient';

const phases = ['Project input', 'Get the source', 'Create subworkflows', 'Save to Library'] as const;

type Props = {
  trace: LibraryJob;
  onPart: (part: LibraryPart) => void;
  onSource: (path: string) => void;
  onMaterial: (id: string) => void;
  onProcess: () => void;
};

export function LibraryImportReplay({ trace, onPart, onSource, onMaterial, onProcess }: Props) {
  const [phase, setPhase] = useState(0);
  const [selectedStep, setSelectedStep] = useState(0);
  const events = trace.events || [];
  const commands = events.filter((event) => event.type === 'import.command.completed');
  const creation = events.filter((event) => event.type === 'import.subworkflow.created');
  const registration = events.find((event) => event.type === 'library.workflow_registered');
  const partEvent = creation[selectedStep];
  const part = partEvent?.payload.subworkflow as LibraryPart | undefined;
  const sourceFiles = part?.source_evidence as { path: string; symbol?: string }[] | undefined;
  const materials = trace.materials || [];
  const evidence = part
    ? materials.filter((material) =>
        [`part.${part.id}.entrypoint`, `part.${part.id}.instruction`, `part.${part.id}.definition`].includes(
          material.id,
        ),
      )
    : [];
  const registeredParts = registration ? trace.workflow?.subworkflows || [] : [];
  const stop = events.find((event) => event.type === 'job.failed' || event.type === 'job.blocked');
  return (
    <section className="wl-import-replay" data-testid="workflow-demo-library-import-replay">
      <nav className="wl-import-stages" aria-label="Recorded import stages">
        {phases.map((name, index) => (
          <button
            key={name}
            type="button"
            aria-current={phase === index ? 'step' : undefined}
            onClick={() => setPhase(index)}
            data-testid="workflow-demo-library-import-stage"
            data-variant={index}
          >
            {name}
          </button>
        ))}
      </nav>
      {phase === 0 && (
        <section className="wl-import-action" data-testid="workflow-demo-library-import-input">
          <h3>Repository submitted</h3>
          <code>{String(trace.request?.repository_url || trace.workflow?.source.repository || '')}</code>
          {typeof trace.request?.revision === 'string' && <p>{trace.request.revision}</p>}
        </section>
      )}
      {phase === 1 && (
        <section className="wl-import-action" data-testid="workflow-demo-library-import-checkout">
          <h3>Source checked out</h3>
          {trace.workflow?.source.revision && <code>{trace.workflow.source.revision}</code>}
          <ol>
            {commands.map((event) => (
              <li key={event.sequence}>
                <code>
                  {Array.isArray(event.payload.argv) ? event.payload.argv.slice(0, 2).map(String).join(' ') : ''}
                </code>
                {' · Exit '}
                {String(event.payload.returncode)}
              </li>
            ))}
          </ol>
          <Button size="sm" onClick={onProcess} data-testid="workflow-demo-library-import-open-import-process">
            Open commands and output
          </Button>
        </section>
      )}
      {phase === 2 && (
        <section className="wl-import-action" data-testid="workflow-demo-library-import-breakdown">
          <h3>Turn source into reusable steps</h3>
          <div className="wl-actions">
            {creation.map((event, index) => (
              <Button
                key={event.sequence}
                size="sm"
                onClick={() => setSelectedStep(index)}
                aria-pressed={selectedStep === index}
                data-testid="workflow-demo-library-import-step"
                data-variant={index}
              >
                {(event.payload.subworkflow as LibraryPart).name}
              </Button>
            ))}
          </div>
          {part && (
            <div className="wl-import-source-step" data-testid="workflow-demo-library-import-source-to-step">
              <section>
                <h4>Original source</h4>
                {sourceFiles?.map((file) => (
                  <button
                    type="button"
                    className="wl-file-open"
                    key={file.path}
                    onClick={() => onSource(file.path)}
                    data-testid="workflow-demo-library-import-open-source"
                    data-variant={file.path}
                  >
                    {file.path.split('/').pop()}
                    {file.symbol ? ` · ${file.symbol}` : ''}
                  </button>
                ))}
              </section>
              <section>
                <h4>{part.name}</h4>
                <p>{part.implementation.type === 'agent' ? 'Agent instruction' : 'Python code'}</p>
                <div className="wl-actions">
                  {evidence.map((material) => (
                    <Button
                      size="sm"
                      key={material.id}
                      onClick={() => onMaterial(material.id)}
                      data-testid="workflow-demo-library-import-open-wrapper"
                      data-variant={material.id}
                    >
                      {material.kind === 'definition' ? 'Open step definition' : 'Open saved wrapper'}
                    </Button>
                  ))}
                </div>
              </section>
            </div>
          )}
          <p>Factory code defined the wrappers around these source files.</p>
        </section>
      )}
      {phase === 3 && (
        <section className="wl-import-action" data-testid="workflow-demo-library-import-registration">
          <h3>{registration ? `${trace.workflow?.name} saved to Library` : 'Registration has no recorded result'}</h3>
          <div className="wl-import-pieces">
            {registeredParts.map((item) => (
              <button
                type="button"
                key={item.id}
                onClick={() => onPart(item)}
                data-testid="workflow-demo-library-created-wrapper"
                data-variant={item.id}
              >
                <strong>{item.name}</strong>
                <span>{item.implementation.type === 'agent' ? 'Agent instruction' : 'Python code'}</span>
              </button>
            ))}
          </div>
          {registration && materials.some((material) => material.id === 'registered-workflow') && (
            <Button
              size="sm"
              onClick={() => onMaterial('registered-workflow')}
              data-testid="workflow-demo-library-open-registration"
            >
              Open registered workflow.json
            </Button>
          )}
        </section>
      )}
      {stop && <pre role="status">{pretty(stop.payload.error)}</pre>}
      <div className="wl-actions">
        <Button
          size="sm"
          onClick={() => setPhase(phase - 1)}
          disabled={phase === 0}
          data-testid="workflow-demo-library-import-previous"
        >
          Previous stage
        </Button>
        <Button
          size="sm"
          onClick={() => setPhase(phase + 1)}
          disabled={phase === phases.length - 1}
          data-testid="workflow-demo-library-import-next"
        >
          Next stage
        </Button>
      </div>
    </section>
  );
}
