import { useMemo, useState } from 'react';
import { chartRows, formatKey, type ChartSource } from './dataModel';
import { useViewerLabels } from './viewerLabels';

const BAR_PAGE_SIZE = 24;

export function ArtifactChart({ charts }: { charts: ChartSource[] }) {
  const { label } = useViewerLabels();
  const [path, setPath] = useState(charts[0].table.path);
  const source = charts.find((chart) => chart.table.path === path) ?? charts[0];
  return (
    <div className="evidence-section" data-testid="factory-runs-data-chart">
      {charts.length > 1 && (
        <select
          aria-label={label('chooseTable')}
          data-testid="factory-runs-chart-select"
          value={source.table.path}
          onChange={(event) => setPath(event.target.value)}
        >
          {charts.map((chart) => (
            <option key={chart.table.path} value={chart.table.path}>
              {chart.table.path || label('root')}
            </option>
          ))}
        </select>
      )}
      <ChartBars key={source.table.path} source={source} />
    </div>
  );
}

function ChartBars({ source }: { source: ChartSource }) {
  const { label, lang } = useViewerLabels();
  const [metric, setMetric] = useState(source.metrics[0]);
  const [page, setPage] = useState(0);
  const selectedMetric = source.metrics.includes(metric) ? metric : source.metrics[0];
  const rows = useMemo(() => chartRows(source, selectedMetric), [source, selectedMetric]);
  const scale = rows.reduce((max, row) => Math.max(max, Math.abs(row.value)), 0) || 1;
  const min = rows.reduce((value, row) => Math.min(value, row.value / scale), 0);
  const max = rows.reduce((value, row) => Math.max(value, row.value / scale), 0);
  const range = max - min || 1;
  const baseline = (-min / range) * 100;
  const from = page * BAR_PAGE_SIZE;
  const locale = new Intl.NumberFormat(lang, { maximumSignificantDigits: 8 });
  return (
    <>
      <label className="evidence-chart-metric">
        {label('metric')}
        <select
          data-testid="factory-runs-chart-metric"
          value={selectedMetric}
          onChange={(event) => {
            setMetric(event.target.value);
            setPage(0);
          }}
        >
          {source.metrics.map((key) => (
            <option key={key} value={key}>
              {formatKey(key)}
            </option>
          ))}
        </select>
      </label>
      <ul className="evidence-chart-rows" aria-label={formatKey(selectedMetric)} data-testid="factory-runs-chart-rows">
        {rows.slice(from, from + BAR_PAGE_SIZE).map((row, index) => {
          const width = (Math.abs(row.value / scale) / range) * 100;
          return (
            <li key={from + index} data-testid="factory-runs-chart-row" data-variant={row.label}>
              <span>{row.label}</span>
              <span className="evidence-chart-track" aria-hidden="true">
                <span className="evidence-chart-baseline" style={{ left: `${baseline}%` }} />
                <span
                  className="evidence-chart-bar"
                  data-negative={row.value < 0}
                  style={{ left: `${row.value < 0 ? baseline - width : baseline}%`, width: `${width}%` }}
                />
              </span>
              <strong title={String(row.value)}>{locale.format(row.value)}</strong>
            </li>
          );
        })}
      </ul>
      {rows.length > BAR_PAGE_SIZE && (
        <div className="evidence-pagination" data-testid="factory-runs-chart-pagination">
          <button
            type="button"
            disabled={!page}
            onClick={() => setPage(page - 1)}
            data-testid="factory-runs-chart-previous"
          >
            {label('previous')}
          </button>
          <output>
            {from + 1}–{Math.min(from + BAR_PAGE_SIZE, rows.length)} / {rows.length}
          </output>
          <button
            type="button"
            disabled={from + BAR_PAGE_SIZE >= rows.length}
            onClick={() => setPage(page + 1)}
            data-testid="factory-runs-chart-next"
          >
            {label('next')}
          </button>
        </div>
      )}
    </>
  );
}
