import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { RecoveryPanel } from './components/RecoveryPanel'
import { ReviewDetail as DetailPage } from './components/ReviewDetail'
import { LanguageProvider } from './components/LanguageProvider'
import { translator, LANGUAGE_KEY } from './lib/i18n'
import { reviewFixture } from './test/reviewFixture'
import type { ReviewDetail } from './types/review'
import type { AuditRun } from './types/analysis'

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })
const batch = { batch_id: 'batch-1', file_ids: ['file_test'], hunk_ids: ['hunk_test'], status: 'completed' as const, error_code: null, diagnostics: null, payload_bytes: 500, original_payload_bytes: 1000 }
const audit: AuditRun = { version: 1, status: 'partial', max_requests: 4, request_count: 2, completed_hunk_ids: ['hunk_test'], unanalyzed_hunk_ids: ['hunk_2'], metadata_only_file_ids: [], batches: [batch, { ...batch, batch_id: 'batch-2', hunk_ids: ['hunk_2'], status: 'incomplete', error_code: 'model_output_budget' }] }
const partial: ReviewDetail = {
  ...reviewFixture, status: 'error', audit, error: { code: 'audit_partial', message: '', recoverable: true },
  analysis: { ...reviewFixture.analysis!, audit },
  recovery: { supported: true, blocked_reason: null, version: 0, active_request_id: null, eligible_batch_ids: ['batch-2'], batch_blockers: { 'batch-1': 'recovery_completed' }, attempts: [], max_calls_per_action: 4, max_per_batch: 2, max_per_review: 4, remaining_review: 4, output_budget: 8192, original_status: 'error', original_finished_at: reviewFixture.finished_at, original_audit: audit },
}
const json = (value: unknown) => new Response(JSON.stringify(value))

it.each(['en', 'es'] as const)('requires explicit selection and paid confirmation in %s', async language => {
  localStorage.setItem(LANGUAGE_KEY, language)
  const t = translator(language)
  const fetch = vi.fn().mockResolvedValue(json(partial))
  vi.stubGlobal('fetch', fetch)
  const updated = vi.fn()
  render(<LanguageProvider><RecoveryPanel review={partial} onUpdated={updated} /></LanguageProvider>)
  expect(fetch).not.toHaveBeenCalled()
  expect(screen.getByRole('checkbox', { name: /batch-1/ })).toBeDisabled()
  expect(screen.getByRole('button', { name: t('recoveryReview') })).toBeDisabled()
  await userEvent.click(screen.getByRole('checkbox', { name: /batch-2/ }))
  await userEvent.click(screen.getByRole('button', { name: t('recoveryReview') }))
  const dialog = screen.getByRole('alertdialog', { name: t('recoveryConfirmTitle') })
  expect(within(dialog).getByText(t('recoveryCost', { count: 1, budget: 8192 }))).toBeVisible()
  expect(fetch).not.toHaveBeenCalled()
  await userEvent.click(within(dialog).getByRole('button', { name: t('recoveryConfirm') }))
  await waitFor(() => expect(updated).toHaveBeenCalledWith(partial))
  expect(fetch).toHaveBeenCalledTimes(1)
  const [url, options] = fetch.mock.calls[0]
  expect(url).toBe(`/api/reviews/${partial.review_id}/recovery`)
  expect(options.headers['X-Inspector-Request']).toBe('1')
  expect(JSON.parse(options.body)).toEqual({ request_id: expect.any(String), batch_ids: ['batch-2'], expected_version: 0, expected_output_budget: 8192, confirm_paid: true })
})

it('cancels confirmation without any request', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  render(<LanguageProvider><RecoveryPanel review={partial} onUpdated={() => {}} /></LanguageProvider>)
  await userEvent.click(screen.getByRole('checkbox', { name: /batch-2/ }))
  await userEvent.click(screen.getByRole('button', { name: 'Review recovery action' }))
  await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  expect(fetch).not.toHaveBeenCalled()
})

it('reuses the same confirmation ID after a lost response', async () => {
  const fetch = vi.fn().mockRejectedValueOnce(new Error('network')).mockResolvedValueOnce(json(partial))
  vi.stubGlobal('fetch', fetch)
  render(<LanguageProvider><RecoveryPanel review={partial} onUpdated={() => {}} /></LanguageProvider>)
  await userEvent.click(screen.getByRole('checkbox', { name: /batch-2/ }))
  await userEvent.click(screen.getByRole('button', { name: 'Review recovery action' }))
  await userEvent.click(screen.getByRole('button', { name: 'Confirm and send selected batches' }))
  await screen.findByRole('alert')
  await userEvent.click(screen.getByRole('button', { name: 'Confirm and send selected batches' }))
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
  expect(fetch.mock.calls[0][1].body).toBe(fetch.mock.calls[1][1].body)
})

it('blocks historical and active reviews without invoking recovery', () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  const { rerender } = render(<LanguageProvider><RecoveryPanel review={{ ...partial, recovery: { ...partial.recovery!, supported: false, blocked_reason: 'recovery_unavailable', eligible_batch_ids: [] } }} onUpdated={() => {}} /></LanguageProvider>)
  expect(screen.getByText(/no reproducible recovery recipe/)).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Review recovery action' })).not.toBeInTheDocument()
  rerender(<LanguageProvider><RecoveryPanel review={{ ...partial, recovery: { ...partial.recovery!, active_request_id: 'active' } }} onUpdated={() => {}} /></LanguageProvider>)
  expect(screen.getByRole('button', { name: 'Review recovery action' })).toBeDisabled()
  expect(screen.getByRole('checkbox', { name: /batch-2/ })).toBeDisabled()
  expect(fetch).not.toHaveBeenCalled()
})

it.each(['en', 'es'] as const)('shows original and recovered attempt history in %s', async language => {
  localStorage.setItem(LANGUAGE_KEY, language)
  const t = translator(language)
  const attempted: ReviewDetail = { ...partial, recovery: { ...partial.recovery!, version: 1, attempts: [{ attempt_id: 'attempt-uuid', request_id: 'request-uuid', batch_id: 'batch-2', number: 2, status: 'incomplete', created_at: reviewFixture.created_at, started_at: reviewFixture.created_at, finished_at: reviewFixture.finished_at, output_budget: 4096, error_code: 'model_output_budget', diagnostics: null }] } }
  render(<LanguageProvider><RecoveryPanel review={attempted} onUpdated={() => {}} /></LanguageProvider>)
  await userEvent.click(screen.getByText(t('recoveryHistory'), { exact: true }))
  expect(screen.getByText(`${t('initialAttempt')} · batch-2 · ${t('incomplete')}`)).toBeVisible()
  expect(screen.getByText(`${t('attemptLabel')} 2 · batch-2 · ${t('incomplete')}`)).toBeVisible()
})

it('keeps the original feedback draft mounted after successful recovery', async () => {
  const recovered = { ...partial, status: 'completed', audit: { ...audit, status: 'completed' }, recovery: { ...partial.recovery!, version: 1, eligible_batch_ids: [] } }
  const fetch = vi.fn().mockResolvedValueOnce(json(partial)).mockResolvedValueOnce(json(recovered))
  vi.stubGlobal('fetch', fetch)
  render(<LanguageProvider><DetailPage id={partial.review_id} navigate={() => {}} /></LanguageProvider>)
  const draft = await screen.findByRole('textbox', { name: 'Optional comment (up to 4,000 characters)' })
  await userEvent.type(draft, 'Keep my draft')
  await userEvent.click(screen.getByRole('checkbox', { name: /batch-2/ }))
  await userEvent.click(screen.getByRole('button', { name: 'Review recovery action' }))
  await userEvent.click(screen.getByRole('button', { name: 'Confirm and send selected batches' }))
  await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument())
  expect(draft).toHaveValue('Keep my draft')
  expect(fetch).toHaveBeenCalledTimes(2)
})
