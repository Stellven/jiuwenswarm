import { useEffect, useRef, useState } from 'react';
import { HighlightStyle, StreamLanguage, syntaxHighlighting } from '@codemirror/language';
import { json } from '@codemirror/legacy-modes/mode/javascript';
import { yaml } from '@codemirror/lang-yaml';
import { EditorState } from '@codemirror/state';
import { EditorView, lineNumbers } from '@codemirror/view';
import { tags } from '@lezer/highlight';
import type { DocumentFormat } from './dataModel';
import { useViewerLabels } from './viewerLabels';

const highlight = syntaxHighlighting(
  HighlightStyle.define([
    { tag: tags.propertyName, class: 'evidence-syntax-key' },
    { tag: tags.string, class: 'evidence-syntax-string' },
    { tag: [tags.number, tags.bool, tags.null, tags.atom], class: 'evidence-syntax-literal' },
    { tag: tags.comment, class: 'evidence-syntax-comment' },
  ]),
);

export function RawDocument({ name, source, format }: { name: string; source: string; format: DocumentFormat }) {
  const host = useRef<HTMLDivElement>(null);
  const [copyStatus, setCopyStatus] = useState<'copy' | 'copied' | 'copyError'>('copy');
  const { label } = useViewerLabels();

  useEffect(() => {
    if (!host.current) return;
    const editor = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: source,
        extensions: [
          EditorState.readOnly.of(true),
          EditorView.editable.of(false),
          EditorView.contentAttributes.of({ 'aria-label': name, tabindex: '0' }),
          lineNumbers(),
          highlight,
          format === 'yaml' ? yaml() : format === 'json' ? StreamLanguage.define(json) : [],
        ],
      }),
    });
    return () => editor.destroy();
  }, [name, source, format]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(source);
      setCopyStatus('copied');
    } catch {
      setCopyStatus('copyError');
    }
  }

  return (
    <div className="evidence-raw" data-testid="factory-runs-raw">
      <div className="evidence-raw-bar">
        <span>{format === 'mermaid' ? 'Mermaid' : format === 'text' ? label('raw') : format.toUpperCase()}</span>
        <button type="button" data-testid="factory-runs-raw-copy" onClick={() => void copy()} aria-live="polite">
          {label(copyStatus)}
        </button>
      </div>
      <div ref={host} className="evidence-code" data-testid="factory-runs-raw-source" />
    </div>
  );
}
