import { useEffect, useState } from 'react'
import { useLanguage } from '../lib/i18n'
import { errorText } from '../lib/errors'
import { getTimeline } from '../lib/reviews'
import type { ReviewTimeline } from '../types/review'
import { ReviewLink } from './ReviewLink'
import { ReviewCompare } from './ReviewCompare'

export function ReviewEvolution({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const { t, language } = useLanguage()
  const [timeline, setTimeline] = useState<ReviewTimeline | null>(null)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    let active = true
    getTimeline(id).then((data) => { if (active) setTimeline(data) })
      .catch((cause) => { if (active) setError(cause) })
    return () => { active = false }
  }, [id])
  const selected = timeline?.items.find((item) => item.review_id === id)
  const parent = selected?.parent_review_id && timeline?.items.some((item) => item.review_id === selected.parent_review_id) ? selected.parent_review_id : null
  const child = timeline?.items.find((item) => item.parent_review_id === id)
  const pair = parent ? [parent, id] : selected && !selected.parent_review_id && child ? [id, child.review_id] : null
  return <main className="evolution-page space-y-6">
    <div className="page-head"><div><h1>{t('evolutionTitle')}</h1><p>{t('evolutionHelp')}</p></div><ReviewLink href={`/reviews/${id}`} navigate={navigate}>{t('viewReview')}</ReviewLink></div>
    {error != null ? <p role="alert">{errorText(error, t)}</p> : !timeline && <p role="status">{t('loadingEvolution')}</p>}
    {timeline && <>
      {timeline.incomplete && <p role="status" className="text-warning">{t('incompleteEvolution')}</p>}
      {timeline.truncated && <p role="status" className="text-warning">{t('truncatedEvolution')}</p>}
      <ol aria-label={t('evolutionTitle')} className="timeline">
        {timeline.items.map((item) => <li key={item.review_id} className={`timeline-node${item.review_id === id ? ' is-selected' : ''}`}>
          <span aria-hidden="true" className="timeline-dot" />
          <ReviewLink href={`/reviews/${item.review_id}`} navigate={navigate} current={item.review_id === id} variant="text" ariaLabel={item.review_id}>{item.review_id.slice(0, 8)}</ReviewLink>
          {item.review_id === id && <span className="timeline-selection">{t('currentReview')}</span>}
          <p className="text-xs text-secondary">{new Date(item.created_at).toLocaleString(language)} · {t(item.scope)}</p>
          <p className="timeline-relationship text-xs text-secondary"><span title={item.parent_review_id ?? undefined}>{item.parent_review_id ? `${t('parentLabel')}: ${item.parent_review_id.slice(0, 8)}` : t('rootReview')}</span><span className={`timeline-status status-${item.status}`}>{t(item.status)}</span></p>
          {item.parent_review_id && timeline.items.some((parent) => parent.review_id === item.parent_review_id) && <ReviewLink href={`/reviews/${item.parent_review_id}/compare/${item.review_id}`} navigate={navigate} variant="quiet">{t('compareParent')}</ReviewLink>}
        </li>)}
      </ol>
      {timeline.missing_review_ids.map((missing) => <p key={missing} className="break-all text-sm text-warning">{t('missingSnapshot')}: {missing}</p>)}
      {pair && <><p className="text-xs text-muted">{t('evolutionPairHelp')}</p><ReviewCompare key={pair.join('-')} id={pair[0]} otherId={pair[1]} navigate={navigate} embedded /></>}
    </>}
  </main>
}
