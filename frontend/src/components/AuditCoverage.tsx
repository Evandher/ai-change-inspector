import { useLanguage } from '../lib/i18n'
import { coverageRows } from '../lib/audit'
import type { ReviewDetail } from '../types/review'

export function AuditCoverage({ review }: { review: ReviewDetail }) {
  const { t } = useLanguage()
  return <details className="snapshot-metadata audit-coverage">
    <summary>{t('auditCoverage')}</summary>
    <dl>{coverageRows(review, t).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    {!!review.capture_coverage?.included_untracked.length && <details><summary>{t('untrackedIncluded')}</summary><ul>{review.capture_coverage.included_untracked.map(path => <li key={path} className="break-all font-mono text-xs">{path}</li>)}</ul></details>}
    <p>{t('coverageHelp')}</p><p>{t('contextHelp')}</p><p>{t('auditLimits')}</p>
  </details>
}
