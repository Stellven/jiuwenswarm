import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import type { JsonRecord } from './api';
import { aggregateMeasurements, gapScale } from './measurementModel';

function format(value: number | null) {
  return value === null ? '—' : value.toFixed(3);
}
export function Measurements({
  observations,
  onOpenEvidence,
}: {
  observations: JsonRecord[];
  onOpenEvidence: (artifact: string) => void;
}) {
  const { t } = useTranslation();
  const rows = useMemo(() => aggregateMeasurements(observations), [observations]);
  const scale = gapScale(rows);
  return (
    <section data-testid="factory-runs-measurements">
      <p className="factory-muted" data-testid="factory-runs-gap-formula">
        {t('factoryRuns.gapFormula')}
      </p>
      <p className="factory-muted" data-testid="factory-runs-measurement-method">
        {t('factoryRuns.measurementMethod')}
      </p>
      <p className="factory-muted" data-testid="factory-runs-memory-method">
        {t('factoryRuns.memoryMethod')}
      </p>
      <div className="factory-table-scroll">
        <table className="factory-measurements" data-testid="factory-runs-measurement-table">
          <thead>
            <tr>
              {[
                'arm',
                'promptTokens',
                'repeats',
                'ttft',
                'range',
                'decode',
                'outputHashes',
                'memory',
                'available',
                'loadTime',
                'inverseA',
                'inverseAplus',
                'gapClosed',
                'sources',
              ].map((key) => (
                <th key={key}>{t(`factoryRuns.${key}`)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={`${row.arm}-${row.prompt}`}
                data-testid="factory-runs-measurement-row"
                data-variant={`${row.arm}-${row.prompt}`}
                title={row.sources.join('\n')}
              >
                <td>{row.arm}</td>
                <td>{row.prompt}</td>
                <td>{row.count}</td>
                <td>{format(row.ttft)}</td>
                <td>
                  {format(row.ttftMin)}–{format(row.ttftMax)}
                </td>
                <td>{format(row.decode)}</td>
                <td>{row.outputHashes || '—'}</td>
                <td>{format(row.memory === null ? null : row.memory / 2 ** 30)}</td>
                <td>{format(row.available === null ? null : row.available / 2 ** 30)}</td>
                <td>{format(row.load)}</td>
                <td>{format(row.inverseA)}</td>
                <td>{format(row.inverseAplus)}</td>
                <td>{row.gap === null ? t('factoryRuns.undefined') : `${(row.gap * 100).toFixed(1)}%`}</td>
                <td>
                  {row.artifacts.map((id, index) => (
                    <button
                      key={id}
                      data-testid="factory-runs-measurement-source"
                      data-variant={id}
                      onClick={() => onOpenEvidence(id)}
                      title={id}
                    >
                      {index + 1}
                    </button>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows.length && <p data-testid="factory-runs-measurements-empty">{t('factoryRuns.noEvidence')}</p>}
      <div className="factory-gap-chart" data-testid="factory-runs-gap-chart">
        {rows.map((row) => (
          <div key={`${row.arm}-${row.prompt}`}>
            <span>
              {row.arm} · {row.prompt}
            </span>
            <div className="factory-gap-track">
              <i style={{ left: `${scale.zero}%` }} />
              {row.gap !== null && (
                <span
                  style={{
                    left: `${Math.min(scale.zero, scale.position(row.gap))}%`,
                    width: `${Math.abs(scale.position(row.gap) - scale.zero)}%`,
                  }}
                />
              )}
            </div>
            <span>{row.gap === null ? t('factoryRuns.undefined') : `${(row.gap * 100).toFixed(1)}%`}</span>
          </div>
        ))}
      </div>
      {rows.some((row) => row.gap === null) && (
        <p className="factory-muted" data-testid="factory-runs-gap-undefined">
          {t('factoryRuns.gapUndefined')}
        </p>
      )}
    </section>
  );
}
