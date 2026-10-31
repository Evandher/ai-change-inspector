import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import App from './App'
import { reviewFixture } from './test/reviewFixture'
import { translator } from './lib/i18n'

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })
const json = (data: unknown) => new Response(JSON.stringify(data))

it('preserves collapsed navigation and accessible names through navigation and reload', async () => {
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(json({ items: [], total: 0 })))
  vi.stubGlobal('fetch', fetchMock)
  const first = render(<App />)
  await userEvent.click(screen.getByRole('button', { name: 'Collapse sidebar' }))
  expect(screen.getByRole('button', { name: 'Expand sidebar' })).toHaveAttribute('aria-expanded', 'false')
  expect(localStorage.getItem('ai-change-inspector.sidebar-collapsed')).toBe('true')
  await userEvent.click(screen.getByRole('link', { name: 'Review inbox' }))
  expect(await screen.findByText(/No reviews yet/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Review inbox' })).toHaveAttribute('aria-current', 'page')
  first.unmount()
  render(<App />)
  expect(screen.getByRole('button', { name: 'Expand sidebar' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Expand sidebar' }))
  expect(localStorage.getItem('ai-change-inspector.sidebar-collapsed')).toBe('false')
  expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#workspace')
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it('supports keyboard toggling and session use with blocked storage', async () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
  render(<App />)
  const toggle = screen.getByRole('button', { name: 'Collapse sidebar' })
  toggle.focus()
  await userEvent.keyboard('{Enter}')
  expect(screen.getByRole('button', { name: 'Expand sidebar' })).toHaveFocus()
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Interface language' }), 'es')
  expect(screen.getByRole('button', { name: 'Expandir barra lateral' })).toHaveAttribute('aria-expanded', 'false')
})

it('connects icon links to named tooltips and allows keyboard dismissal without navigation', async () => {
  render(<App />)
  await userEvent.click(screen.getByRole('button', { name: 'Collapse sidebar' }))
  await userEvent.tab() // Overview
  await userEvent.tab() // Inbox
  const link = screen.getByRole('link', { name: 'Review inbox' })
  expect(link).toHaveFocus()
  expect(link).toHaveAttribute('aria-describedby', 'nav-tip-inbox')
  expect(document.getElementById('nav-tip-inbox')).toHaveTextContent('Review inbox')
  await userEvent.keyboard('{Escape}')
  expect(link).toHaveAttribute('data-tooltip-hidden', 'true')
  expect(window.location.pathname).toBe('/diff')
})

it('renders real review metadata in a navigable table without invented metrics or analysis requests', async () => {
  window.history.replaceState(null, '', '/reviews')
  const fetchMock = vi.fn().mockResolvedValue(json({ items: [reviewFixture], total: 1 }))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  const table = within(await screen.findByRole('table', { name: 'Review inbox' }))
  expect(table.getByRole('columnheader', { name: 'Analysis status' })).toBeInTheDocument()
  expect(table.getByText('Completed')).toBeInTheDocument()
  expect(table.getByText(reviewFixture.review_id)).toBeInTheDocument()
  expect(table.getByRole('link', { name: 'View evolution' })).toHaveAttribute('href', `/reviews/${reviewFixture.review_id}/evolution`)
  expect(fetchMock).toHaveBeenCalledExactlyOnceWith('/api/reviews?limit=20&offset=0', { cache: 'no-store' })
})

it.each(['en', 'es'] as const)('presents a small inbox with real counts, revision identities and action links in %s', async (language) => {
  localStorage.setItem('ai-change-inspector.language', language)
  window.history.replaceState(null, '', '/reviews')
  const t = translator(language)
  const second = { ...reviewFixture, review_id: '22222222-2222-4222-8222-222222222222' }
  const fetchMock = vi.fn().mockResolvedValue(json({ items: [reviewFixture, second], total: 2 }))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  const table = within(await screen.findByRole('table', { name: t('inbox') }))
  expect(table.getAllByRole('row')).toHaveLength(3) // Header and exactly two saved records, no filler rows.
  expect(screen.getByText(t('reviewCount', { count: 2 }))).toBeInTheDocument()
  expect(screen.getByText(t('pagination', { start: 1, end: 2, total: 2 }))).toBeInTheDocument()
  for (const review of [reviewFixture, second]) {
    const identity = table.getByText(review.review_id)
    const row = within(identity.closest('tr')!)
    const link = row.getByRole('link', { name: `${review.repository} · ${t(review.scope)}` })
    expect(link).toHaveTextContent(`${t('reviewLabel')} ${review.review_id.slice(0, 8)}`)
    expect(link).toHaveAccessibleDescription(review.review_id)
    expect(row.getByRole('link', { name: t('viewReview') })).toHaveAttribute('href', `/reviews/${review.review_id}`)
    expect(row.getByRole('link', { name: t('viewEvolution') })).toHaveAttribute('href', `/reviews/${review.review_id}/evolution`)
  }
  expect(fetchMock).toHaveBeenCalledTimes(1)
})
