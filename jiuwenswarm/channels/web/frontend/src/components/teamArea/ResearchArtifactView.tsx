import '../../styles/research-shell.css';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../ui';
import { artifactStanding, artifactText, structuredResearchArtifact } from './researchArtifacts';
import type { ResearchArtifact } from './researchArtifacts';
import type { ResearchRef } from '../../utils/researchClient';
import { ResearchMeasurementsView } from './ResearchMeasurementsView';

export function ResearchArtifactView({
  artifact,
  accepted,
  candidates,
}: {
  artifact: ResearchArtifact;
  accepted: ResearchRef[];
  candidates: ResearchRef[];
}) {
  const { t } = useTranslation();
  const [raw, setRaw] = useState(false);
  const projection = structuredResearchArtifact(artifact.content);
  const standing = artifactStanding(artifact, accepted, candidates);
  return (
    <section className="research-document" data-testid="team-area-research-document" data-variant={artifact.path}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium" data-testid="team-area-research-document-standing" data-variant={standing}>
          {t(`researchShell.standing.${standing}`)}
        </p>
        {projection && (
          <Button onClick={() => setRaw(!raw)} aria-pressed={raw} data-testid="team-area-research-document-source-btn">
            {t(raw ? 'researchShell.readableView' : 'researchShell.sourceView')}
          </Button>
        )}
      </div>
      {projection && !raw ? (
        <div className="space-y-4" data-testid="team-area-research-document-summary">
          <h3 className="font-semibold" data-testid="team-area-research-document-title">
            {t(`researchShell.documents.${projection.kind}`)}
          </h3>
          {projection.metrics && (
            <ResearchMeasurementsView rows={projection.metrics} verdict={projection.kind === 'verdict'} />
          )}
          {projection.sections.map((section) => {
            const values = Array.isArray(section.value) ? section.value : [section.value];
            return (
              <section
                key={section.key}
                className="space-y-1"
                data-testid="team-area-research-document-section"
                data-variant={section.key}
              >
                <h4
                  className="font-medium"
                  data-testid="team-area-research-document-section-title"
                  data-variant={section.key}
                >
                  {t(`researchShell.sections.${section.key}`)}
                </h4>
                {values.length === 0 && (
                  <p
                    className="text-text-muted"
                    data-testid="team-area-research-document-empty"
                    data-variant={section.key}
                  >
                    {t('researchShell.noneRecorded')}
                  </p>
                )}
                <ul className="space-y-2" data-testid="team-area-research-document-items" data-variant={section.key}>
                  {values.map((value, index) => {
                    const row = artifactText(value);
                    const id = value && typeof value === 'object' && 'id' in value ? String(value.id) : String(index);
                    return (
                      <li
                        key={id}
                        className="whitespace-pre-wrap break-words"
                        data-testid="team-area-research-document-item"
                        data-variant={id}
                      >
                        <p>{row.text}</p>
                        {row.detail !== null && (
                          <details data-testid="team-area-research-document-provenance" data-variant={id}>
                            <summary
                              className="cursor-pointer text-text-muted"
                              data-testid="team-area-research-document-provenance-toggle"
                              data-variant={id}
                            >
                              {t('researchShell.sourceDetails')}
                            </summary>
                            <pre className="overflow-auto whitespace-pre-wrap break-words text-xs">
                              {JSON.stringify(row.detail, null, 2)}
                            </pre>
                          </details>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </section>
            );
          })}
        </div>
      ) : (
        <pre
          className="overflow-auto whitespace-pre-wrap break-words"
          data-testid="team-area-research-artifact-content"
        >
          {artifact.content}
        </pre>
      )}
      <details data-testid="team-area-research-document-identity">
        <summary className="cursor-pointer text-text-muted" data-testid="team-area-research-document-identity-toggle">
          {t('researchShell.fileIdentity')}
        </summary>
        <p className="break-all">{artifact.path}</p>
        <p className="break-all">{artifact.ref.id}</p>
        <p className="break-all">{artifact.ref.sha256}</p>
      </details>
    </section>
  );
}
