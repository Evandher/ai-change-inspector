import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import App from './App'
import { analysisFixture } from './test/analysisFixture'
import { parsedFixture } from './test/fixture'
import { examples } from './lib/examples'

afterEach(() => vi.unstubAllGlobals())

async function parseExample() {
  await userEvent.click(screen.getByRole('button', { name: 'Simple change' }))
  await userEvent.click(screen.getByRole('button', { name: 'Parse diff' }))
  await screen.findByRole('heading', { name: 'a.txt' })
}

it('requires parsing first and makes no automatic model request', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(parsedFixture)))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  expect(screen.getByRole('button', { name: 'Review with Muse Spark' })).toBeDisabled()
  await parseExample()
  expect(screen.getByRole('button', { name: 'Review with Muse Spark' })).toBeEnabled()
  expect(fetchMock).toHaveBeenCalledTimes(1)
  expect(screen.getByText(/sends it to Meta and consumes credits/)).toBeInTheDocument()
})

it('reviews the current diff and distinguishes hypotheses from matched evidence', async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify(parsedFixture)))
    .mockResolvedValueOnce(new Response(JSON.stringify(analysisFixture)))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  await parseExample()
  await userEvent.click(screen.getByRole('button', { name: 'Review with Muse Spark' }))
  expect(await screen.findByText('Posible cambio de contrato')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenLastCalledWith('/api/diff/analyze', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ diff: examples[0].diff }),
  })
  expect(screen.getByText(/Model hypothesis · Estimated severity: Medium/)).toBeInTheDocument()
  expect(screen.getByText('Structurally valid references')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /a.txt · old:1–1/ })).toHaveAttribute('href', '#hunk_test-line-5')
  expect(document.getElementById('hunk_test-line-5')).toBeInTheDocument()
  expect(screen.getByText('<script>untrusted()</script>')).toBeInTheDocument()
  expect(document.querySelector('script')).toBeNull()
  expect(screen.getByText('Suggested tests · not executed')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Git diff'), { target: { value: 'edited' } })
  expect(screen.queryByText('Posible cambio de contrato')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Review with Muse Spark' })).toBeDisabled()
})

it('shows invalid references without creating links or claiming the issue was verified', async () => {
  const response = structuredClone(analysisFixture)
  const finding = response.findings[0]
  finding.all_references_valid = false
  finding.reference_checks[0] = {
    reference: { ...finding.reference_checks[0].reference, path: 'invented.py' },
    status: 'invalid', reason: 'path_mismatch', diff_line: null,
  }
  vi.stubGlobal('fetch', vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify(parsedFixture)))
    .mockResolvedValueOnce(new Response(JSON.stringify(response))))
  render(<App />)
  await parseExample()
  await userEvent.click(screen.getByRole('button', { name: 'Review with Muse Spark' }))
  expect(await screen.findByText('Some references are invalid')).toBeInTheDocument()
  expect(screen.getByText('The path does not match the cited side.')).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /invented.py/ })).not.toBeInTheDocument()
})

it('keeps the parsed diff on configuration errors and lets the user retry', async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify(parsedFixture)))
    .mockResolvedValueOnce(new Response(JSON.stringify({ error: {
      code: 'model_not_configured', message: 'Configure MODEL_API_KEY in the backend environment.', line: null,
    } }), { status: 503 }))
    .mockResolvedValueOnce(new Response(JSON.stringify(analysisFixture)))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  await parseExample()
  await userEvent.click(screen.getByRole('button', { name: 'Review with Muse Spark' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('MODEL_API_KEY')
  expect(screen.getByRole('table')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Review with Muse Spark' }))
  expect(await screen.findByText('Posible cambio de contrato')).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

it('blocks edits and duplicate requests while waiting for the model', async () => {
  let finish!: (response: Response) => void
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify(parsedFixture)))
    .mockImplementationOnce(() => new Promise<Response>((resolve) => { finish = resolve }))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  await parseExample()
  await userEvent.click(screen.getByRole('button', { name: 'Review with Muse Spark' }))
  expect(screen.getByText('Waiting for the model review…')).toBeInTheDocument()
  expect(screen.getByLabelText('Git diff')).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Parse diff' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Reviewing with Muse Spark…' })).toBeDisabled()
  await act(async () => finish(new Response(JSON.stringify({ ...analysisFixture, findings: [] }))))
  expect(screen.getByText(/No risks were proposed/)).toBeInTheDocument()
  expect(screen.getByLabelText('Git diff')).toBeEnabled()
  expect(fetchMock).toHaveBeenCalledTimes(2)
})
