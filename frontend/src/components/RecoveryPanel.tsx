import { useRef, useState } from 'react'
import type { ProviderDiagnostic } from '../types/analysis'
import type { RecoveryRequest, ReviewDetail } from '../types/review'
import { useLanguage } from '../lib/i18n'
import { errorText } from '../lib/errors'
import { recoverBatches } from '../lib/reviews'

function Diagnostics({ value }: { value: ProviderDiagnostic | null }) {
  const { t } = useLanguage()
  if (!value) return <p>{t('notRecorded')}</p>
  return <dl className="audit-diagnostics text-xs">{([
    [t('providerStatus'), value.status], [t('incompleteReason'), value.incomplete_reason],
    [t('responseId'), value.response_id], [t('requestId'), value.request_id],
    [t('inputTokens'), value.input_tokens], [t('outputTokens'), value.output_tokens],
    [t('reasoningTokens'), value.reasoning_tokens], [t('requestedBudget'), value.max_output_tokens],
  ] as const).map(([label, item]) => <div key={label}><dt>{label}</dt><dd className="break-all">{item ?? t('notRecorded')}</dd></div>)}</dl>
}

export function RecoveryPanel({ review, onUpdated }: { review: ReviewDetail; onUpdated: (value: ReviewDetail) => void }) {
  const { t, language } = useLanguage()
  const view = review.recovery
  const [selected, setSelected] = useState<string[]>([])
  const [intent, setIntent] = useState<RecoveryRequest | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const inFlight = useRef(false)
  const heading = useRef<HTMLHeadingElement>(null)
  if (!view || (review.audit?.status === 'completed' && !view.attempts.length)) return null
  if (!view.supported && review.status !== 'error') return null
  const active = busy || !!view.active_request_id
  const eligible = selected.filter(id => view.eligible_batch_ids.includes(id))
  const maximum = Math.min(view.max_calls_per_action, view.remaining_review)

  async function confirm() {
    if (!intent || inFlight.current) return
    inFlight.current = true
    setBusy(true)
    setError(null)
    try {
      onUpdated(await recoverBatches(review.review_id, intent))
      setIntent(null)
      setSelected([])
    } catch (cause) { setError(cause) }
    finally {
      inFlight.current = false
      setBusy(false)
      heading.current?.focus({ preventScroll: true })
    }
  }
  return <section className="snapshot-metadata space-y-3" aria-label={t('recoveryTitle')}>
    <h2 ref={heading} tabIndex={-1}>{t('recoveryTitle')}</h2>
    <p className="text-xs text-secondary">{t('recoveryHelp')}</p>
    {!view.supported && <p className="text-warning">{view.blocked_reason === 'recovery_unavailable' ? t('recoveryUnavailable') : errorText({ code: view.blocked_reason ?? 'recovery_unavailable' }, t)}</p>}
    {!!view.active_request_id && <p role="status">{t('recoveryBusy')} <span className="font-mono">{view.active_request_id}</span></p>}
    {view.supported && <>
      <p>{t('recoveryLimits', { batch: view.max_per_batch, review: view.max_per_review, remaining: view.remaining_review })}</p>
      <fieldset disabled={active || !!intent} className="space-y-2">
        <legend>{t('recoverySelect')}</legend>
        {review.audit?.batches.map(batch => <label key={batch.batch_id} className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={selected.includes(batch.batch_id)} disabled={!view.eligible_batch_ids.includes(batch.batch_id)}
            onChange={event => setSelected(ids => event.target.checked ? [...ids, batch.batch_id] : ids.filter(id => id !== batch.batch_id))} />
          <span>{t('batchLabel')} {batch.batch_id} · {t(batch.status)}{view.batch_blockers[batch.batch_id] && <span className="block text-xs text-muted">{errorText({ code: view.batch_blockers[batch.batch_id] }, t)}</span>}</span>
        </label>)}
      </fieldset>
      {!view.eligible_batch_ids.length && !active && <p>{t('recovery_no_eligible')}</p>}
      <p>{t('recoveryCost', { count: eligible.length, budget: view.output_budget ?? t('notRecorded') })}</p>
      <button className="secondary-button" disabled={active || !!intent || !eligible.length || eligible.length > maximum || view.output_budget == null}
        onClick={() => { if (view.output_budget == null) return; setError(null); setIntent({ expected_output_budget: view.output_budget, request_id: crypto.randomUUID(), batch_ids: eligible, expected_version: view.version, confirm_paid: true }) }}>{t('recoveryReview')}</button>
    </>}
    {intent && <section role="alertdialog" aria-labelledby={`confirm-${review.review_id}`} className="rounded border border-edge-strong p-4 space-y-3">
      <h3 id={`confirm-${review.review_id}`}>{t('recoveryConfirmTitle')}</h3>
      <p>{intent.batch_ids.join(', ')}</p>
      <p>{t('recoveryCost', { count: intent.batch_ids.length, budget: view.output_budget ?? t('notRecorded') })}</p>
      <p className="break-all font-mono text-xs">{intent.request_id}</p>
      <div className="flex flex-wrap gap-3"><button className="primary-button" disabled={active} onClick={confirm}>{t('recoveryConfirm')}</button><button className="secondary-button" disabled={active} onClick={() => setIntent(null)}>{t('recoveryCancel')}</button></div>
    </section>}
    {error != null && <div role="alert" className="text-warning"><p>{errorText(error, t)}</p><p>{t('recoveryUnconfirmed')}</p></div>}
    <details><summary>{t('recoveryHistory')}</summary>
      {view.original_audit?.batches.map(batch => <details key={batch.batch_id} className="mt-3">
        <summary>{t('initialAttempt')} · {batch.batch_id} · {t(batch.status)}</summary>
        {batch.error_code && <p>{errorText({ code: batch.error_code }, t)} ({batch.error_code})</p>}
        <Diagnostics value={batch.diagnostics} />
      </details>)}
      {view.attempts.map(attempt => <details key={attempt.attempt_id} className="mt-3">
        <summary>{t('attemptLabel')} {attempt.number} · {attempt.batch_id} · {t(attempt.status)}</summary>
        <p className="break-all font-mono text-xs">{attempt.attempt_id}</p>
        <p>{new Date(attempt.created_at).toLocaleString(language)} · {t('requestedBudget')}: {attempt.output_budget}</p>
        {attempt.error_code && <p>{errorText({ code: attempt.error_code }, t)} ({attempt.error_code})</p>}
        <Diagnostics value={attempt.diagnostics} />
      </details>)}
    </details>
  </section>
}
