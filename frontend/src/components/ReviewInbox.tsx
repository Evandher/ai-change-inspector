import { ReviewTable } from './ReviewTable'
import { ReviewLink } from './ReviewLink'
import { errorText } from '../lib/errors'
import { useLanguage } from '../lib/i18n'
import { useEffect, useState } from 'react'
import { listReviews } from '../lib/reviews'
import type { ReviewPage } from '../types/review'

export function ReviewInbox({ navigate }: { navigate: (path: string) => void }) {
  const { t } = useLanguage()
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
    <main className="inbox-page mx-auto max-w-screen-2xl space-y-6 px-6 py-8">
      <div className="page-head">
        <div><h1 className="text-xl font-semibold text-primary">{t('inbox')}</h1>
          <p className="mt-2 text-sm text-secondary">{t('inboxHelp')}</p></div>
        <div className="head-actions"><button className="secondary-button" disabled={loading} onClick={() => reload()}>{t('refreshInbox')}</button><ReviewLink href="/diff" navigate={navigate}>{t('manual')}</ReviewLink></div>
      </div>
      {loading && <p role="status" className={page ? 'sr-only' : undefined}>{t('loadingReviews')}</p>}
      {error != null && <p role="alert" className="text-danger">{errorText(error, t)}</p>}
      {!loading && !error && page?.total === 0 && <p className="text-secondary">{t('emptyInbox')}</p>}
      {page && page.items.length > 0 && <section className="inbox-ledger" aria-label={t('submittedReviews')}>
        <div className="ledger-heading"><div><h2>{t('submittedReviews')}</h2><p>{t('inboxHelp')}</p></div><span>{t('reviewCount', { count: page.total })}</span></div>
        <ReviewTable items={page.items} navigate={navigate} />
      <div className="ledger-footer"><span>{t('inboxSnapshotHelp')}</span><span>{t('pagination', { start: offset + 1, end: offset + page.items.length, total: page.total })}</span></div></section>}
      {page && page.total > 20 && <div className="flex gap-3">
        <button className="secondary-button" disabled={loading || offset === 0} onClick={() => reload(Math.max(0, offset - 20))}>{t('previous')}</button>
        <span className="text-sm text-secondary">{t('pagination', { start: offset + 1, end: Math.min(offset + 20, page.total), total: page.total })}</span>
        <button className="secondary-button" disabled={loading || offset + 20 >= page.total} onClick={() => reload(offset + 20)}>{t('next')}</button>
      </div>}
    </main>
  )
}
