import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import App from './App'
import { reviewFixture } from './test/reviewFixture'
import { translator } from './lib/i18n'

afterEach(() => vi.unstubAllGlobals())
const json = (data: unknown) => new Response(JSON.stringify(data))
const items = (['completed', 'completed', 'pending', 'analyzing', 'error', 'completed'] as const).map((status, index) => ({ ...reviewFixture, status, review_id: `${index}1111111-1111-4111-8111-111111111111` }))

it('keeps the existing table usable during an explicit refresh and blocks duplicate refreshes', async () => {
  window.history.replaceState(null, '', '/')
  let finish!: (response: Response) => void
  const fetchMock = vi.fn().mockResolvedValueOnce(json({ items, total: 6 }))
    .mockImplementationOnce(() => new Promise<Response>((resolve) => { finish = resolve }))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  const table = await screen.findByRole('table')
  const refresh = screen.getByRole('button', { name: 'Refresh inbox' })
  await userEvent.click(refresh)
  expect(refresh).toBeDisabled()
  expect(screen.getByRole('table')).toBe(table)
  expect(screen.getByRole('table')).toBeVisible()
  await userEvent.click(refresh)
  expect(fetchMock).toHaveBeenCalledTimes(2)
  await act(async () => finish(json({ items, total: 6 })))
  expect(refresh).toBeEnabled()
})

it.each(['en', 'es'] as const)('opens Overview as the landing page and labels bounded counts in %s', async (language) => {
  window.history.replaceState(null, '', '/')
  localStorage.setItem('ai-change-inspector.language', language)
  const t = translator(language)
  const fetchMock = vi.fn().mockResolvedValue(json({ items, total: 90 }))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  expect(screen.getByRole('heading', { name: t('overview') })).toBeInTheDocument()
  const metrics = within(await screen.findByRole('region', { name: t('overviewCounts') }))
  for (const [label, count] of [[t('totalReviews'), '90'], [t('completed'), '3'], [t('awaitingAnalysis'), '2'], [t('error'), '1']]) {
    expect(within(metrics.getByRole('heading', { name: label }).closest('article')!).getByText(count)).toBeInTheDocument()
  }
  expect(screen.getByText(t('overviewScope', { count: 6, total: 90 }))).toBeInTheDocument()
  expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(6)
  expect(fetchMock).toHaveBeenCalledExactlyOnceWith('/api/reviews?limit=20&offset=0', { cache: 'no-store' })
  await userEvent.click(screen.getByRole('link', { name: t('viewAllReviews') }))
  expect(window.location.pathname).toBe('/reviews')
  expect(fetchMock.mock.calls.every(([, options]) => !options.method)).toBe(true)
})

it('distinguishes loading, failed and empty counts without inventing zeroes on failure', async () => {
  window.history.replaceState(null, '', '/')
  let finish!: (response: Response) => void
  const fetchMock = vi.fn().mockImplementationOnce(() => new Promise<Response>((resolve) => { finish = resolve }))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading reviews')
  expect(screen.queryByRole('region', { name: 'Recorded review counts' })).not.toBeInTheDocument()
  await act(async () => finish(json({ items: [], total: 0 })))
  expect(await screen.findByText(/No reviews yet/)).toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  fetchMock.mockRejectedValue(new TypeError('offline'))
  await userEvent.click(screen.getByRole('button', { name: 'Refresh inbox' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Check that the backend is running')
  expect(screen.queryByRole('region', { name: 'Recorded review counts' })).not.toBeInTheDocument()
})

it('keeps the manual parser available at its dedicated route without loading reviews', async () => {
  window.history.replaceState(null, '', '/')
  const fetchMock = vi.fn().mockResolvedValue(json({ items: [], total: 0 }))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  await screen.findByText(/No reviews yet/)
  await userEvent.click(within(screen.getByRole('navigation', { name: 'Main navigation' })).getByRole('link', { name: 'Manual inspection' }))
  expect(window.location.pathname).toBe('/diff')
  expect(screen.getByRole('button', { name: 'Parse diff' })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})
