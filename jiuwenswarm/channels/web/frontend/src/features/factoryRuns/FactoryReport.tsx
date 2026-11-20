import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { factoryApi, type EvidenceFile, type FileContent } from './api';
import { FactoryStructuredReport } from './FactoryStructuredReport';
import { evidenceIndex, externalReportLink, linkedEvidence, reportFiles, reportHeadings } from './reportModel';
import './factoryReport.css';

type FileResult = { key: string; file?: FileContent };

function useRunFile(runId: string, source: EvidenceFile) {
  const { path, sha256, expected_sha256, integrity } = source;
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<FileResult>();
  const key = JSON.stringify([runId, path, sha256, expected_sha256, integrity, attempt]);

  useEffect(() => {
    if (integrity === 'missing') return;
    let current = true;
    void factoryApi.file(runId, path).then(
      (file) => {
        if (current) setResult({ key, file });
      },
      () => {
        if (current) setResult({ key });
      },
    );
    return () => {
      current = false;
    };
  }, [runId, path, integrity, key]);

  return {
    file: result?.key === key ? result.file : undefined,
    loading: integrity !== 'missing' && result?.key !== key,
    retry: () => setAttempt((value) => value + 1),
  };
}

function ReportDigest({ source }: { source: EvidenceFile }) {
  const { t } = useTranslation();
  return (
    <div className="factory-report-digests" data-testid="factory-runs-report-digests">
      <span
        className="factory-report-integrity"
        data-testid="factory-runs-report-integrity"
        data-integrity={source.integrity}
      >
        {t(`factoryRuns.${source.integrity}`)}
      </span>
      {source.sha256 && <code data-testid="factory-runs-report-sha256">SHA-256 {source.sha256}</code>}
      {source.expected_sha256 && source.integrity !== 'verified' && (
        <code data-testid="factory-runs-report-expected-sha256">
          {t('factoryRuns.reportView.expectedDigest')} {source.expected_sha256}
        </code>
      )}
    </div>
  );
}

function FileStatus({
  loading,
  missing,
  evidence,
  onRetry,
}: {
  loading: boolean;
  missing: boolean;
  evidence?: boolean;
  onRetry: () => void;
}) {
  const { t } = useTranslation();
  const variant = loading ? 'loading' : missing ? 'missing' : 'error';
  return (
    <div className="factory-report-status" data-testid="factory-runs-report-file-status" data-variant={variant}>
      <p role={variant === 'error' ? 'alert' : 'status'}>
        {t(
          loading
            ? 'factoryRuns.loading'
            : evidence
              ? 'factoryRuns.reportView.evidenceError'
              : 'factoryRuns.reportView.loadError',
        )}
      </p>
      {variant === 'error' && (
        <button type="button" onClick={onRetry} data-testid="factory-runs-report-file-retry">
          {t('factoryRuns.reportView.retry')}
        </button>
      )}
    </div>
  );
}

function TruncatedNotice() {
  const { t } = useTranslation();
  return (
    <p className="factory-report-notice" data-testid="factory-runs-report-truncated">
      {t('factoryRuns.truncated')}
    </p>
  );
}

function EvidenceDialog({ runId, source, onClose }: { runId: string; source: EvidenceFile; onClose: () => void }) {
  const { t } = useTranslation();
  const { file, loading, retry } = useRunFile(runId, source);
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  return (
    <dialog
      ref={ref}
      className="factory-report-dialog"
      aria-labelledby={titleId}
      onClose={onClose}
      data-testid="factory-runs-report-evidence"
    >
      <div className="factory-report-dialog-header">
        <h3 id={titleId} data-testid="factory-runs-report-evidence-title">
          {t('factoryRuns.reportView.evidenceTitle')}
        </h3>
        <button type="button" onClick={() => ref.current?.close()} data-testid="factory-runs-report-evidence-close">
          {t('common.close')}
        </button>
      </div>
      <div className="factory-report-source">
        <p data-testid="factory-runs-report-evidence-path">{source.display_path || source.path}</p>
        <ReportDigest source={file ?? source} />
      </div>
      {file ? (
        <>
          {file.truncated && <TruncatedNotice />}
          <div data-testid="factory-runs-report-evidence-content">
            {/\.json(?:$| ·)/i.test(file.display_path || file.path)
              ? <FactoryStructuredReport content={file.content} />
              : <pre className="factory-report-raw">{file.content}</pre>}
          </div>
        </>
      ) : (
        <FileStatus evidence loading={loading} missing={source.integrity === 'missing'} onRetry={retry} />
      )}
    </dialog>
  );
}

function headingLink(slug: string) {
  return `#factory-report-heading-${slug}`;
}

function MarkdownReport({
  content,
  source,
  files,
  onOpenEvidence,
}: {
  content: string;
  source: EvidenceFile;
  files: EvidenceFile[];
  onOpenEvidence: (file: EvidenceFile) => void;
}) {
  const { t } = useTranslation();
  const headings = useMemo(() => reportHeadings(content), [content]);
  const components = useMemo<Components>(() => {
    const headingsByOffset = new Map(headings.map((heading) => [heading.offset, heading.slug]));
    const slugs = new Set(headings.map((heading) => heading.slug));
    const indexed = evidenceIndex(files);
    const renderLink = (href: string | undefined) => {
      if (!href) return {};
      const external = externalReportLink(href);
      if (external) return { href: external, external: true };
      const [path, fragment] = href.split('#');
      const evidence = path ? linkedEvidence(href, source, files) : undefined;
      if (fragment && (!path || evidence?.path === source.path)) {
        try {
          const slug = decodeURIComponent(fragment);
          if (slugs.has(slug)) return { href: headingLink(slug) };
        } catch {
          return {};
        }
      }
      return { evidence };
    };

    const result: Components = {
      a({ node, href, children, ...attributes }) {
        if (
          href?.startsWith('#user-content-fn') &&
          node &&
          ('dataFootnoteRef' in node.properties || 'dataFootnoteBackref' in node.properties)
        ) {
          return (
            <a {...attributes} href={href} data-testid="factory-runs-report-link" data-variant={href}>
              {children}
            </a>
          );
        }
        const target = renderLink(href);
        if (target.evidence) {
          const evidence = target.evidence;
          return (
            <button
              className="factory-report-evidence-link"
              type="button"
              onClick={() => onOpenEvidence(evidence)}
              data-testid="factory-runs-report-evidence-link"
              data-variant={evidence.path}
            >
              {children}
            </button>
          );
        }
        if (!target.href) return <>{children}</>;
        return (
          <a
            href={target.href}
            target={target.external ? '_blank' : undefined}
            rel={target.external ? 'noopener noreferrer' : undefined}
            data-testid="factory-runs-report-link"
            data-variant={target.href}
          >
            {children}
          </a>
        );
      },
      code({ children, className }) {
        const reference = typeof children === 'string' && !children.includes('\n') ? indexed.get(children) : undefined;
        const code = <code className={className}>{children}</code>;
        return reference && reference.path !== source.path ? (
          <button
            className="factory-report-evidence-link"
            type="button"
            data-testid="factory-runs-report-evidence-link"
            data-variant={reference.path}
            onClick={() => onOpenEvidence(reference)}
          >
            {code}
          </button>
        ) : code;
      },
      img({ alt }) {
        return alt ? <span>{alt}</span> : null;
      },
      table({ children }) {
        return (
          <div className="factory-report-table">
            <table>{children}</table>
          </div>
        );
      },
    };
    for (const tag of ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'] as const) {
      result[tag] = ({ node, children, id, className }) => {
        const slug = headingsByOffset.get(node?.position?.start.offset ?? -1);
        const Heading = tag;
        return (
          <Heading
            id={slug ? headingLink(slug).slice(1) : id}
            className={className}
            tabIndex={slug ? -1 : undefined}
            data-testid="factory-runs-report-heading"
            data-variant={slug}
          >
            {children}
          </Heading>
        );
      };
    }
    return result;
  }, [headings, source, files, onOpenEvidence]);
  const firstLevel = Math.min(...headings.map(({ depth }) => depth));

  return (
    <div className="factory-report-layout" data-contents={headings.length > 0}>
      {headings.length > 0 && (
        <nav
          className="factory-report-toc"
          aria-label={t('factoryRuns.reportView.contents')}
          data-testid="factory-runs-report-contents"
        >
          <h3 data-testid="factory-runs-report-contents-title">{t('factoryRuns.reportView.contents')}</h3>
          <ol>
            {headings.map(({ slug, title, depth }) => (
              <li key={slug} style={{ paddingInlineStart: `${Math.min(depth - firstLevel, 3) * 0.65}rem` }}>
                <a href={headingLink(slug)} data-testid="factory-runs-report-contents-link" data-variant={slug}>
                  {title}
                </a>
              </li>
            ))}
          </ol>
        </nav>
      )}
      <article className="factory-report-prose" data-testid="factory-runs-report-markdown">
        <ReactMarkdown skipHtml remarkPlugins={[remarkGfm]} components={components}>
          {content}
        </ReactMarkdown>
      </article>
    </div>
  );
}

function ReportDocument({
  runId,
  selected,
  files,
  expectedSha,
}: {
  runId: string;
  selected: ReturnType<typeof reportFiles>[number];
  files: EvidenceFile[];
  expectedSha?: string;
}) {
  const { t } = useTranslation();
  const { file, loading, retry } = useRunFile(runId, selected.file);
  const [evidence, setEvidence] = useState<EvidenceFile>();
  const source = file ?? selected.file;
  const displayed = expectedSha && source.sha256 !== expectedSha && source.integrity !== 'missing'
    ? { ...source, expected_sha256: expectedSha, integrity: 'mismatch' as const } : source;
  return (
    <>
      <div className="factory-report-source" data-testid="factory-runs-report-source">
        <div className="factory-report-source-title">
          <span>{t('factoryRuns.reportView.source')}</span>
          <strong data-testid="factory-runs-report-source-path">{selected.label}</strong>
          <span>{t(`factoryRuns.reportView.${selected.format}`)}</span>
        </div>
        <ReportDigest source={displayed} />
      </div>
      {file?.truncated && <TruncatedNotice />}
      {!file ? (
        <FileStatus loading={loading} missing={selected.file.integrity === 'missing'} onRetry={retry} />
      ) : !file.content.trim() ? (
        <p className="factory-report-status" data-testid="factory-runs-report-empty-file">
          {t('factoryRuns.reportView.emptyFile')}
        </p>
      ) : selected.format === 'markdown' ? (
        <MarkdownReport source={selected.file} files={files} content={file.content} onOpenEvidence={setEvidence} />
      ) : (
        <FactoryStructuredReport content={file.content} />
      )}
      {evidence && <EvidenceDialog runId={runId} source={evidence} onClose={() => setEvidence(undefined)} />}
    </>
  );
}

export function FactoryReport({ runId, files, initialPath, expectedSha }: { runId: string; files: EvidenceFile[]; initialPath?: string; expectedSha?: string }) {
  const { t } = useTranslation();
  const reports = useMemo(() => reportFiles(files), [files]);
  const [selection, setSelection] = useState({ runId, path: '' });
  const selected =
    (selection.runId === runId ? reports.find(({ file }) => file.path === selection.path) : undefined) ??
    reports.find(({ file }) => file.path === initialPath) ??
    reports.find(({ file }) => file.integrity !== 'missing') ??
    reports[0];
  const otherIssues = reports.filter(
    ({ file }) => file.path !== selected?.file.path && (file.integrity === 'mismatch' || file.integrity === 'missing'),
  );

  return (
    <section className="factory-report" aria-label={t('factoryRuns.report')} data-testid="factory-runs-report">
      {selected ? (
        <>
          {reports.length > 1 && (
            <label className="factory-report-picker">
              <span>{t('factoryRuns.reportView.select')}</span>
              <select
                value={selected.file.path}
                onChange={(event) => setSelection({ runId, path: event.target.value })}
                data-testid="factory-runs-report-select"
              >
                {reports.map(({ file, label }) => (
                  <option key={file.path} value={file.path}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          )}
          {otherIssues.length > 0 && (
            <ul className="factory-report-issues" data-testid="factory-runs-report-issues">
              {otherIssues.map(({ file, label }) => (
                <li key={file.path} data-testid="factory-runs-report-issue" data-variant={file.path}>
                  <span>{label}</span>
                  <ReportDigest source={file} />
                </li>
              ))}
            </ul>
          )}
          <ReportDocument
            key={JSON.stringify([runId, selected.file.path])}
            runId={runId}
            selected={selected}
            files={files}
            expectedSha={selected.file.path === initialPath ? expectedSha : undefined}
          />
        </>
      ) : (
        <div className="factory-report-empty" data-testid="factory-runs-report-empty">
          <h3 data-testid="factory-runs-report-empty-title">{t('factoryRuns.reportView.emptyTitle')}</h3>
          <p data-testid="factory-runs-report-empty-body">{t('factoryRuns.reportView.emptyBody')}</p>
        </div>
      )}
    </section>
  );
}
