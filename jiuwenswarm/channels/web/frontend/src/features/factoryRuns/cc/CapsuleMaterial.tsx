import { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { factoryApi, type EvidenceFile } from '../api';
import { AnalysisData } from './AnalysisData';
import { capsuleApi, type CapsuleFile } from './capsuleApi';
import { isRecord, localMaterial, numericColumns, readableName, tableData } from './capsuleModel';
import { useCapsuleCopy } from './copy';
import { useCapsuleResource } from './useCapsuleResource';

export function Integrity({ state }: { state: EvidenceFile['integrity'] }) {
  const copy = useCapsuleCopy();
  return (
    <span
      className="cc-integrity"
      data-integrity={state}
      data-testid="factory-runs-capsule-integrity"
      data-variant={state}
    >
      <span aria-hidden>{state === 'verified' ? '✓' : state === 'untracked' ? '○' : '!'}</span> {copy(state)}
    </span>
  );
}

export function Loading({ error, retry }: { error?: string; retry: () => void }) {
  const copy = useCapsuleCopy();
  return error ? (
    <div className="cc-alert" role="alert" data-testid="factory-runs-capsule-load-state" data-variant="error">
      <span>{error}</span>
      <button type="button" className="cc-control" onClick={retry} data-testid="factory-runs-capsule-retry">
        {copy('retry')}
      </button>
    </div>
  ) : (
    <p className="cc-muted" role="status" data-testid="factory-runs-capsule-load-state" data-variant="loading">
      {copy('loading')}
    </p>
  );
}

export function SafeMarkdown({
  content,
  path,
  available,
  onOpen,
}: {
  content: string;
  path: string;
  available: Set<string>;
  onOpen: (path: string) => void;
}) {
  return (
    <div className="cc-markdown" data-testid="factory-runs-capsule-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          img: ({ alt }) => <span>{alt}</span>,
          a: ({ href, children }) => {
            const target = localMaterial(path, href || '', available);
            if (target)
              return (
                <button
                  className="cc-text-button"
                  type="button"
                  onClick={() => onOpen(target)}
                  data-testid="factory-runs-capsule-material-link"
                  data-variant={target}
                >
                  {children}
                </button>
              );
            if (href?.startsWith('https://'))
              return (
                <a href={href} target="_blank" rel="noreferrer" data-testid="factory-runs-capsule-external-link">
                  {children}
                </a>
              );
            return <span>{children}</span>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function scalar(value: unknown): string {
  return value === null ? 'null' : String(value);
}

function childrenOf(value: unknown): [string, unknown][] | undefined {
  if (Array.isArray(value)) return value.map((item, index) => [String(index), item]);
  if (isRecord(value)) return Object.entries(value);
  return undefined;
}

export function StructuredData({ value, tree = false, depth = 0 }: { value: unknown; tree?: boolean; depth?: number }) {
  const entries = depth < 32 ? childrenOf(value) : undefined;
  if (!entries) return <span>{scalar(value)}</span>;
  if (!entries.length) return <code>{Array.isArray(value) ? '[]' : '{}'}</code>;
  if (entries.every(([, item]) => !childrenOf(item)) && Array.isArray(value)) {
    return <span>{value.map(scalar).join(', ')}</span>;
  }
  return (
    <dl className={tree ? 'cc-tree' : 'cc-structured'} data-testid="factory-runs-capsule-structure">
      {entries.map(([key, item]) => (
        <div key={key} data-testid="factory-runs-capsule-structure-item" data-variant={key}>
          {tree && childrenOf(item) ? (
            <dd>
              <details open={depth === 0}>
                <summary data-testid="factory-runs-capsule-tree-branch" data-variant={key}>
                  {key}
                </summary>
                <StructuredData value={item} tree depth={depth + 1} />
              </details>
            </dd>
          ) : (
            <>
              <dt>{tree ? key : readableName(key)}</dt>
              <dd>
                <StructuredData value={item} tree={tree} depth={depth + 1} />
              </dd>
            </>
          )}
        </div>
      ))}
    </dl>
  );
}

export function MaterialList({
  files,
  onOpen,
  hashes = false,
}: {
  files: EvidenceFile[];
  onOpen: (path: string) => void;
  hashes?: boolean;
}) {
  return (
    <ul className="cc-file-list" data-testid="factory-runs-capsule-file-list">
      {files.map((file) => (
        <li key={file.path} data-testid="factory-runs-capsule-file-row" data-variant={file.path}>
          <button
            className="cc-text-button"
            type="button"
            onClick={() => onOpen(file.path)}
            data-testid="factory-runs-capsule-open-file"
          >
            {file.display_path || file.path.replace(/^owner-ontology\//, '')}
          </button>
          <Integrity state={file.integrity} />
          {hashes && <FileDigests file={file} />}
        </li>
      ))}
    </ul>
  );
}

function FileDigests({ file }: { file: EvidenceFile }) {
  const copy = useCapsuleCopy();
  return (
    <dl className="cc-file-digests" data-testid="factory-runs-capsule-file-digests">
      {file.sha256 && (
        <div>
          <dt>{copy('observed')}</dt>
          <dd>
            <code>{file.sha256}</code>
          </dd>
        </div>
      )}
      {file.expected_sha256 && file.expected_sha256 !== file.sha256 && (
        <div>
          <dt>{copy('expected')}</dt>
          <dd>
            <code>{file.expected_sha256}</code>
          </dd>
        </div>
      )}
    </dl>
  );
}

function parseArtifact(title: string, content: string): unknown {
  try {
    if (/\.(?:jsonl|ndjson)(?:$|\s|@)/i.test(title)) {
      return content
        .split(/\r?\n/)
        .filter((line) => line.trim())
        .map((line) => JSON.parse(line));
    }
    if (/^\s*[\[{]/.test(content)) return JSON.parse(content);
  } catch {
    return null;
  }
  return null;
}

function RawFile({ content, diff }: { content: string; diff: boolean }) {
  return (
    <pre tabIndex={0} data-testid="factory-runs-capsule-raw-file">
      <code>
        {diff
          ? content.split(/(?<=\n)/).map((line, index) => (
              <span
                key={index}
                data-line={
                  line.startsWith('+')
                    ? 'added'
                    : line.startsWith('-')
                      ? 'removed'
                      : line.startsWith('@@')
                        ? 'hunk'
                        : undefined
                }
              >
                {line}
              </span>
            ))
          : content}
      </code>
    </pre>
  );
}

export function MaterialDialog({
  name,
  path,
  run,
  title,
  available,
  onOpen,
  onClose,
  loadFile,
}: {
  name: string;
  path: string;
  run?: string;
  title?: string;
  available: Set<string>;
  onOpen: (path: string) => void;
  onClose: () => void;
  loadFile?: (path: string, signal: AbortSignal) => Promise<CapsuleFile>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const copy = useCapsuleCopy();
  const load = useMemo(
    () => async (relative: string, signal: AbortSignal) => {
      if (loadFile) return loadFile(relative, signal);
      if (!run) return capsuleApi.file(name, relative, signal);
      const file = await factoryApi.file(run, relative, signal);
      return {
        ...file,
        parsed: file.truncated ? null : parseArtifact(title || file.display_path || relative, file.content),
      };
    },
    [loadFile, name, run, title],
  );
  const file = useCapsuleResource(path, load);
  const [view, setView] = useState<'readable' | 'tree' | 'table' | 'chart' | 'raw'>('readable');
  const [copyStatus, setCopyStatus] = useState<'copied' | 'copyFailed'>();
  const label = title || file.data?.display_path || path;
  const markdown = /\.(?:md|markdown)(?:$|\s|@)/i.test(label);
  const diff = /\.(?:diff|patch)(?:$|\s|@)/i.test(label) || file.data?.content.startsWith('diff --git ');
  const structured = file.data?.parsed != null;
  const datasets = useMemo(() => tableData(file.data?.parsed), [file.data?.parsed]);
  const hasChart = datasets.some(({ rows }) => rows.length > 1 && numericColumns(rows).length);
  const modes = [
    ...(structured || markdown ? (['readable'] as const) : []),
    ...(structured ? (['tree'] as const) : []),
    ...(datasets.length ? (['table'] as const) : []),
    ...(hasChart ? (['chart'] as const) : []),
    'raw' as const,
  ];
  const mode = modes.includes(view) ? view : 'raw';

  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);

  return (
    <dialog
      ref={dialog}
      className="cc-dialog"
      aria-labelledby="cc-material-title"
      data-testid="factory-runs-capsule-file-dialog"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="cc-dialog-header">
        <h2 id="cc-material-title">{label}</h2>
        <button type="button" className="cc-control" onClick={onClose} data-testid="factory-runs-capsule-close-file">
          {copy('dropFile')}
        </button>
      </div>
      {!file.data ? (
        <Loading {...file} />
      ) : (
        <>
          <div className="cc-file-info">
            <Integrity state={file.data.integrity} />
            <span>{new Intl.NumberFormat().format(file.data.size)} B</span>
            <FileDigests file={file.data} />
          </div>
          {file.data.truncated && (
            <p className="cc-alert" role="status">
              {copy('truncated')}
            </p>
          )}
          <div className="cc-file-modes">
            <div className="cc-switcher">
              {modes.map((item) => (
                <button
                  type="button"
                  key={item}
                  aria-pressed={mode === item}
                  onClick={() => setView(item)}
                  data-testid="factory-runs-capsule-file-mode"
                  data-variant={item}
                >
                  {copy(item)}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="cc-control"
              data-testid="factory-runs-capsule-copy-file"
              onClick={() => {
                if (!file.data) return;
                if (!navigator.clipboard?.writeText) {
                  setCopyStatus('copyFailed');
                  return;
                }
                void navigator.clipboard.writeText(file.data.content).then(
                  () => setCopyStatus('copied'),
                  () => setCopyStatus('copyFailed'),
                );
              }}
            >
              {copy(copyStatus || 'copy')}
            </button>
          </div>
          <div className="cc-file-surface" data-testid="factory-runs-capsule-file-content" data-variant={mode}>
            {mode === 'raw' && <RawFile content={file.data.content} diff={!!diff} />}
            {mode === 'readable' &&
              (markdown ? (
                <SafeMarkdown content={file.data.content} path={path} available={available} onOpen={onOpen} />
              ) : (
                <StructuredData value={file.data.parsed} />
              ))}
            {mode === 'tree' && <StructuredData value={file.data.parsed} tree />}
            {(mode === 'table' || mode === 'chart') && <AnalysisData datasets={datasets} chart={mode === 'chart'} />}
          </div>
        </>
      )}
    </dialog>
  );
}
