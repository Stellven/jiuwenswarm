import { useDeferredValue, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { EvidenceFile, FileContent } from '../api';
import { DataViewer } from './DataViewer';
import { DiffViewer } from './DiffViewer';
import { DigestBadge, EvidenceMetadata } from './EvidenceMetadata';
import { RawDocument } from './RawDocument';
import { TerminalViewer } from './TerminalViewer';
import { documentFormat, evidenceKind } from './dataModel';
import { useViewerLabels } from './viewerLabels';

type FileBrowserProps = {
  files: EvidenceFile[];
  selectedFile?: EvidenceFile;
  content: FileContent | null;
  error?: string;
  onSelect: (path: string) => void;
};

const FILE_PAGE_SIZE = 100;

export function EvidenceFileBrowser({ files, selectedFile, content, error, onSelect }: FileBrowserProps) {
  const { label } = useViewerLabels();
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(FILE_PAGE_SIZE);
  const search = useDeferredValue(query.trim().toLowerCase());
  const matches = useMemo(
    () =>
      files.filter((file) =>
        [file.path, file.display_path || '', ...(file.artifact_ids ?? [])].some((name) =>
          name.toLowerCase().includes(search),
        ),
      ),
    [files, search],
  );
  const visible = matches.slice(0, limit);

  return (
    <div className="factory-file-grid">
      <div data-testid="factory-runs-files">
        {files.length > 0 && (
          <input
            type="search"
            className="evidence-search"
            aria-label={label('filterFiles')}
            placeholder={label('filterFiles')}
            data-testid="factory-runs-files-search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setLimit(FILE_PAGE_SIZE);
            }}
          />
        )}
        <div
          className="factory-files evidence-files-list"
          aria-label={label('browseFiles')}
          data-testid="factory-runs-files-list"
        >
          {visible.map((file) => (
            <button
              key={file.path}
              type="button"
              data-testid="factory-runs-file"
              data-variant={file.path}
              aria-pressed={selectedFile?.path === file.path}
              onClick={() => onSelect(file.path)}
            >
              <span>{file.display_path || file.path}</span>
              <DigestBadge file={file} />
            </button>
          ))}
          {matches.length > visible.length && (
            <button
              type="button"
              data-testid="factory-runs-files-show-more"
              onClick={() => setLimit(limit + FILE_PAGE_SIZE)}
            >
              {label('showMore')} · {matches.length - visible.length}
            </button>
          )}
          {!visible.length && (
            <p className="factory-muted" data-testid="factory-runs-no-evidence">
              {files.length ? label('noResults') : t('factoryRuns.noEvidence')}
            </p>
          )}
        </div>
      </div>
      <div className="factory-file-content" data-testid="factory-runs-file-content">
        {selectedFile ? (
          <EvidenceFilePreview key={selectedFile.path} file={selectedFile} content={content} error={error} />
        ) : files.length > 0 ? (
          <p className="evidence-file-preview-status" data-testid="factory-runs-file-prompt">
            {label('chooseFile')}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function ReportDocument({ file, name }: { file: FileContent; name: string }) {
  const { label } = useViewerLabels();
  const [raw, setRaw] = useState(false);
  return (
    <section className="evidence-inspector" data-testid="factory-runs-report-document">
      <header className="evidence-toolbar">
        <div className="evidence-modes" role="group" aria-label={label('modes')}>
          <button
            type="button"
            aria-pressed={!raw}
            onClick={() => setRaw(false)}
            data-testid="factory-runs-report-rendered-mode"
          >
            {label('readable')}
          </button>
          <button
            type="button"
            aria-pressed={raw}
            onClick={() => setRaw(true)}
            data-testid="factory-runs-report-raw-mode"
          >
            {label('raw')}
          </button>
        </div>
        <EvidenceMetadata file={file} size={file.size} />
      </header>
      {raw ? (
        <RawDocument name={name} format="text" source={file.content} />
      ) : (
        <article className="evidence-report" data-testid="factory-runs-markdown">
          <ReactMarkdown
            skipHtml
            remarkPlugins={[remarkGfm]}
            components={{
              a: ({ href, children }) => (
                <a href={href} target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              ),
              img: ({ alt }) => <span>{alt}</span>,
              table: ({ children }) => (
                <div className="evidence-table-scroll">
                  <table>{children}</table>
                </div>
              ),
            }}
          >
            {file.content}
          </ReactMarkdown>
        </article>
      )}
    </section>
  );
}

function fileName(file: EvidenceFile, source: string) {
  const names = [file.path, ...(file.display_path?.split(' · ') ?? [])];
  return (
    names.find((name) => documentFormat(name, '') !== 'text') ||
    names.find((name) => documentFormat(name, source) === 'json') ||
    file.display_path ||
    file.path
  );
}

export function EvidenceFilePreview({
  file,
  content,
  error,
}: {
  file: EvidenceFile;
  content: FileContent | null;
  error?: string;
}) {
  const { label } = useViewerLabels();
  const { t } = useTranslation();
  const title = file.display_path || file.path;
  const current = content?.path === file.path ? content : null;
  const metadata = current ?? file;
  const kind = evidenceKind(metadata.path, metadata.display_path, current?.content);
  const binary = current?.content.includes('\u0000');
  const status = file.integrity === 'missing' ? 'missing' : error ? 'error' : !current ? 'loading' : undefined;
  const titleAndTruncation = (
    <header className="evidence-file-preview-title">
      <h3 data-testid="factory-runs-file-title">{title}</h3>
      {current?.truncated && (
        <p className="factory-muted" data-testid="factory-runs-truncated">
          {t('factoryRuns.truncated')}
        </p>
      )}
    </header>
  );

  return (
    <>
      {titleAndTruncation}
      {status && (
        <div
          className="evidence-file-preview-status"
          role="status"
          data-testid="factory-runs-file-status"
          data-variant={status}
        >
          <EvidenceMetadata file={metadata} size={metadata.size} />
          <p>{status === 'missing' ? label('fileMissing') : error || label('fileLoading')}</p>
        </div>
      )}
      {!status &&
        current &&
        (binary ? (
          <div className="evidence-file-preview-status" data-testid="factory-runs-file-status" data-variant="binary">
            <EvidenceMetadata file={current} size={current.size} />
            <p>{label('binaryFile')}</p>
          </div>
        ) : kind === 'data' ? (
          <DataViewer name={fileName(current, current.content)} file={current} source={current.content} />
        ) : kind === 'markdown' ? (
          <ReportDocument name={title} file={current} />
        ) : (
          <div className="evidence-specialized-viewer" data-testid="factory-runs-specialized-file" data-variant={kind}>
            <EvidenceMetadata file={current} size={current.size} />
            {kind === 'diff' ? <DiffViewer content={current.content} /> : <TerminalViewer content={current.content} />}
          </div>
        ))}
    </>
  );
}
