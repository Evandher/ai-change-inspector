import { ReviewLink } from './ReviewLink'
import { FeedbackEditor } from './FeedbackEditor'
import { errorText } from '../lib/errors'
import { useLanguage } from '../lib/i18n'
import { useEffect, useState } from 'react'
import { analyzeReview, getReview } from '../lib/reviews'
import type { ReviewDetail as Review } from '../types/review'
import { DiffExplorer } from './DiffExplorer'
import { FindingsPanel } from './FindingsPanel'
import { Icon } from './Icon'

export function ReviewDetail({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const { t, language } = useLanguage()
  const [review, setReview] = useState<Review | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)
  const [refresh, setRefresh] = useState(0)
  useEffect(() => {
    let active = true
    getReview(id).then((data) => { if (active) { setReview(data); setError(null) } })
      .catch((cause) => { if (active) setError(cause) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id, refresh])
  async function analyze() {
    setLoading(true)
    setError(null)
    try { setReview(await analyzeReview(id)) }
    catch (cause) { setError(cause) }
    finally { setLoading(false) }
  }
  return (
    <main className="review-detail-page space-y-6">
      <div className="page-head">
        <div>{review && <div className="eyebrow"><Icon name="folder" />{review.repository}</div>}<h1 aria-label={t('detail')}>{t('reviewLabel')} <span className="font-mono">{id.slice(0, 8)}</span></h1>
          <p>{t('detailHelp')}</p></div>
        <div className="head-actions"><button className="secondary-button" disabled={loading} onClick={() => { setLoading(true); setRefresh((n) => n + 1) }}>{t('refreshReview')}</button><ReviewLink href={`/reviews/${id}/evolution`} navigate={navigate}><Icon name="history" />{t('viewEvolution')}</ReviewLink></div>
      </div>
      {loading && <p role="status" className={review ? 'sr-only' : undefined}>{t('loadingSnapshot')}</p>}
      {error != null && <p role="alert" className="text-danger">{errorText(error, t)}</p>}
      {review && <>
        <section className="snapshot-metadata" aria-label={t('snapshotData')}>
          <div className="review-metadata"><span>{new Date(review.created_at).toLocaleString(language)}</span><span>{t(review.scope)} · MCP</span><span>{t('files', { count: review.parsed_diff.files.length })}</span><span className="text-success">+{review.parsed_diff.additions}</span><span className="text-danger">−{review.parsed_diff.deletions}</span><span className={`status-badge status-${review.status}`}>{t(review.status)}</span></div>
          <details><summary className="text-xs text-muted">{t('snapshotData')}</summary>
            <p className="mt-3 text-xs text-secondary">{t('immutable')}</p>
            <p className="mt-3 break-all font-mono text-xs text-secondary">{id}</p>
            <p className="mt-3 break-all text-xs text-secondary">{review.repository_root}</p>
            <p className="mt-2 break-all font-mono text-xs text-muted">SHA-256: {review.diff_sha256}</p>
          </details>
          {review.error && <p role="alert" className="text-danger">{errorText(review.error, t)} ({review.error.code})</p>}
          {review.status === 'analyzing' && <p className="text-sm text-secondary">{t('inProgress')}</p>}
          {review.status === 'pending' && <div><button className="secondary-button" disabled={loading} onClick={analyze}>{t('analyzePending')}</button><p className="mt-2 text-xs text-secondary">{t('pendingCredits')}</p></div>}
        </section>
        <nav aria-label={t('relatedReviews')} className="flex flex-wrap gap-3 text-sm text-accent-hover">
          {review.parent_review_id && <ReviewLink href={`/reviews/${review.parent_review_id}/compare/${id}`} navigate={navigate}>{t('compareParent')}</ReviewLink>}
          {review.parent_review_id && <ReviewLink href={`/reviews/${review.parent_review_id}`} navigate={navigate}>{t('previousReview')}</ReviewLink>}
          {review.child_review_ids?.map((id) => <ReviewLink key={id} href={`/reviews/${id}`} navigate={navigate} ariaLabel={`${t('nextReview')} · ${id}`}>{t('nextReview')} · {id.slice(0, 8)}</ReviewLink>)}
        </nav>
        <div className="grid items-start gap-6 review-layout">
          <DiffExplorer result={review.parsed_diff} />
          <FindingsPanel analysis={review.analysis} loading={false} error="" canReview={false} onReview={() => {}} readOnly renderFeedback={(index) => {
              const feedback = review.feedback?.find((item) => item.finding_index === index)
              return <FeedbackEditor key={`${index}-${feedback?.updated_at ?? 'pending'}`} reviewId={id} index={index} feedback={feedback} />
            }} />
        </div>
        <details className="rounded-lg border border-edge p-4"><summary className="cursor-pointer text-sm">{t('originalDiff')}</summary>
          <textarea aria-label={t('originalDiff')} readOnly spellCheck={false} wrap="off" value={review.diff} className="mt-4 h-64 w-full rounded bg-canvas p-3 font-mono text-xs" /></details>
      </>}
    </main>
  )
}
