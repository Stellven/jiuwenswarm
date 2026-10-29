import '../../styles/research-shell.css';
import { useTranslation } from 'react-i18next';
import type { ResearchMetricRow } from './researchArtifacts';

/** Show recorded values only; the view never aggregates or judges measurements. */
export function ResearchMeasurementsView({ rows, verdict }: { rows: ResearchMetricRow[]; verdict: boolean }) {
  const { t } = useTranslation();
  const side = (value: number | null, reason?: string | null) => (
    <>
      <p>{value === null ? t('researchShell.measurements.unavailable') : String(value)}</p>
      {reason && (
        <p className="text-xs text-text-muted">
          {t(`researchShell.measurements.reasons.${reason}`, { defaultValue: reason })}
        </p>
      )}
    </>
  );
  return (
    <div className="research-measurements" data-testid="team-area-research-measurements">
      <table className="w-full text-left text-sm" data-testid="team-area-research-measurements-table">
        <caption className="mb-2 text-left text-text-muted" data-testid="team-area-research-measurements-caption">
          {t('researchShell.measurements.recordedOnly')}
        </caption>
        <thead>
          <tr>
            {['metric', 'baseline', 'treatment', verdict ? 'classification' : 'delta', 'details'].map((field) => (
              <th
                key={field}
                scope="col"
                className="px-2 py-2 font-medium"
                data-testid="team-area-research-measurement-heading"
                data-variant={field}
              >
                {t(`researchShell.measurements.${field}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              className="align-top"
              data-testid="team-area-research-measurement-row"
              data-variant={row.id}
            >
              <th scope="row" className="px-2 py-2 font-medium" data-testid="team-area-research-measurement-name">
                {row.id}
                {row.unit ? ` (${row.unit})` : ''}
              </th>
              <td className="px-2 py-2" data-testid="team-area-research-measurement-baseline">
                {side(row.baseline, row.baselineReason)}
              </td>
              <td className="px-2 py-2" data-testid="team-area-research-measurement-treatment">
                {side(row.treatment, row.treatmentReason)}
              </td>
              <td className="px-2 py-2" data-testid="team-area-research-measurement-result">
                {verdict
                  ? row.classification
                  : row.delta === null
                    ? t('researchShell.measurements.unavailable')
                    : String(row.delta)}
              </td>
              <td className="px-2 py-2">
                <details data-testid="team-area-research-measurement-details">
                  <summary className="cursor-pointer" data-testid="team-area-research-measurement-details-toggle">
                    {t('researchShell.sourceDetails')}
                  </summary>
                  <pre className="whitespace-pre-wrap break-words text-xs">{JSON.stringify(row.details, null, 2)}</pre>
                </details>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
