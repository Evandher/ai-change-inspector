import { useState } from 'react'
import { useLanguage } from '../lib/i18n'
import { errorText } from '../lib/errors'
import { saveFeedback } from '../lib/reviews'
import type { HumanFeedback, Decision } from '../types/review'
import { Icon } from './Icon'

export function FeedbackEditor({ reviewId, index, feedback }: { reviewId: string; index: number; feedback?: HumanFeedback }) {
  const { t, language } = useLanguage()
  const [saved, setSaved] = useState(feedback)
  const [decision, setDecision] = useState<Decision | ''>(feedback?.decision ?? '')
  const [comment, setComment] = useState(feedback?.comment ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const dirty = decision !== (saved?.decision ?? '') || comment !== (saved?.comment ?? '')
  async function save() {
    if (!decision) return
    setBusy(true); setError(null)
    try { setSaved(await saveFeedback(reviewId, index, { decision, comment })) }
    catch (cause) { setError(cause) }
    finally { setBusy(false) }
  }
  return <section className="feedback-editor space-y-3" aria-label={t('humanFeedback')}>
    <h4 className="feedback-title"><Icon name="person" />{t('humanFeedback')}</h4>
    <p role="status" className="text-xs text-warning">{saved?.decision ? t(saved.decision) : t('decisionPending')}{dirty && ` · ${t('unsaved')}`}</p>
    <fieldset className="feedback-decisions" disabled={busy}><legend>{t('humanDecision')}</legend>
      <div className="decision-options">{(['request_changes', 'accept_risk', 'dismiss'] as const).map((value) => <label className="decision-option" key={value}>
        <input type="radio" name={`decision-${reviewId}-${index}`} value={value} checked={decision === value} onChange={() => setDecision(value)} />
        <span>{t(value)}</span>
      </label>)}</div>
    </fieldset>
    <label className="block text-xs">{t('humanComment')}
      <textarea aria-label={t('humanComment')} className="mt-2 w-full rounded bg-canvas p-2" rows={3} maxLength={4000} value={comment} disabled={busy} onChange={(event) => setComment(event.target.value)} />
    </label>
    <button type="button" className="primary-button" disabled={busy || !decision || !dirty} onClick={save}>{busy ? t('savingFeedback') : t('saveFeedback')}</button>
    {saved?.updated_at && <p className="text-xs text-secondary">{t('modifiedAt')}: {new Date(saved.updated_at).toLocaleString(language)}</p>}
    <p className="text-xs text-secondary">{t('humanFeedbackHelp')}</p>
    {error != null && <p role="alert">{errorText(error, t)}</p>}
  </section>
}
