import { Fragment, useMemo, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { CapsuleChips } from '../cc/CapsuleChips';
import type { Run } from '../api';
import { groupRunEntries, runListEntries } from './runListModel';
import { useViewerLabels } from './viewerLabels';

export function FactoryRunList({
  runs,
  selected,
  onSelect,
  engineViewer = false,
}: {
  runs: Run[];
  selected: string;
  onSelect: (id: string) => void;
  engineViewer?: boolean;
}) {
  const { t } = useTranslation();
  const { label, lang } = useViewerLabels();
  const entries = useMemo(() => runListEntries(runs), [runs]);
  const [showEverything, setShowEverything] = useState(false);
  const [showHidden, setShowHidden] = useState(false);
  const groups = useMemo(() => groupRunEntries(entries, showEverything), [entries, showEverything]);
  const date = useMemo(
    () =>
      new Intl.DateTimeFormat(lang, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23',
        timeZone: 'UTC',
      }),
    [lang],
  );

  return (
    <div className="factory-run-list" data-testid="factory-runs-list">
      {(() => {
        const render = (items: typeof entries): ReactNode => items.map(({ run, source, shortId }) => {
        const updated = Number.isFinite(run.updated) && run.updated > 0 ? new Date(run.updated * 1000) : null;
        const status =
          run.status === 'replay'
            ? label('runReplay')
            : run.status === 'live'
              ? label('runLive')
              : run.status || t('factoryRuns.recorded');
        return (
          <Fragment key={run.id}>
          <button
            type="button"
            className="factory-run"
            data-testid="factory-runs-run"
            data-variant={run.id}
            aria-pressed={run.id === selected}
            onClick={() => onSelect(run.id)}
          >
            <strong title={run.name} data-testid="factory-runs-run-name">
              {run.demo && <span className="factory-run-demo-badge" data-testid="factory-runs-run-demo">Demo</span>}
              {run.name}
            </strong>
            <span className="factory-run-meta">
              <span className="factory-run-kind" data-testid="factory-runs-run-kind" data-variant={run.kind}>
                {label(run.kind === 'bundle' ? 'runExport' : 'runHome')}
              </span>
              {updated && (
                <time
                  dateTime={updated.toISOString()}
                  title={updated.toISOString()}
                  data-testid="factory-runs-run-updated"
                >
                  {date.format(updated)} UTC
                </time>
              )}
              <span className="factory-run-status" data-testid="factory-runs-run-status">
                {status}
              </span>
            </span>
            {(source || shortId) && (
              <small
                className="factory-run-source"
                title={[source, shortId].filter(Boolean).join(' · ')}
                data-testid="factory-runs-run-source"
              >
                {[source, shortId].filter(Boolean).join(' · ')}
              </small>
            )}
          </button>
          <CapsuleChips value={[run.task_id,run.objective]} />
          </Fragment>
        );
      });
        if (engineViewer) {
          return (
            <>
              <section className="factory-run-group" data-testid="factory-runs-demo-group" aria-label="Demo">
                <h2 className="factory-run-group-title">Demo</h2>
                {render([...groups.demo, ...groups.featured])}
              </section>
              {groups.history.length > 0 && (
                <section className="factory-run-group" data-testid="factory-runs-history-group" aria-label="History">
                  <h2 className="factory-run-group-title">History</h2>
                  {render(groups.history)}
                </section>
              )}
            </>
          );
        }
        if (!groups.featured.length && !groups.history.length && !groups.demo.length) return render(entries);
        const selectedInRest = groups.rest.some(({ run }) => run.id === selected);
        return (
          <>
            {groups.featured.length > 0 && (
              <section className="factory-run-group" data-testid="factory-runs-featured-group" aria-label="Featured run">
                {render(groups.featured)}
              </section>
            )}
            {groups.history.length > 0 && (
              <section className="factory-run-group" data-testid="factory-runs-history-group" aria-label="Run history">
                <h2 className="factory-run-group-title">History</h2>
                {render(groups.history)}
              </section>
            )}
            {groups.demo.length > 0 && (
              <section className="factory-run-group" data-testid="factory-runs-demo-group" aria-label="Demo">
                <h2 className="factory-run-group-title">Demo</h2>
                {render(groups.demo)}
              </section>
            )}
            {groups.rest.length + groups.hidden > 0 && !(showHidden || selectedInRest) && (
              <button
                type="button"
                className="factory-run-hidden-toggle"
                data-testid="factory-runs-show-hidden"
                onClick={() => setShowHidden(true)}
              >
                {groups.rest.length + groups.hidden} other runs hidden · show
              </button>
            )}
            {groups.rest.length + groups.hidden > 0 && (showHidden || selectedInRest) && (
              <details className="factory-run-group" data-testid="factory-runs-all-group" open>
                <summary className="factory-run-group-title" data-testid="factory-runs-all-group-toggle">
                  All runs ({groups.rest.length})
                </summary>
                <label className="factory-run-show-all" data-testid="factory-runs-show-everything">
                  <input
                    type="checkbox"
                    checked={showEverything}
                    onChange={(event) => setShowEverything(event.target.checked)}
                  />
                  Show everything{groups.hidden ? ` (+${groups.hidden} scratch homes and older exports)` : ''}
                </label>
                {render(groups.rest)}
              </details>
            )}
          </>
        );
      })()}
      {!entries.length && <p data-testid="factory-runs-empty">{t('factoryRuns.empty')}</p>}
    </div>
  );
}
