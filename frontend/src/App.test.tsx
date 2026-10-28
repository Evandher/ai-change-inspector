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
    expect(screen.getByRole('heading', { name: 'Explorador de cambios' })).toBeInTheDocument()
    expect(screen.getByRole('complementary')).toHaveTextContent('Hallazgos de IA')
    expect(screen.queryByRole('button', { name: /analizar.*ia/i })).not.toBeInTheDocument()
  })

  it('rejects empty and oversized UTF-8 input without making a request', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'Analizar diff' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Pega un diff')
    fireEvent.change(screen.getByLabelText('Diff de Git'), { target: { value: 'é'.repeat(MAX_DIFF_BYTES / 2 + 1) } })
    await userEvent.click(screen.getByRole('button', { name: 'Analizar diff' }))
    expect(screen.getByRole('alert')).toHaveTextContent('1 MiB')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('loads an example, submits it, renders safe text and clears stale results', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(parsedFixture)))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'Cambio simple' }))
    expect(screen.getByLabelText('Diff de Git')).toHaveValue(examples[0].diff)
    await userEvent.click(screen.getByRole('button', { name: 'Analizar diff' }))
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
    fireEvent.change(screen.getByLabelText('Diff de Git'), { target: { value: 'changed' } })
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Limpiar' }))
    expect(screen.getByLabelText('Diff de Git')).toHaveValue('')
  })

  it('disables editing while parsing and shows a loading state', async () => {
    let finish!: (response: Response) => void
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((resolve) => { finish = resolve })))
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'Cambio simple' }))
    await userEvent.click(screen.getByRole('button', { name: 'Analizar diff' }))
    expect(screen.getByRole('status')).toHaveTextContent('Procesando')
    expect(screen.getByLabelText('Diff de Git')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Varios archivos' })).toBeDisabled()
    await act(async () => finish(new Response(JSON.stringify(parsedFixture))))
    expect(screen.getByLabelText('Diff de Git')).toBeEnabled()
  })

  it('displays parser errors with their source line', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: 'invalid_hunk', message: 'Malformed unified hunk header.', line: 4 },
    }), { status: 422 })))
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'Cambio simple' }))
    await userEvent.click(screen.getByRole('button', { name: 'Analizar diff' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Malformed unified hunk header. Línea 4.')
  })

  it('explains connection failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Network error')))
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'Cambio simple' }))
    await userEvent.click(screen.getByRole('button', { name: 'Analizar diff' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo conectar con el backend')
  })
})
