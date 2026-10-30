import { errorText } from '../lib/errors'
import { useLanguage } from '../lib/i18n'
import { useEffect, useState } from 'react'
import { listReviews } from '../lib/reviews'
import type { ReviewPage } from '../types/review'

export function ReviewInbox({ navigate }: { navigate: (path: string) => void }) {
  const { t, language } = useLanguage()
  const [page, setPage] = useState<ReviewPage | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [offset, setOffset] = useState(0)
  const [refresh, setRefresh] = useState(0)
  useEffect(() => {
    let active = true
    listReviews(offset).then((data) => { if (active) { setPage(data); setError(null) } })
      .catch((cause) => { if (active) setError(cause) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [offset, refresh])
  function reload(nextOffset = offset) { setLoading(true); setOffset(nextOffset); setRefresh((n) => n + 1) }
  return (
    <main className="mx-auto max-w-screen-2xl space-y-6 px-6 py-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div><h1 className="text-xl font-semibold text-white">{t('inbox')}</h1>
          <p className="mt-2 text-sm text-slate-400">{t('inboxHelp')}</p></div>
        <button className="secondary-button" disabled={loading} onClick={() => reload()}>{t('refreshInbox')}</button>
      </div>
      {loading && <p role="status">{t('loadingReviews')}</p>}
      {error != null && <p role="alert" className="text-rose-200">{errorText(error, t)}</p>}
      {!loading && !error && page?.total === 0 && <p className="text-slate-400">{t('emptyInbox')}</p>}
      {page && <ul className="space-y-3">{page.items.map((review) => (
        <li key={review.review_id} className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <a href={`/reviews/${review.review_id}`} onClick={(event) => { event.preventDefault(); navigate(`/reviews/${review.review_id}`) }} className="break-all font-semibold text-teal-200 underline">{review.repository} · {t(review.scope)}</a>
          <p className="mt-2 text-sm text-slate-400">{t(review.status)} · {new Date(review.created_at).toLocaleString(language)} · MCP</p>
          <p className="mt-2 break-all font-mono text-xs text-slate-500">{review.review_id}</p>
        </li>
      ))}</ul>}
      {page && page.total > 20 && <div className="flex gap-3">
        <button className="secondary-button" disabled={loading || offset === 0} onClick={() => reload(Math.max(0, offset - 20))}>{t('previous')}</button>
        <span className="text-sm text-slate-400">{t('pagination', { start: offset + 1, end: Math.min(offset + 20, page.total), total: page.total })}</span>
        <button className="secondary-button" disabled={loading || offset + 20 >= page.total} onClick={() => reload(offset + 20)}>{t('next')}</button>
      </div>}
    </main>
  )
}
