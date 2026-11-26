import { FileCode } from 'lucide-react';
import type { EvidenceFile } from '../api';
import { evidenceRecord, evidenceText } from './nodeEvidenceModel';

export type EvidenceLinks = { files: readonly EvidenceFile[]; onOpenFile?: (path: string) => void };

export function SourceLinks({
  source,
  ids = [],
  files,
  onOpenFile,
}: EvidenceLinks & { source?: unknown; ids?: readonly string[] }) {
  const sources = Array.isArray(source) ? source : [source];
  const refs = [
    ...new Set([
      ...ids,
      ...sources.flatMap((value) => {
        const row = evidenceRecord(value);
        return [
          evidenceText(value),
          ...[
            row?.path,
            row?.file,
            row?.artifact_id,
            row?.obs_id,
            row?.observation_id,
            row?.decision_id,
            row?.attempt_id,
            row?.record_id,
            row?.id,
            row?.ref,
            row?.section,
          ].map(evidenceText),
        ].filter((ref): ref is string => Boolean(ref));
      }),
    ]),
  ];
  if (!refs.length) return null;
  return (
    <ul className="factory-node-evidence-sources" data-testid="factory-runs-node-evidence-sources" aria-label="Sources">
      {refs.map((ref) => {
        const file = files.find(
          (entry) => entry.path === ref || entry.display_path === ref || entry.artifact_ids?.includes(ref),
        );
        return (
          <li key={ref} data-testid="factory-runs-node-evidence-source" data-variant={ref}>
            {file && onOpenFile && file.integrity !== 'missing' ? (
              <button
                className="factory-graph-file-link"
                type="button"
                onClick={() => onOpenFile(file.path)}
                data-testid="factory-runs-node-evidence-source-open"
              >
                <FileCode aria-hidden size={13} /> {file.display_path || file.path}
              </button>
            ) : (
              <code>{ref}</code>
            )}
          </li>
        );
      })}
    </ul>
  );
}
