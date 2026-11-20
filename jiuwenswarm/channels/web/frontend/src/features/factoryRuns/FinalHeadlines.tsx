import { useEffect, useState } from 'react';
import { request } from './api';
import './headlines.css';

type HeadlineSource = { path: string; sha256: string };
export type HeadlineRow = {
  id: string;
  arm: string;
  cc: string | null;
  grade: string;
  ttft: string;
  decode: string;
  summary: string;
  sources: HeadlineSource[];
};

type HeadlinePublication = {
  run_id: string;
  artifact_id: string;
  sha256: string;
  source_artifacts: string[];
  payload: { schema: 'spark-final-headlines/1'; title: string; summary: string; rows: HeadlineRow[] };
};

export function useFinalHeadlines(enabled = true, refreshVersion = 0) {
  const [headlines, setHeadlines] = useState<HeadlinePublication | null>(null);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    request<HeadlinePublication | null>('/headlines', { signal: controller.signal })
      .then((value) => { if (!controller.signal.aborted) setHeadlines(value); })
      .catch(() => { if (!controller.signal.aborted) setHeadlines(null); });
    return () => controller.abort();
  }, [enabled, refreshVersion]);
  return enabled ? headlines : null;
}

export function FinalHeadlines({ publication, onOpen }: {
  publication: HeadlinePublication;
  onOpen: (runId: string, panel: 'report' | 'artifacts', artifact: string, sha256: string) => void;
}) {
  const { run_id: runId, artifact_id: artifact, sha256, payload, source_artifacts: sourceArtifacts } = publication;
  return (
    <section className="factory-headlines" data-testid="factory-final-headlines" data-sha256={sha256}
      aria-label="Headline results">
      <header>
        <div>
          <h2>{payload.title}</h2>
          <p>{payload.summary}</p>
        </div>
        <button type="button" onClick={() => onOpen(runId, 'artifacts', artifact, sha256)}>
          Open verified snapshot
        </button>
      </header>
      <div className="factory-headline-table-scroll">
        <table className="factory-measurement-table">
          <caption>Metric pairs are shown for 512 and 2,048 prompt tokens, in that order.</caption>
          <thead>
            <tr><th scope="col">Arm</th><th scope="col">Evidence grade</th><th scope="col">TTFT</th>
              <th scope="col">Decode</th><th scope="col">Finding</th></tr>
          </thead>
          <tbody>
            {payload.rows.map((row) => {
              const primary = row.sources.find(({ path, sha256 }) =>
                path.endsWith('.md') && sourceArtifacts.includes(`source:${path}@sha256:${sha256}`));
              return (
                <tr key={row.id} data-testid="factory-final-headline-row" data-arm={row.id}>
                  <th scope="row">{row.arm}</th>
                  <td><span className="factory-headline-grade">{row.grade}</span></td>
                  <td className="factory-headline-metric">{row.ttft}</td>
                  <td className="factory-headline-metric">{row.decode}</td>
                  <td>
                    {row.summary}
                    {primary && (
                      <button type="button" className="factory-headline-report"
                        aria-label={`Open source report for ${row.arm}`}
                        onClick={() => onOpen(runId, 'report', `source:${primary.path}@sha256:${primary.sha256}`, primary.sha256)}>
                        Report ↗
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function CapsuleHeadlineResults({ rows }: { rows: HeadlineRow[] }) {
  return (
    <div className="cc-headline-results" data-testid="factory-capsule-headline-results">
      {rows.map((row) => (
        <div key={row.id} data-testid="factory-capsule-headline-row" data-arm={row.id}>
          {rows.length > 1 && <strong>{row.arm}</strong>}
          <span className="factory-headline-grade">{row.grade}</span>
          <p>{row.summary}</p>
          <small>TTFT {row.ttft} · Decode {row.decode}</small>
        </div>
      ))}
    </div>
  );
}
