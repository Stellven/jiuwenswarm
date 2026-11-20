import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import type { Run } from '../api';
import { runListEntries } from './runListModel';
import { useViewerLabels } from './viewerLabels';

export function FactoryRunList({
  runs,
  selected,
  onSelect,
}: {
  runs: Run[];
  selected: string;
  onSelect: (id: string) => void;
}) {
  const { t } = useTranslation();
  const { label, lang } = useViewerLabels();
  const entries = useMemo(() => runListEntries(runs), [runs]);
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
      {entries.map(({ run, source, shortId }) => {
        const updated = Number.isFinite(run.updated) && run.updated > 0 ? new Date(run.updated * 1000) : null;
        const status =
          run.status === 'replay'
            ? label('runReplay')
            : run.status === 'live'
              ? label('runLive')
              : run.status || t('factoryRuns.recorded');
        return (
          <button
            key={run.id}
            type="button"
            className="factory-run"
            data-testid="factory-runs-run"
            data-variant={run.id}
            aria-pressed={run.id === selected}
            onClick={() => onSelect(run.id)}
          >
            <strong title={run.name} data-testid="factory-runs-run-name">
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
        );
      })}
      {!entries.length && <p data-testid="factory-runs-empty">{t('factoryRuns.empty')}</p>}
    </div>
  );
}
