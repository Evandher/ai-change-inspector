import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { MAX_DIFF_BYTES } from './lib/api'
import { examples } from './lib/examples'
import { parsedFixture } from './test/fixture'

afterEach(() => vi.unstubAllGlobals())

describe('diff workflow', () => {
  it('shows the explorer and separate future findings panel', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Diff explorer' })).toBeInTheDocument()
    expect(screen.getByRole('complementary')).toHaveTextContent('AI findings')
    expect(screen.queryByRole('button', { name: /analizar.*ia/i })).not.toBeInTheDocument()
  })

  it('rejects empty and oversized UTF-8 input without making a request', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'Parse diff' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Paste a Git diff')
    fireEvent.change(screen.getByLabelText('Git diff'), { target: { value: 'é'.repeat(MAX_DIFF_BYTES / 2 + 1) } })
    await userEvent.click(screen.getByRole('button', { name: 'Parse diff' }))
    expect(screen.getByRole('alert')).toHaveTextContent('1 MiB')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('loads an example, submits it, renders safe text and clears stale results', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(parsedFixture)))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'Simple change' }))
    expect(screen.getByLabelText('Git diff')).toHaveValue(examples[0].diff)
    await userEvent.click(screen.getByRole('button', { name: 'Parse diff' }))
    expect(await screen.findByRole('heading', { name: 'a.txt' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/diff/parse', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ diff: examples[0].diff }),
    })
    expect(screen.getByText('<script>alert(1)</script>')).toBeInTheDocument()
    expect(document.querySelector('script')).toBeNull()
    const table = screen.getByRole('table')
    expect(within(table).getAllByText('1')).toHaveLength(2)
    expect(screen.getByText(/No newline at end of file/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'a.txt' })).toHaveAttribute('href', '#file_test')
    expect(document.getElementById('hunk_test-line-6')).toHaveAttribute('data-hunk-id', 'hunk_test')
    fireEvent.change(screen.getByLabelText('Git diff'), { target: { value: 'changed' } })
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Clear' }))
    expect(screen.getByLabelText('Git diff')).toHaveValue('')
  })

  it('disables editing while parsing and shows a loading state', async () => {
    let finish!: (response: Response) => void
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((resolve) => { finish = resolve })))
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'Simple change' }))
    await userEvent.click(screen.getByRole('button', { name: 'Parse diff' }))
    expect(screen.getByRole('status')).toHaveTextContent('Processing')
    expect(screen.getByLabelText('Git diff')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Multiple files' })).toBeDisabled()
    await act(async () => finish(new Response(JSON.stringify(parsedFixture))))
    expect(screen.getByLabelText('Git diff')).toBeEnabled()
  })

  it('displays parser errors with their source line', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: 'invalid_hunk', message: 'Malformed unified hunk header.', line: 4 },
    }), { status: 422 })))
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'Simple change' }))
    await userEvent.click(screen.getByRole('button', { name: 'Parse diff' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('The hunk header or content is invalid. Line 4.')
  })

  it('explains connection failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Network error')))
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'Simple change' }))
    await userEvent.click(screen.getByRole('button', { name: 'Parse diff' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not connect to the backend')
  })
})
