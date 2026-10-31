import { useEffect, useState } from 'react'
import { useLanguage } from '../lib/i18n'
import { errorText } from '../lib/errors'
import { listReviews } from '../lib/reviews'
import type { ReviewPage } from '../types/review'
import { ReviewTable } from './ReviewTable'
import { ReviewLink } from './ReviewLink'
import { Icon } from './Icon'

export function Overview({ navigate }: { navigate: (path: string) => void }) {
  const { t, language } = useLanguage()
  const [page, setPage] = useState<ReviewPage | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [refresh, setRefresh] = useState(0)
  useEffect(() => {
    let active = true
    listReviews().then((data) => { if (active) { setPage(data); setError(null) } })
      .catch((cause) => { if (active) setError(cause) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [refresh])
  const metrics = page ? [
    { label: t('totalReviews'), count: page.total, help: t('allRecordedReviews'), icon: 'inbox' as const, status: '' },
    { label: t('completed'), count: page.items.filter((item) => item.status === 'completed').length, help: t('latestBatch'), icon: 'file' as const, status: '' },
    { label: t('awaitingAnalysis'), count: page.items.filter((item) => item.status === 'pending' || item.status === 'analyzing').length, help: t('latestBatch'), icon: 'history' as const, status: 'warning' },
    { label: t('error'), count: page.items.filter((item) => item.status === 'error').length, help: t('latestBatch'), icon: 'alert' as const, status: 'danger' },
  ] : []
  return <main className="overview-page space-y-6">
    <div className="page-head"><div><h1>{t('overview')}</h1><p>{t('overviewHelp')}</p></div><div className="head-actions"><button className="secondary-button" disabled={loading} onClick={() => { setLoading(true); setRefresh((n) => n + 1) }}>{t('refreshInbox')}</button><ReviewLink href="/diff" navigate={navigate}>{t('manual')}</ReviewLink></div></div>
    {loading && <p role="status" className={page ? 'sr-only' : undefined}>{t('loadingReviews')}</p>}
    {error != null && <p role="alert" className="text-danger">{errorText(error, t)}</p>}
    {page && !error && <>
      <section className="overview-metrics" aria-label={t('overviewCounts')}>
        {metrics.map((metric) => <article className={`metric ${metric.status}`} key={metric.icon}><div className="metric-label"><Icon name={metric.icon} /><h2>{metric.label}</h2></div><p className="metric-value">{metric.count.toLocaleString(language)}</p><p className="metric-help">{metric.help}</p></article>)}
      </section>
      <p className="text-xs text-muted">{t('overviewScope', { count: page.items.length, total: page.total })}</p>
      <section className="inbox-ledger" aria-label={t('recentReviews')}><div className="ledger-heading"><div><h2>{t('recentReviews')}</h2><p>{t('recentReviewsHelp')}</p></div><ReviewLink href="/reviews" navigate={navigate} variant="quiet">{t('viewAllReviews')}<Icon name="arrow" /></ReviewLink></div>
        {page.items.length > 0 ? <ReviewTable items={page.items.slice(0, 5)} navigate={navigate} /> : <p className="empty-ledger">{t('emptyInbox')}</p>}
        <div className="ledger-footer">{t('openingIsReadOnly')}</div>
      </section>
      <section className="orientation-note"><Icon name="info" /><div><h2>{t('recordNotVerdict')}</h2><p>{t('overviewBoundary')}</p></div></section>
    </>}
  </main>
}
