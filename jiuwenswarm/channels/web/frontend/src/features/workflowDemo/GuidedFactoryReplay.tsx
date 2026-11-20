import { useEffect, useRef, useState } from 'react';
import { Button } from '../../components/ui/Button/Button';
import { factoryClient } from './factoryClient';
import { mountGuidedReplay } from './guidedReplay/mountGuidedReplay';

export function GuidedFactoryReplay() {
  const container = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const target = container.current;
    if (!target) return;

    const controller = new AbortController();
    let unmount: (() => void) | undefined;
    void factoryClient
      .guidedReplay(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        unmount = mountGuidedReplay(target, data);
        setStatus('ready');
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          target.replaceChildren();
          setStatus('error');
        }
      });

    return () => {
      controller.abort();
      unmount?.();
    };
  }, [attempt]);

  return (
    <section
      className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden"
      aria-busy={status === 'loading'}
      data-testid="workflow-demo-guided-replay"
      data-variant={status}
    >
      {status === 'loading' && (
        <p role="status" className="p-[var(--shell-pad)]" data-testid="workflow-demo-guided-replay-loading">
          Opening the recorded workflow.
        </p>
      )}
      {status === 'error' && (
        <div
          role="alert"
          className="space-y-2 p-[var(--shell-pad)]"
          data-testid="workflow-demo-guided-replay-error"
        >
          <p>The recorded workflow could not be opened.</p>
          <Button
            size="sm"
            onClick={() => {
              setStatus('loading');
              setAttempt((value) => value + 1);
            }}
            data-testid="workflow-demo-guided-replay-retry"
          >
            Retry
          </Button>
        </div>
      )}
      <div className="min-h-0 min-w-0 flex-1 overflow-y-auto" ref={container} />
    </section>
  );
}
