import { useLanguage } from '../lib/i18n'
import type { ReviewSummary } from '../types/review'
import { ReviewLink } from './ReviewLink'
import { Icon } from './Icon'

export function ReviewTable({ items, navigate }: { items: ReviewSummary[]; navigate: (path: string) => void }) {
  const { t, language } = useLanguage()
  return <div className="review-table-wrap" role="region" tabIndex={0} aria-label={t('inbox')}>
    <table className="review-table" aria-label={t('inbox')}>
      <thead><tr><th scope="col">{t('repositoryLabel')}</th><th scope="col">{t('statusLabel')}</th><th scope="col">{t('receivedLabel')}</th><th scope="col">{t('actionsLabel')}</th></tr></thead>
      <tbody>{items.map((review) => <tr key={review.review_id}>
        <td className="review-identity"><div className="repo-title"><Icon name="folder" />{review.repository}</div>
          <a href={`/reviews/${review.review_id}`} className="review-link" aria-label={`${review.repository} · ${t(review.scope)}`} aria-describedby={`review-meta-${review.review_id}`} onClick={(event) => {
            if (!event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) { event.preventDefault(); navigate(`/reviews/${review.review_id}`) }
          }}>{t('reviewLabel')} <span className="font-mono">{review.review_id.slice(0, 8)}</span></a>
          <div className="review-meta-row"><p className="review-id" id={`review-meta-${review.review_id}`}>{review.review_id}</p><p className="review-subtitle">MCP · {t(review.scope)}</p></div>
        </td>
        <td><span className={`status-badge status-${review.status}`}>{t(review.status)}</span></td>
        <td><time dateTime={review.created_at}>{new Date(review.created_at).toLocaleDateString(language)}<span className="block text-muted mt-1">{new Date(review.created_at).toLocaleTimeString(language)}</span></time></td>
        <td><div className="table-actions"><ReviewLink href={`/reviews/${review.review_id}`} navigate={navigate}>{t('viewReview')}<Icon name="arrow" /></ReviewLink><ReviewLink href={`/reviews/${review.review_id}/evolution`} navigate={navigate} variant="quiet">{t('viewEvolution')}</ReviewLink></div></td>
      </tr>)}</tbody>
    </table>
  </div>
}
