import { useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, FileCode, Folder } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { buildDiffTree, pairDiffLines, readDiff, type DiffFile, type DiffLine, type DiffTreeNode } from './diffModel';
import './diffViewer.css';

const labels = {
  en: {
    diffView: 'Diff view',
    files: 'Changed files',
    unified: 'Unified',
    split: 'Side by side',
    raw: 'Raw',
    before: 'Before',
    after: 'After',
    added: 'Lines added',
    removed: 'Lines removed',
    unnamed: 'Untitled patch',
    binary: 'Binary file changed.',
    metadata: 'No text hunks in this file.',
    fallback: 'The patch could not be displayed as a structured diff.',
  },
  zh: {
    diffView: '差异视图',
    files: '变更文件',
    unified: '统一视图',
    split: '并排视图',
    raw: '原文',
    before: '变更前',
    after: '变更后',
    added: '新增行数',
    removed: '删除行数',
    unnamed: '未命名补丁',
    binary: '二进制文件已变更。',
    metadata: '此文件没有文本差异。',
    fallback: '无法以结构化差异显示此补丁。',
  },
};

type Labels = typeof labels.en;
type Mode = 'unified' | 'split' | 'raw';
const modes: Mode[] = ['unified', 'split', 'raw'];
const markers: Record<DiffLine['kind'], string> = { added: '+', removed: '−', context: '' };

function Stats({ added, removed, text }: Pick<DiffFile, 'added' | 'removed'> & { text: Labels }) {
  return (
    <span className="factory-diff-stats" data-testid="factory-runs-diff-stats">
      <span className="factory-diff-added" aria-label={`${text.added} ${added}`} title={text.added}>
        +{added}
      </span>
      <span className="factory-diff-removed" aria-label={`${text.removed} ${removed}`} title={text.removed}>
        −{removed}
      </span>
    </span>
  );
}

function FileTree({
  nodes,
  current,
  navigate,
  text,
}: {
  nodes: DiffTreeNode[];
  current: string;
  navigate: (id: string) => void;
  text: Labels;
}) {
  return (
    <ul className="factory-diff-tree">
      {nodes.map((node) =>
        node.kind === 'directory' ? (
          <li key={node.path} data-testid="factory-runs-diff-directory" data-variant={node.path}>
            <details open>
              <summary
                className="factory-diff-tree-item"
                title={node.path}
                data-testid="factory-runs-diff-directory-toggle"
              >
                <ChevronDown className="factory-diff-tree-chevron" aria-hidden="true" size={13} />
                <Folder aria-hidden="true" size={15} />
                <span>{node.name}</span>
              </summary>
              <FileTree nodes={node.children} current={current} navigate={navigate} text={text} />
            </details>
          </li>
        ) : (
          <li key={node.file.id}>
            <button
              type="button"
              className="factory-diff-tree-item"
              title={node.file.path}
              aria-current={node.file.id === current ? 'location' : undefined}
              onClick={() => navigate(node.file.id)}
              data-testid="factory-runs-diff-tree-file"
              data-variant={node.file.path || node.file.id}
            >
              <FileCode aria-hidden="true" size={15} />
              <span>{node.name || text.unnamed}</span>
            </button>
          </li>
        ),
      )}
    </ul>
  );
}

function Line({ line, side }: { line?: DiffLine; side?: 'before' | 'after' }) {
  return (
    <div className="factory-diff-line" data-kind={line?.kind ?? 'empty'}>
      {side !== 'after' && <span className="factory-diff-number">{line?.oldNumber}</span>}
      {side !== 'before' && <span className="factory-diff-number">{line?.newNumber}</span>}
      <span className="factory-diff-marker">{line && markers[line.kind]}</span>
      <code>
        {line?.text}
        {line?.note && <small className="factory-diff-line-note">{line.note}</small>}
      </code>
    </div>
  );
}

function FileBody({ file, mode, text }: { file: DiffFile; mode: Exclude<Mode, 'raw'>; text: Labels }) {
  if (!file.hunks.length) {
    return (
      <p className="factory-diff-notice" data-testid="factory-runs-diff-no-hunks">
        {file.binary ? text.binary : text.metadata}
      </p>
    );
  }
  return (
    <div className="factory-diff-body" data-testid="factory-runs-diff-body" data-variant={mode}>
      {mode === 'split' && (
        <div className="factory-diff-columns">
          <span>{text.before}</span>
          <span>{text.after}</span>
        </div>
      )}
      {file.hunks.map((hunk, index) => (
        <section className="factory-diff-hunk" key={index} data-testid="factory-runs-diff-hunk" data-variant={index}>
          <div className="factory-diff-hunk-heading">{hunk.header}</div>
          {mode === 'unified'
            ? hunk.lines.map((line, lineIndex) => <Line key={lineIndex} line={line} />)
            : pairDiffLines(hunk.lines).map(({ before, after }, lineIndex) => (
                <div className="factory-diff-row" key={lineIndex}>
                  <Line line={before} side="before" />
                  <Line line={after} side="after" />
                </div>
              ))}
        </section>
      ))}
    </div>
  );
}

export function DiffViewer({ content }: { content: string }) {
  const { i18n } = useTranslation();
  const text = (i18n.resolvedLanguage ?? i18n.language)?.startsWith('zh') ? labels.zh : labels.en;
  const diff = useMemo(() => readDiff(content), [content]);
  const tree = useMemo(() => buildDiffTree(diff?.files ?? []), [diff]);
  const firstFile = diff?.files[0]?.id ?? '';
  const [mode, setMode] = useState<Mode>('unified');
  const [current, setCurrent] = useState('');
  const [fileState, setFileState] = useState<Record<string, boolean>>({});
  const fileButtons = useRef(new Map<string, HTMLButtonElement>());

  function navigate(id: string) {
    setCurrent(id);
    setFileState((state) => ({ ...state, [id]: true }));
    const button = fileButtons.current.get(id);
    button?.focus({ preventScroll: true });
    button?.scrollIntoView({ block: 'nearest' });
  }

  return (
    <section className="factory-diff" aria-label={text.diffView} data-testid="factory-runs-diff-viewer">
      {diff && (
        <header className="factory-diff-toolbar">
          <div role="group" aria-label={text.diffView} className="factory-diff-modes">
            {modes.map((option) => (
              <button
                type="button"
                key={option}
                aria-pressed={mode === option}
                onClick={() => setMode(option)}
                data-testid={`factory-runs-diff-mode-${option}`}
              >
                {text[option]}
              </button>
            ))}
          </div>
          <Stats added={diff.added} removed={diff.removed} text={text} />
        </header>
      )}
      {!diff || mode === 'raw' ? (
        <>
          {!diff && (
            <p className="factory-diff-notice" data-testid="factory-runs-diff-fallback">
              {text.fallback}
            </p>
          )}
          <pre className="factory-diff-raw" data-testid="factory-runs-diff-raw">
            {content}
          </pre>
        </>
      ) : (
        <div className="factory-diff-layout">
          <nav className="factory-diff-navigation" aria-label={text.files} data-testid="factory-runs-diff-navigation">
            <div className="factory-diff-navigation-heading">
              {text.files} <span>{diff.files.length}</span>
            </div>
            <FileTree nodes={tree} current={current || firstFile} navigate={navigate} text={text} />
          </nav>
          <div className="factory-diff-files">
            {diff.files.map((file) => {
              const expanded = fileState[file.id] ?? file.id === firstFile;
              return (
                <section
                  className="factory-diff-file"
                  key={file.id}
                  data-testid="factory-runs-diff-file"
                  data-variant={file.path || file.id}
                >
                  <button
                    type="button"
                    className="factory-diff-file-toggle"
                    aria-expanded={expanded}
                    ref={(button) => {
                      if (button) fileButtons.current.set(file.id, button);
                      else fileButtons.current.delete(file.id);
                    }}
                    onClick={() => {
                      setCurrent(file.id);
                      setFileState((state) => ({ ...state, [file.id]: !expanded }));
                    }}
                    data-testid="factory-runs-diff-file-toggle"
                  >
                    {expanded ? (
                      <ChevronDown size={15} aria-hidden="true" />
                    ) : (
                      <ChevronRight size={15} aria-hidden="true" />
                    )}
                    <span className="factory-diff-file-path">
                      {file.previousPath && <>{file.previousPath} → </>}
                      {file.path || text.unnamed}
                    </span>
                    <Stats added={file.added} removed={file.removed} text={text} />
                  </button>
                  {expanded && <FileBody file={file} mode={mode} text={text} />}
                </section>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
