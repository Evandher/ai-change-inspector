import { useEffect, useState } from 'react'
import { useLanguage } from '../lib/i18n'
import { errorText } from '../lib/errors'
import { compareReviews } from '../lib/reviews'
import type { ReviewComparison } from '../types/review'
import { ReviewLink } from './ReviewLink'
import { ReviewSnapshot } from './ReviewSnapshot'

export function ReviewCompare({ id, otherId, navigate, embedded = false }: { id: string; otherId: string; navigate: (path: string) => void; embedded?: boolean }) {
  const { t } = useLanguage()
  const [comparison, setComparison] = useState<ReviewComparison | null>(null)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    let active = true
    compareReviews(id, otherId).then((data) => { if (active) setComparison(data) })
      .catch((cause) => { if (active) setError(cause) })
    return () => { active = false }
  }, [id, otherId])
  const Container = embedded ? 'section' : 'main'
  return <Container className="comparison-view space-y-6">
    {embedded ? <h2 className="text-lg font-semibold">{t('comparisonTitle')}</h2> : <h1>{t('comparisonTitle')}</h1>}
    <p className="comparison-notice">{t('comparisonWarning')}</p>
    {!embedded && <nav className="flex flex-wrap gap-4" aria-label={t('relatedReviews')}>
      <ReviewLink href={`/reviews/${id}/evolution`} navigate={navigate}>{t('viewEvolution')}</ReviewLink>
      {comparison && <><ReviewLink href={`/reviews/${comparison.parent.review_id}`} navigate={navigate}>{t('previousReview')}</ReviewLink>
        <ReviewLink href={`/reviews/${comparison.child.review_id}`} navigate={navigate}>{t('nextReview')}</ReviewLink></>}
    </nav>}
    {error != null ? <p role="alert">{errorText(error, t)}</p> : !comparison && <p role="status">{t('loadingComparison')}</p>}
    {comparison && <div className="overflow-x-auto" role="region" tabIndex={0} aria-label={t('comparisonPanels')}>
      <div className="comparison-grid items-start">
        <ReviewSnapshot review={comparison.parent} side="parent" />
        <ReviewSnapshot review={comparison.child} side="child" />
      </div>
    </div>}
  </Container>
}
