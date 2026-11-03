import type { Translate } from './i18n'
import type { AgentSource, ReviewDetail } from '../types/review'

export function agentLabel(source: AgentSource | undefined, t: Translate) {
  return ({ muse_code: 'Muse Code', codex: 'Codex', claude_code: 'Claude Code', other: t('agentOther'), unknown: t('agentUnknown') })[source ?? 'unknown']
}

export function coverageRows(review: ReviewDetail, t: Translate): [string, string][] {
  const coverage = review.capture_coverage
  const audit = review.audit ?? review.analysis?.audit
  const unknown = t('notRecorded')
  // Historical reports did not record delivery; never reconstruct from today's repository.
  const preflight = ['no_text_changes', 'analysis_too_large', 'model_not_configured', 'sensitive_path', 'possible_secret', 'unsafe_diff_path', 'unsupported_change', 'unauthorized_repository']
  const sent = !coverage ? unknown : review.status === 'pending' || preflight.includes(review.error?.code ?? '') ? '0' : review.status === 'completed' ? String(review.parsed_diff.files.length) : unknown
  const rows: [string, string][] = [
    [t('captureScope'), t(review.scope)],
    [t('capturedFiles'), String(review.parsed_diff.files.length)],
    [audit ? t('completedBatchFiles') : t('submittedFiles'), audit ? String(new Set(audit.batches.filter(b => b.status === 'completed').flatMap(b => b.file_ids)).size) : sent],
    [t('untrackedSeen'), coverage?.untracked_seen == null ? unknown : String(coverage.untracked_seen)],
    [t('untrackedIncluded'), coverage ? String(coverage.included_untracked.length) : unknown],
    [t('untrackedExcluded'), coverage?.untracked_seen == null ? unknown : String(Object.values(coverage.exclusions).reduce((a, b) => a + (b ?? 0), 0))],
  ]
  const labels = { policy: t('policy'), sensitive: t('sensitive'), binary: t('binary'), too_large: t('largeFile'), unsafe: t('unsafe'), encoding: t('encoding'), budget: t('budget') }
  if (coverage) for (const [reason, count] of Object.entries(coverage.exclusions)) rows.push([labels[reason as keyof typeof labels], String(count)])
  return rows
}

// Markdown is a download, never interpreted as instructions or inserted into the DOM.
// All untrusted strings stay inside fences longer than any backtick run in the data.
export function redactReport(value: string) {
  return value
    .replace(/-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----/g, '[REDACTED]')
    .replace(/\b(?:gh[pousr]_[\w-]{20,}|github_pat_[\w-]{20,}|(?:AKIA|ASIA)[A-Z0-9]{16}|xox[baprs]-[\w-]{15,}|eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,})\b/g, '[REDACTED]')
    .replace(/\b(?:bearer\s+\S+|(?:[\w-]*(?:api[_-]?key|token|password|passwd|secret)[\w-]*)["']?\s*[:=]\s*[^\r\n]+)/gi, '[REDACTED]')
    .replace(/https?:\/\/[^/\s:@]+:[^/\s@]+@/g, 'https://[REDACTED]@')
    .replace(/(?:[A-Za-z]:[\\/]|\\\\)[^\r\n]+/g, '[LOCAL PATH REDACTED]')
    .replace(/(?:^|[\s"'])(\/(?:[^\s/]+\/)+[^\s]*)/gm, ' [LOCAL PATH REDACTED]')
    .split('').filter(c => c === '\n' || c === '\t' || c.charCodeAt(0) >= 32 && c.charCodeAt(0) !== 127).join('')
}

function block(value: string) {
  const text = redactReport(value)
  let length = 3
  for (const match of text.matchAll(/`+/g)) length = Math.max(length, match[0].length + 1)
  const fence = '`'.repeat(length)
  return `${fence}text\n${text}\n${fence}\n`
}

export function markdownReport(review: ReviewDetail, t: Translate) {
  const parts = ['# AI Change Inspector', t('reportBoundary'), t('reportPrivacy'), '## ' + t('snapshotData'), block([
    `ID: ${review.review_id}`, `${t('receivedLabel')}: ${review.created_at}`,
    `${t('repositoryLabel')}: ${review.repository}`, `${t('captureScope')}: ${t(review.scope)}`,
    `${t('agentProvenance')}: ${agentLabel(review.agent_source, t)}`,
    `${t('statusLabel')}: ${t(review.status)}`, `SHA-256: ${review.diff_sha256}`,
    review.error ? `Error: ${review.error.code}` : '',
  ].filter(Boolean).join('\n')), t('provenanceHelp'), '## ' + t('diffFiles')]
  for (const file of review.parsed_diff.files) parts.push(block(`${file.old_path ?? ''} → ${file.new_path ?? ''}\n${t(file.change_type)} · +${file.additions} −${file.deletions}${file.is_binary ? '\n' + t('binary') : ''}`))
  const audit = review.audit ?? review.analysis?.audit
  if (audit) {
    parts.push('## ' + t('auditRun'), block(`${t(audit.status)}\n${t('auditRequests')}: ${audit.request_count}/${audit.max_requests}\n${t('completedHunks')}: ${audit.completed_hunk_ids.length}\n${t('unanalyzedHunks')}: ${audit.unanalyzed_hunk_ids.length}`), t('batchContext'))
    if (audit.status !== 'completed') parts.push(t('partialAuditWarning'))
    for (const batch of audit.batches) {
      parts.push(block(JSON.stringify(batch, null, 2)))
      // Only validated numeric metrics bypass generic secret-name redaction.
      if (batch.diagnostics) for (const [label, value] of [
        [t('inputTokens'), batch.diagnostics.input_tokens],
        [t('outputTokens'), batch.diagnostics.output_tokens],
        [t('reasoningTokens'), batch.diagnostics.reasoning_tokens],
      ] as const) parts.push(`${label}: ${typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : t('notRecorded')}`)
    }
  }
  if (review.recovery?.attempts.length) parts.push('## ' + t('recoveryHistory'), block(JSON.stringify(review.recovery, null, 2)))
  parts.push('## ' + t('summary'), block(review.analysis?.summary ?? t('notRecorded')))
  if (review.analysis?.findings.length === 0) parts.push(t('noFindings'))
  for (const [index, finding] of (review.analysis?.findings ?? []).entries()) {
    if (finding.attempt_ids?.length) parts.push(block(`${t('attemptOrigin')}: ${finding.attempt_ids.join(', ')}`))
    if (finding.batch_ids?.length) parts.push(block(`${t('batchLabel')}: ${finding.batch_ids.join(', ')}`))
    parts.push(`## ${t('findings')} ${index + 1}`, block(`${finding.hypothesis.title}\n${t('severity')} ${t(finding.hypothesis.severity)}\n${finding.hypothesis.explanation}`))
    for (const check of finding.reference_checks) parts.push('### ' + t(check.status === 'valid' ? 'validReferences' : 'invalidReferences'), block([
      `${check.reference.path} · ${check.reference.side}:${check.reference.line_start}–${check.reference.line_end}`,
      `file_id: ${check.reference.file_id}`, `hunk_id: ${check.reference.hunk_id}`,
      `diff_line: ${check.diff_line ?? t('notRecorded')}`, t(check.reason), check.reference.quote,
    ].join('\n')))
    parts.push('### ' + t('tests'), ...finding.hypothesis.suggested_tests.map(block))
    const feedback = review.feedback.find(item => item.finding_index === index)
    parts.push('### ' + t('humanFeedback'), block(feedback ? `${feedback.decision ? t(feedback.decision) : t('decisionPending')}\n${feedback.comment}\n${feedback.updated_at ?? ''}` : t('decisionPending')))
  }
  parts.push('## ' + t('auditCoverage'), block(coverageRows(review, t).map(([label, value]) => `${label}: ${value}`).join('\n')),
    ...(review.capture_coverage?.included_untracked.map(block) ?? []), t('coverageHelp'), t('contextHelp'), t('auditLimits'),
    '## ' + t('relatedReviews'), block(`${t('parentLabel')}: ${review.parent_review_id ?? t('notRecorded')}\n${t('nextReview')}: ${review.child_review_ids.join(', ') || t('notRecorded')}`))
  return parts.join('\n\n') + '\n'
}
