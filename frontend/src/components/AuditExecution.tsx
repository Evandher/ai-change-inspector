import { useLanguage } from '../lib/i18n'
import { errorText } from '../lib/errors'
import type { ReviewDetail } from '../types/review'

export function AuditExecution({ review }: { review: ReviewDetail }) {
  const { t } = useLanguage()
  const audit = review.audit ?? review.analysis?.audit
  if (!audit) return null
  const unknown = t('notRecorded')
  const paths = (ids: string[]) => ids.map(id => {
    const file = review.parsed_diff.files.find(f => f.file_id === id)
    return file?.new_path ?? file?.old_path ?? id
  }).join(', ')
  return <section className="snapshot-metadata space-y-3" aria-label={t('auditRun')}>
    <h2>{t('auditRun')} · {t(audit.status)}</h2>
    {audit.status !== 'completed' && <p role="alert" className="text-warning">{t('partialAuditWarning')}</p>}
    <p>{t('auditRequests')}: {audit.request_count} / {audit.max_requests} · {t('batchLabel')}: {audit.batches.filter(b => b.status === 'completed').length} / {audit.batches.length}</p>
    <p>{t('completedHunks')}: {audit.completed_hunk_ids.length} · {t('unanalyzedHunks')}: {audit.unanalyzed_hunk_ids.length}</p>
    <p className="text-xs text-secondary">{t('batchContext')}</p>
    {!!audit.metadata_only_file_ids.length && <p>{t('metadataOnlyFiles')}: {paths(audit.metadata_only_file_ids)}</p>}
    {audit.batches.map(batch => <details key={batch.batch_id}>
      <summary>{t('batchLabel')} {batch.batch_id} · {t(batch.status)} · {paths(batch.file_ids)}</summary>
      <p className="text-xs break-all">{batch.hunk_ids.join(', ')}</p>
      <p>{t('payloadBytes')}: {batch.original_payload_bytes} → {batch.payload_bytes}</p>
      {batch.error_code && <p className="text-warning">{errorText({ code: batch.error_code }, t)} ({batch.error_code})</p>}
      {batch.diagnostics && <dl className="audit-diagnostics text-xs">
        {([
          [t('providerStatus'), batch.diagnostics.status],
          [t('diagnosticOutcome'), batch.diagnostics.outcome],
          [t('incompleteReason'), batch.diagnostics.incomplete_reason],
          [t('providerError'), batch.diagnostics.provider_error_code],
          [t('responseId'), batch.diagnostics.response_id],
          [t('requestId'), batch.diagnostics.request_id],
          [t('inputTokens'), batch.diagnostics.input_tokens],
          [t('outputTokens'), batch.diagnostics.output_tokens],
          [t('reasoningTokens'), batch.diagnostics.reasoning_tokens],
          ['max_output_tokens', batch.diagnostics.max_output_tokens],
        ] as const).map(([label, value]) => <div key={label}><dt>{label}</dt><dd className="break-all">{value ?? unknown}</dd></div>)}
      </dl>}
    </details>)}
  </section>
}
