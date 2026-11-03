import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import App from './App'
import { coverageRows, markdownReport } from './lib/audit'
import { translator, LANGUAGE_KEY } from './lib/i18n'
import { reviewFixture } from './test/reviewFixture'
import type { ReviewDetail } from './types/review'

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })
const json = (value: unknown) => new Response(JSON.stringify(value))
const captured: ReviewDetail = { ...reviewFixture, agent_source: 'muse_code', capture_coverage: {
  version: 1, include_untracked: true, untracked_seen: 3, included_untracked: ['new.py'], exclusions: { sensitive: 1, policy: 1 },
} }

it.each(['en', 'es'] as const)('exports stored evidence, decisions, ancestry and limitations safely in %s', language => {
  const review = structuredClone(captured)
  review.analysis!.summary = '```\n<script>alert(1)</script>\n```'
  review.analysis!.findings[0].reference_checks.push({ ...review.analysis!.findings[0].reference_checks[0], status: 'invalid', reason: 'quote_mismatch', diff_line: null })
  review.feedback = [{ finding_index: 0, decision: 'request_changes', comment: 'password="do-not-export-this"\nC:\\Users\\private\\secret.txt\nSaved comment', updated_at: '2026-10-31T00:00:00Z' }]
  review.parent_review_id = '22222222-2222-4222-8222-222222222222'
  const t = translator(language)
  const before = JSON.stringify(review)
  const markdown = markdownReport(review, t)
  expect(markdown).toContain('````text\n```\n<script>')
  expect(markdown).toContain(t('invalidReferences'))
  expect(markdown).toContain(t('validReferences'))
  expect(markdown).toContain('Saved comment')
  expect(markdown).toContain('Muse Code')
  expect(markdown).toContain(review.parent_review_id)
  expect(markdown).toContain(t('reportBoundary'))
  expect(markdown).toContain(t('contextHelp'))
  expect(markdown).not.toContain('do-not-export-this')
  expect(markdown).not.toContain('C:\\Users')
  expect(markdown).not.toContain(review.repository_root)
  expect(JSON.stringify(review)).toBe(before)
})

it('keeps historical and failed delivery coverage unknown, without querying the repository', () => {
  const t = translator('en')
  const rows = (review: ReviewDetail) => Object.fromEntries(coverageRows(review, t))
  expect(rows(reviewFixture)['Files sent to the model']).toBe(t('notRecorded'))
  expect(rows(captured)['Files sent to the model']).toBe('1')
  expect(rows({ ...captured, status: 'pending' })['Files sent to the model']).toBe('0')
  expect(rows({ ...captured, status: 'error', error: { code: 'model_timeout', message: '', recoverable: true } })['Files sent to the model']).toBe(t('notRecorded'))
  expect(rows({ ...captured, status: 'error', error: { code: 'analysis_too_large', message: '', recoverable: true } })['Files sent to the model']).toBe('0')
  expect(rows(captured)['New files excluded']).toBe('2')
})

it.each(['en', 'es'] as const)('filters on the server, paginates matching results and clears filters in %s', async language => {
  localStorage.setItem(LANGUAGE_KEY, language)
  window.history.replaceState(null, '', '/reviews')
  const fetchMock = vi.fn().mockResolvedValue(json({ items: [], total: 0 }))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  const t = translator(language)
  await waitFor(() => expect(screen.getByRole('button', { name: t('applyFilters') })).toBeEnabled())
  await userEvent.type(screen.getByLabelText(t('searchReview')), '1111')
  await userEvent.type(screen.getByLabelText(t('repositoryFilter')), 'demo')
  await userEvent.selectOptions(screen.getByLabelText(t('statusLabel')), 'completed')
  await userEvent.selectOptions(screen.getByLabelText(t('severity')), 'high')
  await userEvent.selectOptions(screen.getByLabelText(t('agentProvenance')), 'muse_code')
  fireEvent.change(screen.getByLabelText(t('dateFrom')), { target: { value: '2026-10-01' } })
  fireEvent.change(screen.getByLabelText(t('dateTo')), { target: { value: '2026-10-31' } })
  expect(fetchMock).toHaveBeenCalledTimes(1)
  fetchMock.mockResolvedValue(json({ items: [captured], total: 21 }))
  await userEvent.click(screen.getByRole('button', { name: t('applyFilters') }))
  await screen.findByText('Muse Code')
  const query = '?limit=20&offset=0&q=1111&repository=demo&status=completed&severity=high&agent_source=muse_code&date_from=2026-10-01&date_to=2026-10-31'
  expect(fetchMock).toHaveBeenLastCalledWith('/api/reviews' + query, { cache: 'no-store' })
  await userEvent.click(screen.getByRole('button', { name: t('next') }))
  await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith('/api/reviews' + query.replace('offset=0', 'offset=20'), { cache: 'no-store' }))
  fetchMock.mockResolvedValue(json({ items: [], total: 0 }))
  await userEvent.click(screen.getByRole('button', { name: t('clearFilters') }))
  await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith('/api/reviews?limit=20&offset=0', { cache: 'no-store' }))
  expect(screen.getByLabelText(t('searchReview'))).toHaveValue('')
})

it('downloads current stored data using GET only and leaves the feedback draft untouched', async () => {
  window.history.replaceState(null, '', `/reviews/${reviewFixture.review_id}`)
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(json(captured)))
  vi.stubGlobal('fetch', fetchMock)
  const createURL = vi.fn().mockReturnValue('blob:report')
  const revokeURL = vi.fn()
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createURL })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeURL })
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  render(<App />)
  const comment = await screen.findByRole('textbox', { name: translator('en')('humanComment') })
  await userEvent.type(comment, 'Unsaved draft')
  await userEvent.click(screen.getByRole('button', { name: 'Export Markdown' }))
  await waitFor(() => expect(createURL).toHaveBeenCalledTimes(1))
  expect(createURL.mock.calls[0][0]).toBeInstanceOf(Blob)
  expect(click).toHaveBeenCalledTimes(1)
  expect(comment).toHaveValue('Unsaved draft')
  expect(fetchMock).toHaveBeenCalledTimes(2)
  expect(fetchMock.mock.calls.every(([, options]) => !options.method)).toBe(true)
  await waitFor(() => expect(revokeURL).toHaveBeenCalledWith('blob:report'))
})
