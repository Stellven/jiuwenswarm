import { useState } from 'react';
import { numericColumns, readableName, type DataRows } from './capsuleModel';
import { useCapsuleCopy } from './copy';

function renderValue(value: unknown) {
  if (value == null) return '—';
  if (typeof value === 'object') return <code>{JSON.stringify(value)}</code>;
  return String(value);
}

function AnalysisChart({ rows }: { rows: Record<string, unknown>[] }) {
  const copy = useCapsuleCopy();
  const metrics = numericColumns(rows);
  const [requested, setMetric] = useState('');
  const metric = metrics.includes(requested) ? requested : metrics[0];
  const values = rows.flatMap((row, index) => {
    const value = row[metric];
    const name = row.name ?? row.phase ?? row.label ?? row.region ?? row.key ?? row.arm;
    const category = name ?? row.k_per_layer ?? row.prompt_tokens;
    return typeof value === 'number'
      ? [{ value, name: typeof category === 'string' || typeof category === 'number' ? String(category) : String(index + 1), index }]
      : [];
  });
  const max = values.reduce((peak, { value }) => Math.max(peak, Math.abs(value)), 1e-12);
  const signed = values.some(({ value }) => value < 0);
  return (
    <div className="cc-chart" data-testid="factory-runs-capsule-chart">
      <label>
        {copy('metric')}
        <select
          value={metric}
          onChange={(event) => setMetric(event.target.value)}
          data-testid="factory-runs-capsule-chart-metric"
        >
          {metrics.map((column) => (
            <option key={column} value={column}>
              {readableName(column)}
            </option>
          ))}
        </select>
      </label>
      <ol>
        {values.map(({ name, value, index }) => (
          <li key={index} data-testid="factory-runs-capsule-chart-point" data-variant={name}>
            <span>{name}</span>
            <span className="cc-chart-track" data-signed={signed || undefined} aria-hidden>
              <span
                className="cc-chart-bar"
                data-negative={value < 0 || undefined}
                style={{ width: `${(Math.abs(value) / max) * (signed ? 50 : 100)}%`,
                  left: signed && value >= 0 ? '50%' : undefined, right: value < 0 ? '50%' : undefined }}
              />
            </span>
            <code>{value.toLocaleString(undefined, { maximumSignificantDigits: 6 })}</code>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function AnalysisData({ datasets, chart = false }: { datasets: DataRows[]; chart?: boolean }) {
  const copy = useCapsuleCopy();
  const eligible = chart ? datasets.filter(({ rows }) => rows.length > 1 && numericColumns(rows).length) : datasets;
  const [requested, setDataset] = useState(0);
  const { rows } = eligible[requested] ?? eligible[0];
  const [sortBy, setSortBy] = useState<{ column: string; desc: boolean }>();
  const columns = [...new Set(rows.flatMap(Object.keys))];
  const sorted =
    sortBy && columns.includes(sortBy.column)
      ? [...rows].sort((a, b) => {
          const left = a[sortBy.column];
          const right = b[sortBy.column];
          const comparison =
            typeof left === 'number' && typeof right === 'number'
              ? left - right
              : String(left ?? '').localeCompare(String(right ?? ''), undefined, { numeric: true });
          return sortBy.desc ? -comparison : comparison;
        })
      : rows;
  return (
    <>
      {eligible.length > 1 && (
        <label className="cc-dataset">
          {copy('dataset')}
          <select
            value={requested}
            onChange={(event) => setDataset(Number(event.target.value))}
            data-testid="factory-runs-capsule-dataset"
          >
            {eligible.map(({ path }, index) => (
              <option value={index} key={path}>
                {path || copy('all')}
              </option>
            ))}
          </select>
        </label>
      )}
      {chart ? (
        <AnalysisChart rows={rows} />
      ) : (
        <div className="cc-table-wrap" data-testid="factory-runs-capsule-analysis-table">
          <table className="cc-table">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th
                    key={column}
                    scope="col"
                    aria-sort={sortBy?.column === column ? (sortBy.desc ? 'descending' : 'ascending') : undefined}
                  >
                    <button
                      type="button"
                      className="cc-text-button"
                      onClick={() => setSortBy({ column, desc: sortBy?.column === column && !sortBy.desc })}
                      data-testid="factory-runs-capsule-sort-column"
                      data-variant={column}
                    >
                      {readableName(column)}
                      {sortBy?.column === column && <span aria-hidden>{sortBy.desc ? ' ↓' : ' ↑'}</span>}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((row, index) => (
                <tr key={index}>
                  {columns.map((column) => (
                    <td key={column}>{renderValue(row[column])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
