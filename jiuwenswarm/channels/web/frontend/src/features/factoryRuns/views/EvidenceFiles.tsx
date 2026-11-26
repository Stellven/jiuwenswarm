import { useDeferredValue, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSlug from 'rehype-slug';
import type { EvidenceFile, FileContent } from '../api';
import { DataViewer } from './DataViewer';
import { DiffViewer } from './DiffViewer';
import { DigestBadge, EvidenceMetadata } from './EvidenceMetadata';
import { ReplayLabel } from './NodeEvidence';
import { RawDocument } from './RawDocument';
import { TerminalViewer } from './TerminalViewer';
import { documentFormat, evidenceKind, resolveEvidenceLink } from './dataModel';
import { useViewerLabels } from './viewerLabels';
import type { KeyFile } from './storyModel';

type FileBrowserProps = {
  files: EvidenceFile[];
  selectedFile?: EvidenceFile;
  runFiles?: EvidenceFile[];
  content: FileContent | null;
  error?: string;
  onSelect: (path: string) => void;
  /** Key files of the current replay step, pinned above the list. */
  keyFiles?: { key: KeyFile; file: EvidenceFile }[];
  /** Every flagged key file in the run, by path. */
  keyFlags?: Map<string, KeyFile[]>;
  replayByArtifact?: Map<string, unknown[]>;
};

export function KeyFileBadge({ flags }: { flags?: KeyFile[] }) {
  if (!flags?.length) return null;
  const steps = [...new Set(flags.map((flag) => flag.step).filter((step) => step !== undefined))];
  return (
    <span
      className="factory-key-badge"
      data-testid="factory-runs-key-badge"
      title={flags.map((flag) => `${flag.label}${flag.why ? ' - ' + flag.why : ''}`).join(' | ')}
    >
      ★ Key file{steps.length ? ` · step ${steps.join(', ')}` : ''}
    </span>
  );
}

const FILE_PAGE_SIZE = 100;

export function EvidenceFileBrowser({
  files,
  runFiles = files,
  selectedFile,
  content,
  error,
  onSelect,
  keyFiles = [],
  keyFlags,
  replayByArtifact,
}: FileBrowserProps) {
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
  const fileReplay = (file: EvidenceFile) => file.artifact_ids?.flatMap((id) => replayByArtifact?.get(id) ?? []);

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
        {keyFiles.length > 0 && (
          <section className="factory-key-files" data-testid="factory-runs-key-files" aria-label="Key files">
            <h4>★ Key files for this step</h4>
            {keyFiles.map(({ key, file }) => (
              <button
                key={file.path}
                type="button"
                data-testid="factory-runs-key-file"
                data-variant={file.path}
                aria-pressed={selectedFile?.path === file.path}
                onClick={() => onSelect(file.path)}
                title={key.why}
              >
                <span>
                  <strong>{key.label}</strong>
                  {key.why && <small>{key.why}</small>}
                  <ReplayLabel value={fileReplay(file)} />
                </span>
                <DigestBadge file={file} />
              </button>
            ))}
          </section>
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
              <KeyFileBadge flags={keyFlags?.get(file.path)} />
              <ReplayLabel value={fileReplay(file)} />
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
        {selectedFile && <ReplayLabel value={fileReplay(selectedFile)} />}
        {selectedFile ? (
          <EvidenceFilePreview
            key={selectedFile.path}
            file={selectedFile}
            content={content}
            error={error}
            resolveLink={(href) => resolveEvidenceLink(runFiles, selectedFile, href)}
            onOpenFile={onSelect}
          />
        ) : files.length > 0 ? (
          <p className="evidence-file-preview-status" data-testid="factory-runs-file-prompt">
            {label('chooseFile')}
          </p>
        ) : null}
      </div>
    </div>
  );
}

type ReportLinks = { resolveLink?: (href: string) => string | undefined; onOpenFile?: (path: string) => void };
const REPORT_HEADING_PREFIX = 'evidence-heading-';

function ReportDocument({ file, name, resolveLink, onOpenFile }: { file: FileContent; name: string } & ReportLinks) {
  const { label } = useViewerLabels();
  const [raw, setRaw] = useState(false);
  const article = useRef<HTMLElement>(null);
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
        <article ref={article} className="evidence-report" data-testid="factory-runs-markdown">
          <ReactMarkdown
            skipHtml
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[[rehypeSlug, { prefix: REPORT_HEADING_PREFIX }]]}
            components={{
              a: ({ href, children }) => {
                if (!href) return <span>{children}</span>;
                if (/^(https?:|mailto:)/i.test(href)) {
                  return (
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      {children}
                    </a>
                  );
                }
                const path = resolveLink?.(href);
                const isAnchor = href.startsWith('#');
                if ((path && onOpenFile) || isAnchor) {
                  return (
                    <button
                      type="button"
                      className="evidence-report-link"
                      data-testid="factory-runs-report-link"
                      data-variant={href}
                      onClick={() => {
                        if (path) onOpenFile?.(path);
                        else
                          article.current
                            ?.querySelector('#' + CSS.escape(REPORT_HEADING_PREFIX + href.slice(1)))
                            ?.scrollIntoView();
                      }}
                    >
                      {children}
                    </button>
                  );
                }
                return <span>{children}</span>;
              },
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

function fileName(file: EvidenceFile) {
  const names = [file.path, ...(file.display_path?.split(' · ') ?? [])];
  return names.find((name) => documentFormat(name, '') !== 'text') || file.display_path || file.path;
}

export function EvidenceFilePreview({
  file,
  content,
  error,
  resolveLink,
  onOpenFile,
}: {
  file: EvidenceFile;
  content: FileContent | null;
  error?: string;
} & ReportLinks) {
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
          <DataViewer name={fileName(current)} file={current} source={current.content} />
        ) : kind === 'markdown' ? (
          <ReportDocument name={title} file={current} resolveLink={resolveLink} onOpenFile={onOpenFile} />
        ) : (
          <div className="evidence-specialized-viewer" data-testid="factory-runs-specialized-file" data-variant={kind}>
            <EvidenceMetadata file={current} size={current.size} />
            {kind === 'diff' ? <DiffViewer content={current.content} /> : <TerminalViewer content={current.content} />}
          </div>
        ))}
    </>
  );
}
