import { useMemo, useState } from 'react';
import { diffLines } from 'diff';
import { FileCode2, Folder } from 'lucide-react';
import type { CcCandidateDetail, CcNode } from '../ccTypes';
import { ConsoleDialog } from './ConsoleDialog';

export function ConsoleFiles({
  node,
  detail,
  loading,
  error,
  onClose,
}: {
  node: CcNode;
  detail: CcCandidateDetail | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  const [mode, setMode] = useState<'diff' | 'file'>('diff');
  const chunks = useMemo(() => {
    if (!detail || detail.candidate_code == null) return [];
    if (mode === 'file') return [{ value: detail.candidate_code, added: false, removed: false }];
    if (detail.parent_code == null) return [];
    // Bound synchronous work for large captured candidates; always retain the full-file view.
    return diffLines(detail.parent_code, detail.candidate_code, { timeout: 300 }) ?? [];
  }, [detail, mode]);
  let oldLine = 0;
  let newLine = 0;
  return (
    <ConsoleDialog title={`Capsule files · ${node.label}`} onClose={onClose}>
      <div className="rc-file-layout">
        <aside className="rc-file-tree" data-testid="rsi-console-file-tree">
          <div className="rc-eyebrow">CAPTURED SOURCE</div>
          <div className="rc-folder">
            <Folder size={15} /> {node.target_id}
          </div>
          {detail && (
            <div className="rc-file-entry" data-testid="rsi-console-file-entry" aria-current="true">
              <FileCode2 size={15} />
              <span>{detail.path}</span>
              <b>{detail.parent_code == null ? '?' : detail.parent_code === detail.candidate_code ? '=' : 'M'}</b>
            </div>
          )}
          <p className="rc-hint">Only source files published by the engine are shown.</p>
        </aside>
        <div className="rc-file-view">
          <div className="rc-file-toolbar">
            <span className="rc-mono">{detail?.path ?? 'Loading source…'}</span>
            <div className="rc-segment">
              <button
                data-testid="rsi-console-diff-mode"
                aria-pressed={mode === 'diff'}
                onClick={() => setMode('diff')}
              >
                Diff vs parent
              </button>
              <button
                data-testid="rsi-console-file-mode"
                aria-pressed={mode === 'file'}
                onClick={() => setMode('file')}
              >
                File
              </button>
            </div>
          </div>
          {loading ? (
            <p className="rc-empty" role="status">
              Loading captured source…
            </p>
          ) : error ? (
            <p className="rc-notice" role="alert">
              {error}
            </p>
          ) : detail?.candidate_code == null ? (
            <p className="rc-empty">{detail?.blocker ?? 'Captured source is unavailable.'}</p>
          ) : mode === 'diff' && detail.parent_code == null ? (
            <p className="rc-empty">Parent source was not published. Select File to inspect this candidate.</p>
          ) : chunks.length === 0 ? (
            <p className="rc-empty">This diff is too large to display. Select File to view the source.</p>
          ) : (
            <pre className="rc-code" data-testid="rsi-console-source-code">
              {chunks.flatMap((chunk, index) => {
                const lines = chunk.value.split('\n');
                if (lines[lines.length - 1] === '') lines.pop();
                return lines.map((line, lineIndex) => {
                  if (!chunk.added) oldLine++;
                  if (!chunk.removed) newLine++;
                  return (
                    <span
                      className={`rc-code-line ${chunk.added ? 'added' : chunk.removed ? 'removed' : ''}`}
                      key={`${index}-${lineIndex}`}
                    >
                      <span className="rc-line-number">
                        {chunk.added ? '+' : chunk.removed ? '−' : ' '}
                        {chunk.removed ? oldLine : newLine}
                      </span>
                      <code>{line || ' '}</code>
                    </span>
                  );
                });
              })}
            </pre>
          )}
        </div>
      </div>
    </ConsoleDialog>
  );
}
