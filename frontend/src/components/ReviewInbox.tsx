import { ReviewTable } from './ReviewTable'
import { ReviewLink } from './ReviewLink'
import { errorText } from '../lib/errors'
import { useLanguage } from '../lib/i18n'
import { useEffect, useState } from 'react'
import { listReviews } from '../lib/reviews'
import type { ReviewFilters } from '../lib/reviews'
import { agentLabel } from '../lib/audit'
import type { ReviewPage } from '../types/review'

export function ReviewInbox({ navigate }: { navigate: (path: string) => void }) {
  const { t } = useLanguage()
  const [page, setPage] = useState<ReviewPage | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [offset, setOffset] = useState(0)
  const [refresh, setRefresh] = useState(0)
  const [draft, setDraft] = useState<ReviewFilters>({})
  const [filters, setFilters] = useState<ReviewFilters>({})
  function filterValue(key: keyof ReviewFilters, value: string) { setDraft(current => ({ ...current, [key]: value })) }
  function applyFilters(next: ReviewFilters) { setFilters(next); setOffset(0); setLoading(true); setPage(null); setRefresh(n => n + 1) }
  const hasFilters = Object.values(filters).some(Boolean)
  useEffect(() => {
    let active = true
    listReviews(offset, filters).then((data) => { if (active) { setPage(data); setError(null) } })
      .catch((cause) => { if (active) setError(cause) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [offset, refresh, filters])
  function reload(nextOffset = offset) { setLoading(true); setOffset(nextOffset); setRefresh((n) => n + 1) }
  return (
    <main className="inbox-page mx-auto max-w-screen-2xl space-y-6 px-6 py-8">
      <div className="page-head">
        <div><h1 className="text-xl font-semibold text-primary">{t('inbox')}</h1>
          <p className="mt-2 text-sm text-secondary">{t('inboxHelp')}</p></div>
        <div className="head-actions"><button className="secondary-button" disabled={loading} onClick={() => reload()}>{t('refreshInbox')}</button><ReviewLink href="/diff" navigate={navigate}>{t('manual')}</ReviewLink></div>
      </div>
      <form className="review-filters" aria-label={t('filters')} onSubmit={event => { event.preventDefault(); applyFilters(draft) }}>
        <label>{t('searchReview')}<input value={draft.q ?? ''} maxLength={36} pattern="[0-9a-f-]*" onChange={event => filterValue('q', event.target.value.toLowerCase())} /></label>
        <label>{t('repositoryFilter')}<input value={draft.repository ?? ''} maxLength={64} pattern="[A-Za-z0-9_-]*" onChange={event => filterValue('repository', event.target.value)} /></label>
        <label>{t('statusLabel')}<select value={draft.status ?? ''} onChange={event => filterValue('status', event.target.value)}><option value="">{t('allValues')}</option>{(['pending','analyzing','completed','error'] as const).map(value => <option key={value} value={value}>{t(value)}</option>)}</select></label>
        <label>{t('severity')}<select value={draft.severity ?? ''} onChange={event => filterValue('severity', event.target.value)}><option value="">{t('allValues')}</option>{(['low','medium','high','critical'] as const).map(value => <option key={value} value={value}>{t(value)}</option>)}</select></label>
        <label>{t('agentProvenance')}<select value={draft.agent_source ?? ''} onChange={event => filterValue('agent_source', event.target.value)}><option value="">{t('allValues')}</option>{(['muse_code','codex','claude_code','other','unknown'] as const).map(value => <option key={value} value={value}>{agentLabel(value, t)}</option>)}</select></label>
        <label>{t('dateFrom')}<input type="date" value={draft.date_from ?? ''} max={draft.date_to || undefined} onChange={event => filterValue('date_from', event.target.value)} /></label>
        <label>{t('dateTo')}<input type="date" value={draft.date_to ?? ''} min={draft.date_from || undefined} onChange={event => filterValue('date_to', event.target.value)} /></label>
        <div className="flex flex-wrap items-end gap-3"><button className="secondary-button" disabled={loading}>{t('applyFilters')}</button><button type="button" className="secondary-button" onClick={() => { setDraft({}); applyFilters({}) }}>{t('clearFilters')}</button></div>
        <p className="text-xs text-secondary">{t('newestFirst')} · {t('provenanceHelp')}</p>
      </form>
      {loading && <p role="status" className={page ? 'sr-only' : undefined}>{t('loadingReviews')}</p>}
      {error != null && <p role="alert" className="text-danger">{errorText(error, t)}</p>}
      {!loading && !error && page?.total === 0 && <p className="text-secondary">{t(hasFilters ? 'noMatches' : 'emptyInbox')}</p>}
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
