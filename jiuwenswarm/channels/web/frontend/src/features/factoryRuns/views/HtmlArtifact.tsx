import { useEffect, useMemo, useRef, useState } from 'react';
import type { FileContent } from '../api';
import { EvidenceMetadata } from './EvidenceMetadata';
import { RawDocument } from './RawDocument';
import './htmlArtifact.css';

const MESSAGE = 'factory-html-artifact-link';

// The document has an opaque origin. The nonce permits only this viewer's link handler.
const LINK_HANDLER = `
document.addEventListener('click', (event) => {
  const link = event.target.closest && event.target.closest('a');
  if (!link) return;
  event.preventDefault();
  const href = link.getAttribute('data-artifact-href');
  if (!href) return;
  if (href.startsWith('#')) {
    try { document.getElementById(decodeURIComponent(href.slice(1)))?.scrollIntoView(); } catch {}
    return;
  }
  parent.postMessage({ type: '${MESSAGE}', href }, '*');
}, true);
`;

export function artifactHtmlDocument(source: string) {
  const template = document.createElement('template');
  template.innerHTML = source;
  // Resource loading and navigation are disabled even when an artifact contains active markup.
  template.content.querySelectorAll('base, script, iframe, frame, object, embed, portal, link, area, meta[http-equiv]')
    .forEach((element) => element.remove());
  template.content.querySelectorAll('a').forEach((anchor) => {
    const href = anchor.getAttribute('href');
    anchor.removeAttribute('target');
    anchor.removeAttribute('ping');
    anchor.removeAttribute('download');
    anchor.removeAttributeNS('http://www.w3.org/1999/xlink', 'href');
    if (href) {
      anchor.setAttribute('data-artifact-href', href);
      anchor.setAttribute('href', '#');
    }
  });
  const nonce = Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) => byte.toString(16).padStart(2, '0')).join('');
  const csp = document.createElement('meta');
  csp.httpEquiv = 'Content-Security-Policy';
  csp.content = `default-src 'none'; script-src 'nonce-${nonce}'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'`;
  // Browsers omit a script's attached nonce when serializing the element.
  const bridge = `<script nonce="${nonce}">${LINK_HANDLER}</script>`;
  return '<!doctype html><html><head>' + csp.outerHTML + bridge
    + '</head><body>' + template.innerHTML + '</body></html>';
}

export function HtmlArtifact({
  title,
  file,
  resolveLink,
  onOpenFile,
  showMetadata = true,
}: {
  title: string;
  file: FileContent;
  resolveLink?: (href: string) => string | undefined;
  onOpenFile?: (path: string) => void;
  showMetadata?: boolean;
}) {
  const frame = useRef<HTMLIFrameElement>(null);
  const [raw, setRaw] = useState(false);
  const invalid = file.truncated || file.integrity === 'mismatch';
  const document = useMemo(() => invalid || raw ? '' : artifactHtmlDocument(file.content), [file.content, invalid, raw]);

  useEffect(() => {
    const open = (event: MessageEvent) => {
      if (event.source !== frame.current?.contentWindow || event.origin !== 'null' ||
          event.data?.type !== MESSAGE || typeof event.data.href !== 'string') return;
      const path = resolveLink?.(event.data.href);
      if (path) onOpenFile?.(path);
    };
    window.addEventListener('message', open);
    return () => window.removeEventListener('message', open);
  }, [resolveLink, onOpenFile]);

  return (
    <section className="factory-html-artifact" data-testid="factory-runs-html-artifact">
      <div className="evidence-toolbar">
        <div className="evidence-modes" role="group" aria-label="HTML display">
          <button type="button" disabled={invalid} aria-pressed={!raw && !invalid} onClick={() => setRaw(false)}>Readable</button>
          <button type="button" aria-pressed={raw} onClick={() => setRaw(true)}>Raw</button>
        </div>
        {showMetadata && <EvidenceMetadata file={file} size={file.size} />}
      </div>
      {invalid && (
        <p role="status" data-testid="factory-runs-html-unavailable">
          {file.truncated ? 'The file preview is truncated. The complete HTML is required for the viewer.'
            : 'This HTML artifact did not match its expected digest.'}
        </p>
      )}
      {raw ? <RawDocument name={title} format="text" source={file.content} /> : !invalid && (
        <iframe ref={frame} title={title} srcDoc={document} sandbox="allow-scripts" referrerPolicy="no-referrer" />
      )}
    </section>
  );
}
