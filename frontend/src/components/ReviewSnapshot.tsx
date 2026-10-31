import type { HumanFeedback, ReviewDetail } from '../types/review'
import { useLanguage } from '../lib/i18n'
import { errorText } from '../lib/errors'
import { DiffExplorer } from './DiffExplorer'
import { FindingsPanel } from './FindingsPanel'

function HumanFeedbackView({ feedback }: { feedback?: HumanFeedback }) {
  const { t, language } = useLanguage()
  return <section aria-label={t('feedbackReadOnly')} className="space-y-2 rounded border border-edge-strong p-3">
    <h4 className="text-sm font-semibold">{t('feedbackReadOnly')}</h4>
    <p className="text-xs text-warning">{feedback?.decision ? t(feedback.decision) : t('decisionPending')}</p>
    <p className="whitespace-pre-wrap break-words text-sm">{feedback?.comment || t('noComment')}</p>
    {feedback?.updated_at && <p className="text-xs text-secondary">{t('modifiedAt')}: {new Date(feedback.updated_at).toLocaleString(language)}</p>}
  </section>
}

export function ReviewSnapshot({ review, side }: { review: ReviewDetail; side: 'parent' | 'child' }) {
  const { t, language } = useLanguage()
  const prefix = `compare-${side}-`
  const title = t(side === 'parent' ? 'parentSnapshot' : 'childSnapshot')
  return <section aria-label={title} className="snapshot-panel space-y-3">
    <header className="snapshot-card-header">
    <div className="snapshot-heading"><h2>{title}</h2><span className="font-mono">{review.review_id.slice(0, 8)}</span></div>
    <p className="text-xs">{review.repository} · {t(review.scope)} · {t(review.status)} · {new Date(review.created_at).toLocaleString(language)}</p>
    <details className="text-xs text-secondary"><summary>{t('snapshotData')}</summary><p className="mt-2 break-all font-mono">{review.review_id}</p><p className="mt-2 leading-5">{t('readOnlySnapshot')}</p></details>
    {review.error && <p role="alert">{errorText(review.error, t)} ({review.error.code})</p>}
    {review.status === 'pending' && <p role="status">{t('pendingSnapshot')}</p>}
    {review.status === 'analyzing' && <p role="status">{t('inProgress')}</p>}
    </header>
    <DiffExplorer result={review.parsed_diff} idPrefix={prefix} />
    <FindingsPanel analysis={review.analysis} loading={false} error="" canReview={false} onReview={() => {}} readOnly idPrefix={prefix}
      renderFeedback={(index) => <HumanFeedbackView feedback={review.feedback.find((item) => item.finding_index === index)} />} />
    <details><summary className="cursor-pointer text-sm">{t('originalDiff')}</summary>
      <p className="mt-3 break-all font-mono text-xs text-secondary">SHA-256: {review.diff_sha256}</p>
      <textarea aria-label={`${title} · ${t('originalDiff')}`} readOnly spellCheck={false} wrap="off" value={review.diff} className="mt-3 h-56 w-full rounded bg-canvas p-3 font-mono text-xs" /></details>
  </section>
}
