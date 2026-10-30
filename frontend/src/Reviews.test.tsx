import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import App from './App'
import { reviewFixture } from './test/reviewFixture'

afterEach(() => vi.unstubAllGlobals())

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status })

it('opens the inbox and a persisted detail without requesting another model analysis', async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(json({ items: [reviewFixture], total: 1 }))
    .mockResolvedValueOnce(json(reviewFixture))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  await userEvent.click(screen.getByRole('link', { name: 'Review inbox' }))
  expect(await screen.findByRole('heading', { name: 'Review inbox' })).toBeInTheDocument()
  await userEvent.click(await screen.findByRole('link', { name: 'project · Unstaged' }))
  expect(await screen.findByText('Posible cambio de contrato')).toBeInTheDocument()
  expect(window.location.pathname).toBe(`/reviews/${reviewFixture.review_id}`)
  await userEvent.click(screen.getByText('Original recorded diff'))
  expect(screen.getByLabelText('Original recorded diff')).toHaveValue(reviewFixture.diff)
  expect(screen.getByLabelText('Original recorded diff')).toHaveAttribute('readonly')
  expect(screen.getByText('Structurally valid references')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /a.txt · old:1–1/ })).toHaveAttribute('href', '#hunk_test-line-5')
  expect(screen.queryByRole('button', { name: 'Review with Muse Spark' })).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(true)
})

it('loads a review directly from its URL and displays provider errors with the saved diff', async () => {
  window.history.replaceState(null, '', `/reviews/${reviewFixture.review_id}`)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ ...reviewFixture,
    status: 'error', analysis: null,
    error: { code: 'model_timeout', message: 'Meta agotó el tiempo; el diff se conserva.', recoverable: true },
  })))
  render(<App />)
  expect(await screen.findByRole('alert')).toHaveTextContent('model_timeout')
  expect(screen.getByRole('table')).toBeInTheDocument()
  expect(screen.getByText('Analysis error')).toBeInTheDocument()
  expect(screen.queryByText('Completed')).not.toBeInTheDocument()
})

it('distinguishes a completed review with no findings from a provider error', async () => {
  window.history.replaceState(null, '', `/reviews/${reviewFixture.review_id}`)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ ...reviewFixture,
    analysis: { ...reviewFixture.analysis, findings: [] },
  })))
  render(<App />)
  expect(await screen.findByText(/No risks were proposed/)).toBeInTheDocument()
  expect(screen.getByText('Completed')).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

it('allows explicit analysis of a pending snapshot without changing its diff', async () => {
  window.history.replaceState(null, '', `/reviews/${reviewFixture.review_id}`)
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(json({ ...reviewFixture, status: 'pending', analysis: null, finished_at: null }))
    .mockResolvedValueOnce(json(reviewFixture))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  await userEvent.click(await screen.findByRole('button', { name: 'Analyze pending snapshot' }))
  expect(await screen.findByText('Completed')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenLastCalledWith(`/api/reviews/${reviewFixture.review_id}/analyze`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Inspector-Request': '1' }, body: '{}',
  })
  expect(screen.queryByRole('button', { name: 'Analyze pending snapshot' })).not.toBeInTheDocument()
})

it('shows empty inbox and offers an explicit refresh', async () => {
  window.history.replaceState(null, '', '/reviews')
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(json({ items: [], total: 0 })))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  expect(await screen.findByText(/No reviews yet/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Refresh inbox' }))
  expect(await screen.findByText(/No reviews yet/)).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it('shows recoverable inbox connection errors', async () => {
  window.history.replaceState(null, '', '/reviews')
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
  render(<App />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Check that the backend is running')
})

it('rejects invalid routes and displays missing review errors without leaking local files', async () => {
  window.history.replaceState(null, '', '/reviews/not-an-id')
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  const { unmount } = render(<App />)
  expect(screen.getByRole('alert')).toHaveTextContent('Invalid review route')
  expect(fetchMock).not.toHaveBeenCalled()
  unmount()
  window.history.replaceState(null, '', `/reviews/${reviewFixture.review_id}`)
  fetchMock.mockResolvedValue(json({ error: { code: 'review_not_found', message: 'The review was not found.' } }, 404))
  render(<App />)
  expect(await screen.findByRole('alert')).toHaveTextContent('The review was not found')
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
