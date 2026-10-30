import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import App from './App'
import { reviewFixture } from './test/reviewFixture'
import { LANGUAGE_KEY, translator } from './lib/i18n'

afterEach(() => vi.unstubAllGlobals())
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status })
const url = `/api/reviews/${reviewFixture.review_id}/feedback/0`
const saved = { finding_index: 0, decision: 'request_changes', comment: '<script>check()</script>', updated_at: '2026-10-29T12:00:00+00:00' }

it.each(['en','es'] as const)('saves human feedback in %s without another model request', async (language) => {
  localStorage.setItem(LANGUAGE_KEY, language)
  const t = translator(language)
  window.history.replaceState(null, '', `/reviews/${reviewFixture.review_id}`)
  const fetchMock = vi.fn().mockResolvedValueOnce(json(reviewFixture)).mockResolvedValueOnce(json(saved))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  await screen.findByRole('combobox', { name: t('humanDecision') })
  expect(screen.getByRole('button', { name: t('saveFeedback') })).toBeDisabled()
  expect(screen.getByText(t('decisionPending'), { selector: 'p' })).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByRole('combobox', { name: t('humanDecision') }), 'request_changes')
  await userEvent.type(screen.getByRole('textbox', { name: t('humanComment') }), saved.comment)
  await userEvent.click(screen.getByRole('button', { name: t('saveFeedback') }))
  expect(await screen.findByText(new RegExp(t('modifiedAt')))).toBeInTheDocument()
  expect(fetchMock).toHaveBeenLastCalledWith(url, {
    method:'PUT', headers:{'Content-Type':'application/json','X-Inspector-Request':'1'},
    body: JSON.stringify({decision:'request_changes',comment:saved.comment}),
  })
  expect(screen.getByRole('textbox', { name:t('humanComment') })).toHaveAttribute('maxlength','4000')
  expect(screen.getByRole('button', {name:t('saveFeedback')})).toBeDisabled()
  expect(document.querySelector('script')).toBeNull()
  expect(screen.getByLabelText(t('originalDiff'))).toHaveValue(reviewFixture.diff)
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it('restores saved decisions/comments and displays parent and child links', async () => {
  window.history.replaceState(null, '', `/reviews/${reviewFixture.review_id}`)
  const parent = '22222222-2222-4222-8222-222222222222'
  const child = '33333333-3333-4333-8333-333333333333'
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(json({...reviewFixture,feedback:[saved],parent_review_id:parent,child_review_ids:[child]})))
  render(<App />)
  expect(await screen.findByRole('combobox',{name:'Human decision'})).toHaveValue('request_changes')
  expect(screen.getByRole('textbox',{name:/Optional comment/})).toHaveValue(saved.comment)
  expect(screen.getByRole('link',{name:'Previous review'})).toHaveAttribute('href',`/reviews/${parent}`)
  expect(screen.getByRole('link',{name:`Follow-up review · ${child}`})).toHaveAttribute('href',`/reviews/${child}`)
})

it('keeps the draft on recoverable save errors and never marks it as saved', async () => {
  window.history.replaceState(null, '', `/reviews/${reviewFixture.review_id}`)
  const fetchMock=vi.fn().mockResolvedValueOnce(json(reviewFixture)).mockResolvedValueOnce(json({error:{code:'human_feedback_origin_required'}},403))
  vi.stubGlobal('fetch',fetchMock)
  render(<App />)
  await userEvent.selectOptions(await screen.findByRole('combobox',{name:'Human decision'}),'dismiss')
  await userEvent.click(screen.getByRole('button',{name:'Save decision'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('Use the local web interface')
  expect(screen.getByRole('combobox',{name:'Human decision'})).toHaveValue('dismiss')
  expect(screen.queryByText(/Last modified/)).not.toBeInTheDocument()
  expect(screen.getByRole('button',{name:'Save decision'})).toBeEnabled()
})

it('disables duplicate writes while a decision is being saved',async()=>{
  window.history.replaceState(null, '', `/reviews/${reviewFixture.review_id}`)
  let finish!: (response:Response)=>void
  const fetchMock=vi.fn().mockResolvedValueOnce(json(reviewFixture)).mockImplementationOnce(()=>new Promise<Response>((resolve)=>{finish=resolve}))
  vi.stubGlobal('fetch',fetchMock)
  render(<App />)
  await userEvent.selectOptions(await screen.findByRole('combobox',{name:'Human decision'}),'accept_risk')
  await userEvent.click(screen.getByRole('button',{name:'Save decision'}))
  expect(screen.getByRole('combobox',{name:'Human decision'})).toBeDisabled()
  expect(screen.getByRole('button',{name:'Saving…'})).toBeDisabled()
  await act(async()=>finish(json({...saved,decision:'accept_risk',comment:''})))
  expect(fetchMock).toHaveBeenCalledTimes(2)
})
