import { render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { AuditExecution } from './components/AuditExecution'
import { ReviewDetail } from './components/ReviewDetail'
import { ReviewSnapshot } from './components/ReviewSnapshot'
import { translator, LANGUAGE_KEY } from './lib/i18n'
import { LanguageProvider } from './components/LanguageProvider'
import { markdownReport } from './lib/audit'
import { reviewFixture } from './test/reviewFixture'
import type { AuditRun } from './types/analysis'

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })

const hunk = reviewFixture.parsed_diff.files[0].hunks[0]
const audit: AuditRun = {
  version: 1, status: 'partial', max_requests: 4, request_count: 2,
  completed_hunk_ids: [hunk.hunk_id], unanalyzed_hunk_ids: ['hunk-not-analyzed'],
  metadata_only_file_ids: [],
  batches: [
    { batch_id: 'batch-1', file_ids: [reviewFixture.parsed_diff.files[0].file_id], hunk_ids: [hunk.hunk_id], status: 'completed', error_code: null, diagnostics: null, payload_bytes: 500, original_payload_bytes: 1000 },
    { batch_id: 'batch-2', file_ids: [], hunk_ids: ['hunk-not-analyzed'], status: 'incomplete', error_code: 'model_output_budget', payload_bytes: 600, original_payload_bytes: 1200,
      diagnostics: { status: 'incomplete', response_id: 'resp_mock', request_id: null, incomplete_details_present: true, incomplete_reason: 'max_output_tokens', provider_error_code: null, http_status: null, input_tokens: 1000, output_tokens: 8192, reasoning_tokens: null, max_output_tokens: 8192, outcome: 'budget' } },
  ],
}
const partial = {
  ...reviewFixture, status: 'error' as const, audit,
  error: { code: 'audit_partial', message: '', recoverable: true },
  analysis: { ...reviewFixture.analysis!, audit, findings: reviewFixture.analysis!.findings.map(f => ({ ...f, batch_ids: ['batch-1'] })) },
}

it.each(['en', 'es'] as const)('shows partial coverage and available diagnostics in %s', language => {
  localStorage.setItem(LANGUAGE_KEY, language)
  const t = translator(language)
  render(<LanguageProvider><AuditExecution review={partial} /></LanguageProvider>)
  const panel = screen.getByRole('region', { name: t('auditRun') })
  expect(within(panel).getByText(t('partialAuditWarning'))).toBeVisible()
  expect(within(panel).getAllByText('max_output_tokens')).toHaveLength(2)
  expect(within(panel).getByText('resp_mock')).toBeInTheDocument()
  expect(within(panel).getByText('hunk-not-analyzed')).toBeInTheDocument()
  const reasoning = within(panel).getByText(t('reasoningTokens')).parentElement!
  expect(reasoning).toHaveTextContent(t('notRecorded'))
  expect(reasoning).not.toHaveTextContent('7000')
})

it('keeps historical diagnostics absent rather than fabricating them', () => {
  render(<LanguageProvider><AuditExecution review={reviewFixture} /></LanguageProvider>)
  expect(screen.queryByRole('region')).not.toBeInTheDocument()
})

it('shows completed findings and their batch origin without triggering analysis', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(partial)))
  vi.stubGlobal('fetch', fetch)
  localStorage.setItem(LANGUAGE_KEY, 'en')
  render(<LanguageProvider><ReviewDetail id={partial.review_id} navigate={() => {}} /></LanguageProvider>)
  await screen.findByText(partial.analysis.findings[0].hypothesis.title)
  expect(screen.getByText('Batch: batch-1')).toBeVisible()
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(fetch).toHaveBeenCalledWith(`/api/reviews/${partial.review_id}`, { cache: 'no-store' })
  expect(screen.queryByRole('button', { name: 'Analyze pending snapshot' })).not.toBeInTheDocument()
})

it('keeps parent and child execution coverage independent', () => {
  localStorage.setItem(LANGUAGE_KEY, 'en')
  const child = { ...partial, audit: { ...audit, status: 'completed' as const, unanalyzed_hunk_ids: [] } }
  render(<LanguageProvider><ReviewSnapshot review={partial} side="parent" /><ReviewSnapshot review={child} side="child" /></LanguageProvider>)
  const parent = screen.getByRole('region', { name: 'Parent snapshot' })
  const next = screen.getByRole('region', { name: 'Child snapshot' })
  expect(within(parent).getByRole('heading', { name: 'Audit execution · Partial' })).toBeVisible()
  expect(within(next).getByRole('heading', { name: 'Audit execution · Completed' })).toBeVisible()
})

it.each(['en', 'es'] as const)('exports partial status, coverage, diagnostics and origins in %s', language => {
  const t = translator(language)
  const markdown = markdownReport(partial, t)
  expect(markdown).toContain(t('partialAuditWarning'))
  expect(markdown).toContain('max_output_tokens')
  expect(markdown).toContain(`${t('batchLabel')}: batch-1`)
  expect(markdown).toContain('hunk-not-analyzed')
  expect(markdown).toContain(`${t('inputTokens')}: 1000`)
  expect(markdown).toContain(`${t('reasoningTokens')}: ${t('notRecorded')}`)
})


it.each(['en', 'es'] as const)('uses an accurate coverage warning with zero findings in %s', language => {
  localStorage.setItem(LANGUAGE_KEY, language)
  const t = translator(language)
  const empty = { ...partial, analysis: null, audit: { ...audit, status: 'incomplete' as const, completed_hunk_ids: [] } }
  const { rerender } = render(<LanguageProvider><AuditExecution review={empty} /></LanguageProvider>)
  const expected = language === 'en'
    ? 'Incomplete coverage: only completed batches contribute results. This is not a successful full audit.'
    : 'Cobertura incompleta: solo los lotes completados aportan resultados. No es una auditoría completa exitosa.'
  expect(screen.getByRole('alert')).toHaveTextContent(expected)
  rerender(<LanguageProvider><AuditExecution review={{ ...partial, analysis: { ...partial.analysis, findings: [] } }} /></LanguageProvider>)
  expect(screen.getByRole('alert')).toHaveTextContent(expected)
  expect(markdownReport(empty, t)).toContain(expected)
})
