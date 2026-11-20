import { useTranslation } from 'react-i18next';
import type { EvidenceFile } from '../api';
import { useViewerLabels } from './viewerLabels';
import './dataViewer.css';

export function DigestBadge({ file }: { file: EvidenceFile }) {
  const { t } = useTranslation();
  const actual = file.sha256 || '';
  const expected = file.expected_sha256 || '';
  return (
    <span
      className="factory-digest evidence-digest"
      data-integrity={file.integrity}
      data-testid="factory-runs-digest"
      title={[actual, expected].filter(Boolean).join('\n')}
    >
      {t(`factoryRuns.${file.integrity}`)}
      {(actual || expected) && <> · {(actual || expected).slice(0, 12)}</>}
    </span>
  );
}

function formatSize(size: number, lang: string) {
  const format = (fraction: number) => new Intl.NumberFormat(lang, { maximumFractionDigits: fraction });
  if (size < 1024) return `${format(0).format(size)} B`;
  if (size < 1024 ** 2) return `${format(1).format(size / 1024)} KiB`;
  if (size < 1024 ** 3) return `${format(1).format(size / 1024 ** 2)} MiB`;
  return `${format(1).format(size / 1024 ** 3)} GiB`;
}

export function EvidenceMetadata({ file, size }: { file?: EvidenceFile; size: number }) {
  const { label, lang } = useViewerLabels();
  const bytes = file?.size ?? size;
  return (
    <div className="evidence-metadata" data-testid="factory-runs-file-metadata">
      {file ? (
        <DigestBadge file={file} />
      ) : (
        <span className="evidence-digest" data-testid="factory-runs-digest" data-integrity="unavailable">
          {label('noFileDigest')}
        </span>
      )}
      <span className="evidence-size" data-testid="factory-runs-file-size" title={`${bytes} B`}>
        {!file && `${label('previewSize')} · `}
        {formatSize(bytes, lang)}
      </span>
    </div>
  );
}
