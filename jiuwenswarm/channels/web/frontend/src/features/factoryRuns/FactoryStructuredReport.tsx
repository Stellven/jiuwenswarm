import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { isReportCell, reportTable } from './reportModel';

function ReportTable({ columns, rows }: NonNullable<ReturnType<typeof reportTable>>) {
  const { t } = useTranslation();
  const preview = rows.slice(0, 25);
  return (
    <div className="factory-report-table" data-testid="factory-runs-report-structured-table">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th scope="col" key={column}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {preview.map((row, index) => (
            <tr key={index} data-testid="factory-runs-report-structured-row" data-variant={index}>
              {columns.map((column) => (
                <td key={column}>{Object.prototype.hasOwnProperty.call(row, column) ? String(row[column]) : '—'}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {preview.length < rows.length && (
        <p className="factory-report-notice" data-testid="factory-runs-report-structured-preview">
          {t('factoryRuns.reportView.previewRows', { count: preview.length, total: rows.length })}
        </p>
      )}
    </div>
  );
}

function StructuredGroup({
  label,
  value,
  initiallyOpen,
  depth,
}: {
  label: string;
  value: unknown;
  initiallyOpen: boolean;
  depth: number;
}) {
  const [open, setOpen] = useState(initiallyOpen);
  return (
    <details
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
      data-testid="factory-runs-report-structured-group"
      data-variant={label}
    >
      <summary data-testid="factory-runs-report-structured-group-title" data-variant={label}>
        {label}
      </summary>
      {open && <StructuredValue value={value} depth={depth} />}
    </details>
  );
}

function StructuredValue({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (isReportCell(value)) return <code>{String(value)}</code>;
  if (!value || typeof value !== 'object' || depth >= 6) {
    return <pre className="factory-report-raw">{JSON.stringify(value, null, 2)}</pre>;
  }
  if (Array.isArray(value)) {
    if (!value.length) return <code>[]</code>;
    const table = reportTable(value);
    if (table) return <ReportTable {...table} />;
    if (value.length <= 25 && value.every(isReportCell)) {
      return (
        <ul className="factory-report-structured-list">
          {value.map((item, index) => (
            <li key={index}>{String(item)}</li>
          ))}
        </ul>
      );
    }
    return <pre className="factory-report-raw">{JSON.stringify(value, null, 2)}</pre>;
  }

  const fields = Object.entries(value);
  if (!fields.length) return <code>{'{}'}</code>;
  const scalars = fields.filter(([, item]) => isReportCell(item));
  const groups = fields.filter(([, item]) => !isReportCell(item));
  return (
    <div className="factory-report-structured-fields">
      {scalars.length > 0 && (
        <dl>
          {scalars.map(([label, item]) => (
            <div key={label} data-testid="factory-runs-report-structured-field" data-variant={label}>
              <dt>{label}</dt>
              <dd>
                <StructuredValue value={item} />
              </dd>
            </div>
          ))}
        </dl>
      )}
      {groups.map(([label, item]) => (
        <StructuredGroup
          key={label}
          label={label}
          value={item}
          initiallyOpen={groups.length === 1 && depth < 3}
          depth={depth + 1}
        />
      ))}
    </div>
  );
}

export function FactoryStructuredReport({ content }: { content: string }) {
  const { t } = useTranslation();
  const value: unknown = useMemo(() => {
    try {
      return JSON.parse(content);
    } catch {
      return undefined;
    }
  }, [content]);
  const raw = (
    <pre className="factory-report-raw" data-testid="factory-runs-report-structured-raw">
      {content}
    </pre>
  );
  if (value === undefined) return raw;

  return (
    <div className="factory-report-structured" data-testid="factory-runs-report-structured">
      <StructuredValue value={value} />
      <details className="factory-report-structured-source" data-testid="factory-runs-report-structured-source">
        <summary data-testid="factory-runs-report-structured-source-label">
          {t('factoryRuns.reportView.rawJson')}
        </summary>
        {raw}
      </details>
    </div>
  );
}
