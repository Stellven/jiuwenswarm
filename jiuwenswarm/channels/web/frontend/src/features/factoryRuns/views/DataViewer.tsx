import { createContext, useContext, useDeferredValue, useMemo, useState } from 'react';
import type { EvidenceFile } from '../api';
import {
  chartableTable,
  collectTables,
  filterTree,
  formatKey,
  inspectDocument,
  inspectValue,
  isRecord,
  sortRows,
  treeEntries,
  type StructuredValue,
  type TableSource,
  type TreeEntry,
} from './dataModel';
import { ArtifactChart } from './ArtifactChart';
import { EvidenceMetadata } from './EvidenceMetadata';
import { RawDocument } from './RawDocument';
import { detectGraph, type GraphModel, type GraphReplay } from './graphModel';
import { GraphViewer } from './GraphViewer';
import { useViewerLabels } from './viewerLabels';
import './dataViewer.css';

type Mode = 'readable' | 'tree' | 'table' | 'chart' | 'graph' | 'raw';
type Props = {
  name: string;
  file?: EvidenceFile;
  graph?: GraphModel | null;
  replay?: GraphReplay;
  initialMode?: Mode;
} & ({ value: unknown; source?: never } | { value?: never; source: string });

const PAGE_SIZE = 48;
const DisplayLocale = createContext<{ empty: string; fields: string; items: string; count: Intl.NumberFormat } | null>(
  null,
);

function Value({ value, limit = 600 }: { value: StructuredValue | undefined; limit?: number }) {
  const locale = useContext(DisplayLocale)!;
  if (value === undefined) return <span className="evidence-muted">—</span>;
  if (value === null) return <code className="evidence-muted">null</code>;
  if (typeof value === 'object') {
    const array = Array.isArray(value);
    const count = array ? value.length : Object.keys(value).length;
    return (
      <span className="evidence-muted">
        {locale.count.format(count)} {array ? locale.items : locale.fields}
      </span>
    );
  }
  if (typeof value === 'string') {
    return value === '' ? (
      <span className="evidence-muted">{locale.empty}</span>
    ) : (
      <span className="evidence-value">{value.length > limit ? value.slice(0, limit) + '…' : value}</span>
    );
  }
  return <code className="evidence-scalar">{String(value)}</code>;
}

function EntryList({
  entries,
  readable,
  searching = false,
}: {
  entries: TreeEntry[];
  readable: boolean;
  searching?: boolean;
}) {
  const { label } = useViewerLabels();
  const [limit, setLimit] = useState(PAGE_SIZE);
  if (!entries.length) return <p className="evidence-muted">{label(searching ? 'noResults' : 'empty')}</p>;
  const visible = entries.slice(0, limit);
  return (
    <>
      <ul
        className={readable ? 'evidence-cards' : 'evidence-tree'}
        data-testid={readable ? 'factory-runs-data-cards' : 'factory-runs-data-tree-list'}
      >
        {visible.map((entry) => (
          <li key={entry.path} data-testid="factory-runs-data-entry" data-variant={entry.path}>
            <Entry entry={entry} readable={readable} searching={searching} />
          </li>
        ))}
      </ul>
      {limit < entries.length && (
        <button
          className="evidence-more"
          type="button"
          data-testid="factory-runs-data-show-more"
          onClick={() => setLimit(limit + PAGE_SIZE)}
        >
          {label('showMore')} · {entries.length - limit}
        </button>
      )}
    </>
  );
}

function Entry({ entry, readable, searching }: { entry: TreeEntry; readable: boolean; searching: boolean }) {
  const [open, setOpen] = useState(false);
  const key = <strong title={entry.key}>{readable ? formatKey(entry.key) : entry.key || '""'}</strong>;
  const value = <Value value={entry.value} />;
  if (!entry.children.length)
    return (
      <div className="evidence-entry">
        {key}
        {value}
      </div>
    );
  return (
    <details
      open={searching || open}
      onToggle={(event) => {
        if (!searching) setOpen(event.currentTarget.open);
      }}
    >
      <summary className="evidence-entry" data-testid="factory-runs-data-expand" data-variant={entry.path}>
        {key}
        {value}
      </summary>
      {(searching || open) && <EntryList entries={entry.children} readable={false} searching={searching} />}
    </details>
  );
}

function DataTree({ entries, value }: { entries: TreeEntry[]; value: StructuredValue }) {
  const { label } = useViewerLabels();
  const [query, setQuery] = useState('');
  const search = useDeferredValue(query.trim());
  const matches = useMemo(() => filterTree(entries, search), [entries, search]);
  return (
    <div className="evidence-section" data-testid="factory-runs-data-tree">
      <input
        className="evidence-search"
        type="search"
        placeholder={label('search')}
        aria-label={label('search')}
        data-testid="factory-runs-data-tree-search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {entries.length ? (
        <EntryList key={search} entries={matches} readable={false} searching={Boolean(search)} />
      ) : search && !String(value).toLocaleLowerCase().includes(search.toLocaleLowerCase()) ? (
        <p className="evidence-muted">{label('noResults')}</p>
      ) : (
        <Value value={value} />
      )}
    </div>
  );
}

function DataTable({ tables }: { tables: TableSource[] }) {
  const { label } = useViewerLabels();
  const [path, setPath] = useState(tables[0].path);
  const table = tables.find((item) => item.path === path) ?? tables[0];
  return (
    <div className="evidence-section" data-testid="factory-runs-data-table">
      {tables.length > 1 && (
        <select
          aria-label={label('chooseTable')}
          data-testid="factory-runs-data-table-select"
          value={table.path}
          onChange={(event) => setPath(event.target.value)}
        >
          {tables.map((item) => (
            <option
              key={item.path}
              value={item.path}
              data-testid="factory-runs-data-table-option"
              data-variant={item.path || 'root'}
            >
              {item.path || label('root')} · {item.rows.length}
            </option>
          ))}
        </select>
      )}
      <TableRows key={table.path} table={table} />
    </div>
  );
}

function TableRows({ table }: { table: TableSource }) {
  const { label, lang } = useViewerLabels();
  const [sort, setSort] = useState<{ column: string; descending: boolean }>();
  const [page, setPage] = useState(0);
  const [columnPage, setColumnPage] = useState(0);
  const rows = useMemo(
    () =>
      sort
        ? sortRows(table.rows, sort.column, sort.descending, new Intl.Collator(lang, { numeric: true }))
        : table.rows,
    [table.rows, sort, lang],
  );
  const rowStart = page * PAGE_SIZE;
  const columnStart = columnPage * PAGE_SIZE;
  const columns = table.columns.slice(columnStart, columnStart + PAGE_SIZE);
  return (
    <>
      {table.columns.length > PAGE_SIZE && (
        <Pagination position={columnPage} count={table.columns.length} onChange={setColumnPage} variant="columns" />
      )}
      <div className="evidence-table-scroll" tabIndex={0}>
        <table className="evidence-table">
          <thead>
            <tr>
              {columns.map((column) => {
                const active = sort?.column === column;
                return (
                  <th
                    key={column}
                    scope="col"
                    aria-sort={active ? (sort.descending ? 'descending' : 'ascending') : undefined}
                  >
                    <button
                      type="button"
                      data-testid="factory-runs-data-column-sort"
                      data-variant={column}
                      title={column}
                      onClick={() => {
                        setSort({ column, descending: active ? !sort.descending : false });
                        setPage(0);
                      }}
                    >
                      {formatKey(column)} {active && <span aria-hidden="true">{sort.descending ? '↓' : '↑'}</span>}
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.slice(rowStart, rowStart + PAGE_SIZE).map((row, index) => (
              <tr key={rowStart + index} data-testid="factory-runs-data-row" data-variant={rowStart + index}>
                {columns.map((column) => (
                  <td key={column} data-testid="factory-runs-data-cell" data-variant={column}>
                    <Value
                      value={Object.prototype.hasOwnProperty.call(row, column) ? row[column] : undefined}
                      limit={180}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > PAGE_SIZE ? (
        <Pagination position={page} count={rows.length} onChange={setPage} variant="rows" />
      ) : (
        <p className="evidence-muted">
          {rows.length} {label('items')}
        </p>
      )}
    </>
  );
}

function Pagination({
  position,
  count,
  onChange,
  variant,
}: {
  position: number;
  count: number;
  onChange: (position: number) => void;
  variant: 'rows' | 'columns';
}) {
  const { label } = useViewerLabels();
  return (
    <div className="evidence-pagination" data-testid="factory-runs-data-pagination" data-variant={variant}>
      <button
        type="button"
        disabled={!position}
        data-testid="factory-runs-data-previous"
        onClick={() => onChange(position - 1)}
      >
        {label('previous')}
      </button>
      <output>
        {position * PAGE_SIZE + 1}–{Math.min((position + 1) * PAGE_SIZE, count)} / {count}
      </output>
      <button
        type="button"
        disabled={(position + 1) * PAGE_SIZE >= count}
        data-testid="factory-runs-data-next"
        onClick={() => onChange(position + 1)}
      >
        {label('next')}
      </button>
    </div>
  );
}

export function DataViewer({ name, file, source, value, graph, replay, initialMode }: Props) {
  const { label, lang } = useViewerLabels();
  const locale = useMemo(
    () => ({
      empty: label('empty'),
      fields: label('fields'),
      items: label('items'),
      count: new Intl.NumberFormat(lang),
    }),
    [label, lang],
  );
  const [mode, setMode] = useState(initialMode);
  const raw = useMemo(() => source ?? JSON.stringify(value, null, 2) ?? '', [source, value]);
  const size = useMemo(() => file?.size ?? new TextEncoder().encode(raw).length, [file?.size, raw]);
  const document = useMemo(
    () => (source === undefined ? inspectValue(value) : inspectDocument(name, source)),
    [name, source, value],
  );
  const documentValue = 'value' in document ? document.value : undefined;
  const entries = useMemo(() => (documentValue === undefined ? [] : treeEntries(documentValue)), [documentValue]);
  const tables = useMemo(
    () => (documentValue === undefined ? [] : collectTables(documentValue, entries)),
    [documentValue, entries],
  );
  const charts = useMemo(
    () =>
      tables.flatMap((table) => {
        const chart = chartableTable(table);
        return chart ? [chart] : [];
      }),
    [tables],
  );
  const detectedGraph = useMemo(
    () => (graph === undefined ? detectGraph(document.format === 'mermaid' ? raw : documentValue) : graph),
    [graph, document.format, documentValue, raw],
  );

  const modes: Mode[] = [];
  if (documentValue !== undefined) modes.push('readable', 'tree');
  if (tables.length) modes.push('table');
  if (charts.length) modes.push('chart');
  if (detectedGraph) modes.push('graph');
  modes.push('raw');
  const activeMode = mode && modes.includes(mode) ? mode : detectedGraph ? 'graph' : modes[0];

  return (
    <DisplayLocale.Provider value={locale}>
      <section className="evidence-inspector" data-testid="factory-runs-data-viewer">
        <header className="evidence-toolbar">
          <div className="evidence-modes" role="group" aria-label={label('modes')}>
            {modes.map((item) => (
              <button
                type="button"
                key={item}
                data-testid={`factory-runs-data-mode-${item}`}
                aria-pressed={activeMode === item}
                onClick={() => setMode(item)}
              >
                {label(item)}
              </button>
            ))}
          </div>
          <EvidenceMetadata file={file} size={size} />
        </header>
        {'issue' in document && document.issue && (
          <p className="evidence-muted" role="status" data-testid="factory-runs-data-issue">
            {label(document.issue)}
          </p>
        )}
        {activeMode === 'readable' && documentValue !== undefined && (
          <div className="evidence-section" data-testid="factory-runs-data-readable">
            {entries.length ? (
              <EntryList entries={entries} readable={isRecord(documentValue)} />
            ) : (
              <Value value={documentValue} />
            )}
          </div>
        )}
        {activeMode === 'tree' && documentValue !== undefined && <DataTree entries={entries} value={documentValue} />}
        {activeMode === 'table' && <DataTable tables={tables} />}
        {activeMode === 'chart' && <ArtifactChart charts={charts} />}
        {activeMode === 'graph' && detectedGraph && <GraphViewer graph={detectedGraph} replay={replay} />}
        {activeMode === 'raw' && <RawDocument name={name} format={document.format} source={raw} />}
      </section>
    </DisplayLocale.Provider>
  );
}
