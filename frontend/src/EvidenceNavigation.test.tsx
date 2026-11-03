import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { EvidenceNavigation } from './components/EvidenceNavigation'
import { DiffExplorer } from './components/DiffExplorer'
import { FindingsPanel } from './components/FindingsPanel'
import { ReviewSnapshot } from './components/ReviewSnapshot'
import App from './App'
import { reviewFixture } from './test/reviewFixture'
import { analysisFixture } from './test/analysisFixture'
import { parsedFixture } from './test/fixture'
import type { AnalysisResponse, Reference } from './types/analysis'

const base = parsedFixture.files[0]
const hunk = base.hunks[0]
const lines = [
  { ...hunk.lines[0], diff_line: 5, old_line: 1, new_line: 1, kind: 'context' as const },
  { ...hunk.lines[0], diff_line: 6, old_line: 2 },
  { ...hunk.lines[1], diff_line: 7, new_line: 2 },
  { ...hunk.lines[0], diff_line: 8, old_line: 3 },
  { ...hunk.lines[1], diff_line: 9, new_line: 3 },
]
const parsed = { ...parsedFixture, files: [
  { ...base, hunks: [{ ...hunk, lines }, { ...hunk, hunk_id: 'other-hunk', lines: lines.map(l => ({ ...l, diff_line: l.diff_line + 10 })) }] },
  { ...base, file_id: 'other-file', hunks: [{ ...hunk, hunk_id: 'other-file-hunk', lines: lines.map(l => ({ ...l, diff_line: l.diff_line + 20 })) }] },
] }
function analysis(side: 'old' | 'new' = 'old'): AnalysisResponse {
  const reference: Reference = { ...analysisFixture.findings[0].reference_checks[0].reference, side, line_start: 1, line_end: 3 }
  return { ...analysisFixture, parsed_diff: parsed, findings: [{ ...analysisFixture.findings[0], reference_checks: [
    { reference, status: 'valid', reason: 'matched', diff_line: 5 },
    { reference: { ...reference, path: 'invalid.txt' }, status: 'invalid', reason: 'path_mismatch', diff_line: null },
  ] }] }
}
function Harness({ data = analysis() }: { data?: AnalysisResponse | null }) {
  return <EvidenceNavigation analysis={data} parsed={data ? parsed : null}>
    <DiffExplorer result={data ? parsed : null} />
    <FindingsPanel analysis={data} loading={false} error="" canReview={false} onReview={() => {}} readOnly />
  </EvidenceNavigation>
}
const scroll = vi.fn()
beforeEach(() => { Element.prototype.scrollIntoView = scroll; scroll.mockClear() })
afterEach(() => vi.unstubAllGlobals())

it.each(['old', 'new'] as const)('selects only %s coordinates across interleaved rows, scoped to file and hunk', async side => {
  render(<Harness data={analysis(side)} />)
  await userEvent.click(screen.getByRole('link', { name: new RegExp(`a.txt · ${side}:1–3`) }))
  const ids = [...document.querySelectorAll('.evidence-selected')].map(row => row.id)
  expect(ids).toEqual((side === 'old' ? [5, 6, 8] : [5, 7, 9]).map(n => `hunk_test-line-${n}`))
  expect(document.getElementById(`hunk_test-line-${side === 'old' ? 6 : 7}`)).toHaveClass(side === 'old' ? 'bg-danger-soft' : 'bg-success-soft')
  expect(screen.getByRole('region', { name: 'Selected evidence' })).toHaveTextContent(`· ${side}:1–3`)
  expect(screen.getByText(/invalid.txt/).closest('a')).toBeNull()
})

it('repeats navigation, returns to the exact origin with focus and preserves drafts', async () => {
  window.history.replaceState(null, '', `/reviews/${reviewFixture.review_id}`)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...reviewFixture, parsed_diff: parsed, analysis: analysis() }))))
  render(<App />)
  const link = await screen.findByRole('link', { name: /a.txt · old:1–3/ })
  const comment = screen.getByRole('textbox', { name: /comment/i })
  await userEvent.type(comment, 'Unsaved human draft')
  for (let i = 0; i < 2; i++) {
    await userEvent.click(link)
    expect(document.activeElement?.id).toBe('hunk_test-line-5')
    expect(window.location.hash).toBe('#hunk_test-line-5')
    await userEvent.click(screen.getByRole('button', { name: 'Back to finding' }))
    await waitFor(() => expect(link).toHaveFocus())
    expect(comment).toHaveValue('Unsaved human draft')
  }
  expect(scroll.mock.calls.filter(([options]) => options.behavior === 'instant').length).toBeGreaterThanOrEqual(4)
})

it('resolves a direct fragment after asynchronous data and reopens a closed origin on return', async () => {
  window.history.replaceState(null, '', '/diff#hunk_test-line-5')
  const view = render(<Harness data={null} />)
  view.rerender(<Harness />)
  await waitFor(() => expect(document.getElementById('hunk_test-line-5')).toHaveFocus())
  await userEvent.click(screen.getByRole('button', { name: 'Explanation, evidence & suggested tests' }))
  await userEvent.click(screen.getByRole('button', { name: 'Back to finding' }))
  await waitFor(() => expect(screen.getByRole('link', { name: /a.txt · old:1–3/ })).toHaveFocus())
  expect(screen.getByRole('button', { name: 'Explanation, evidence & suggested tests' })).toHaveAttribute('aria-expanded', 'true')
})

it('keeps parent and child selection and return targets independent, including hash changes', async () => {
  const review = { ...reviewFixture, parsed_diff: parsed, analysis: analysis() }
  render(<><ReviewSnapshot review={review} side="parent" /><ReviewSnapshot review={{ ...review, analysis: analysis('new') }} side="child" /></>)
  const parent = within(screen.getByRole('region', { name: 'Parent snapshot' }))
  const child = within(screen.getByRole('region', { name: 'Child snapshot' }))
  await userEvent.click(parent.getByRole('link', { name: /a.txt · old/ }))
  await userEvent.click(child.getByRole('link', { name: /a.txt · new/ }))
  expect(document.querySelectorAll('.evidence-selected')).toHaveLength(6)
  expect(parent.getByRole('region', { name: 'Selected evidence' })).toHaveTextContent('Parent snapshot')
  expect(child.getByRole('region', { name: 'Selected evidence' })).toHaveTextContent('Child snapshot')
  await userEvent.click(parent.getByRole('button', { name: 'Back to finding' }))
  await waitFor(() => expect(parent.getByRole('link', { name: /a.txt · old/ })).toHaveFocus())
  act(() => { window.history.replaceState(null, '', '#compare-child-hunk_test-line-5'); fireEvent(window, new HashChangeEvent('hashchange')) })
  expect(document.activeElement?.id).toBe('compare-child-hunk_test-line-5')
  expect(parent.getByRole('region', { name: 'Selected evidence' })).toBeInTheDocument()
})
