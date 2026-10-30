import { FeedbackEditor } from './FeedbackEditor'
import { errorText } from '../lib/errors'
import { useLanguage } from '../lib/i18n'
import { useEffect, useState } from 'react'
import { analyzeReview, getReview } from '../lib/reviews'
import type { ReviewDetail as Review } from '../types/review'
import { DiffExplorer } from './DiffExplorer'
import { FindingsPanel } from './FindingsPanel'

export function ReviewDetail({ id }: { id: string }) {
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
    <main className="mx-auto max-w-screen-2xl space-y-6 px-6 py-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><h1 className="text-xl font-semibold text-white">{t('detail')}</h1>
          <p className="mt-2 break-all font-mono text-xs text-slate-400">{id}</p></div>
        <button className="secondary-button" disabled={loading} onClick={() => { setLoading(true); setRefresh((n) => n + 1) }}>{t('refreshReview')}</button>
      </div>
      {loading && <p role="status">{t('loadingSnapshot')}</p>}
      {error != null && <p role="alert" className="text-rose-200">{errorText(error, t)}</p>}
      {review && <>
        <section className="space-y-3 rounded-xl border border-slate-800 bg-slate-900 p-5" aria-label={t('snapshotData')}>
          <p>{review.repository} · {t(review.scope)} · MCP · {new Date(review.created_at).toLocaleString(language)}</p>
          <p className="break-all text-sm text-slate-400">{review.repository_root}</p>
          <p className="text-teal-200">{t(review.status)}</p>
          <p className="break-all font-mono text-xs text-slate-500">SHA-256: {review.diff_sha256}</p>
          <p className="text-sm text-slate-400">{t('immutable')}</p>
          {review.error && <p role="alert" className="text-rose-200">{errorText(review.error, t)} ({review.error.code})</p>}
          {review.status === 'analyzing' && <p className="text-sm text-slate-400">{t('inProgress')}</p>}
          {review.status === 'pending' && <div><button className="secondary-button" disabled={loading} onClick={analyze}>{t('analyzePending')}</button><p className="mt-2 text-xs text-slate-400">{t('pendingCredits')}</p></div>}
        </section>
        <nav aria-label={t('relatedReviews')} className="flex flex-wrap gap-3 text-sm text-teal-200">
          {review.parent_review_id && <a className="underline" href={`/reviews/${review.parent_review_id}`}>{t('previousReview')}</a>}
          {review.child_review_ids?.map((id) => <a key={id} className="underline" href={`/reviews/${id}`}>{t('nextReview')} · {id}</a>)}
        </nav>
        <details className="rounded-xl border border-slate-800 p-4"><summary className="cursor-pointer text-sm">{t('originalDiff')}</summary>
          <textarea aria-label={t('originalDiff')} readOnly spellCheck={false} value={review.diff} className="mt-4 h-64 w-full rounded bg-slate-950 p-3 font-mono text-xs" /></details>
        <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_19rem]">
          <DiffExplorer result={review.parsed_diff} />
          <FindingsPanel analysis={review.analysis} loading={false} error="" canReview={false} onReview={() => {}} readOnly renderFeedback={(index) => {
              const feedback = review.feedback?.find((item) => item.finding_index === index)
              return <FeedbackEditor key={`${index}-${feedback?.updated_at ?? 'pending'}`} reviewId={id} index={index} feedback={feedback} />
            }} />
        </div>
      </>}
    </main>
  )
}
