import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, Copy, Download, FileCode2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { plannerApi, type GraphTlaInfo } from './plannerApi';

export function GraphTlaInspector({
  planId,
  info,
}: {
  planId: string;
  info?: GraphTlaInfo | null;
}) {
  const { i18n } = useTranslation();
  const t = useMemo(() => i18n.getFixedT('en'), [i18n]);
  const [fullSource, setFullSource] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [loadingFull, setLoadingFull] = useState(false);
  const [copied, setCopied] = useState(false);
  const [loadErr, setLoadErr] = useState('');
  const codeWrapRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setFullSource(null);
    setExpanded(false);
    setLoadErr('');
  }, [planId]);

  const loadFullSource = async (): Promise<string | null> => {
    if (fullSource !== null) return fullSource;
    setLoadingFull(true);
    setLoadErr('');
    try {
      const text = await plannerApi.graphTlaText(planId);
      setFullSource(text);
      return text;
    } catch (err) {
      setLoadErr(String(err instanceof Error ? err.message : err));
      return null;
    } finally {
      setLoadingFull(false);
    }
  };

  const handleToggleFull = async () => {
    if (!expanded && fullSource === null) {
      await loadFullSource();
    }
    setExpanded((v) => !v);
  };

  const handleCopy = async () => {
    const text = (await loadFullSource()) ?? info?.preview ?? '';
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard may be restricted in non-HTTPS contexts
    }
  };

  const displayedText = useMemo(() => {
    if (expanded && fullSource !== null) return fullSource;
    return fullSource ?? info?.preview ?? '';
  }, [expanded, fullSource, info?.preview]);

  const lines = useMemo(() => displayedText.split('\n'), [displayedText]);

  const jumpToLine = async (lineNumber: number) => {
    if (lineNumber > lines.length && fullSource === null) {
      await loadFullSource();
    }
    setExpanded(true);
    window.requestAnimationFrame(() => {
      const wrap = codeWrapRef.current;
      if (!wrap) return;
      const target = wrap.querySelector(`[data-line="${lineNumber}"]`) as HTMLElement | null;
      if (target) {
        wrap.scrollTop = Math.max(0, target.offsetTop - wrap.offsetTop - 16);
      }
    });
  };

  return (
    <section className="factory-planner-block planner-tla-inspector" data-testid="factory-planner-tla-inspector">
      <div className="factory-detail-header">
        <div>
          <h3>
            <FileCode2 size={16} style={{ verticalAlign: '-2px', marginRight: 6 }} aria-hidden />
            {t('factoryPlanner.tlaInspector.title')}
          </h3>
          <p className="factory-muted">{t('factoryPlanner.tlaInspector.lead')}</p>
        </div>
        <div className="planner-btn-row">
          <button type="button" className="planner-btn" onClick={() => void handleToggleFull()} disabled={loadingFull}>
            {loadingFull
              ? t('factoryRuns.loading')
              : expanded
                ? t('factoryPlanner.tlaInspector.collapse')
                : t('factoryPlanner.tlaInspector.loadFull')}
          </button>
          <button type="button" className="planner-btn" onClick={() => void handleCopy()}>
            {copied ? <Check size={14} aria-hidden /> : <Copy size={14} aria-hidden />}
            {copied ? t('factoryPlanner.tlaInspector.copied') : t('factoryPlanner.tlaInspector.copy')}
          </button>
          <a
            className="planner-btn is-primary"
            href={plannerApi.graphTlaUrl(planId)}
            download="graph.tla"
            target="_blank"
            rel="noreferrer"
          >
            <Download size={14} aria-hidden />
            {t('factoryPlanner.downloadGraphTla')}
          </a>
        </div>
      </div>

      {info && (
        <div className="planner-tla-meta" data-testid="factory-planner-tla-meta">
          <div className="planner-btn-row" style={{ marginTop: 0 }}>
            <span className={`planner-badge ${info.roundtrip_consistent ? 'is-good' : 'is-warn'}`}>
              {info.roundtrip_consistent
                ? t('factoryPlanner.tlaInspector.roundtripOk')
                : t('factoryPlanner.tlaInspector.roundtripMismatch')}
            </span>
            <span className="planner-badge is-info">
              {t('factoryPlanner.tlaInspector.parseSpeed', { ms: info.parse_ms })}
            </span>
            <span className="planner-badge">
              {t('factoryPlanner.tlaInspector.stats', {
                lines: info.lines,
                kb: (info.bytes / 1024).toFixed(1),
                nodes: info.parsed_nodes,
              })}
            </span>
          </div>
          <small className="factory-muted" title={info.sha256}>
            SHA-256: <code>{info.sha256.slice(0, 12)}</code>
          </small>
        </div>
      )}

      {info?.sections && info.sections.length > 0 && (
        <div className="planner-tla-sections" aria-label="TLA+ sections">
          {info.sections.map((sec) => (
            <button
              key={sec.id}
              type="button"
              className="planner-btn"
              onClick={() => void jumpToLine(sec.line)}
            >
              {sec.label} <span className="factory-muted">L{sec.line}</span>
            </button>
          ))}
        </div>
      )}

      {loadErr && <p className="factory-error">{loadErr}</p>}

      {lines.length > 0 && (
        <div className="planner-tla-code-wrap" ref={codeWrapRef}>
          {lines.map((lineText, idx) => {
            const lineno = idx + 1;
            const isMarker = lineText.includes('\\* -- ') || lineText.startsWith('ASSUME ') || lineText.startsWith('NodeSpec ==');
            return (
              <div
                key={lineno}
                data-line={lineno}
                className={`planner-tla-line${isMarker ? ' is-marker' : ''}`}
              >
                <span className="planner-tla-lineno">{lineno}</span>
                <span className="planner-tla-linetext">{lineText || ' '}</span>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
