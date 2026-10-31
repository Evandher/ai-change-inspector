import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import App from './App'
import { reviewFixture } from './test/reviewFixture'
import { LANGUAGE_KEY, translator } from './lib/i18n'
import type { ReviewDetail, ReviewTimeline } from './types/review'

afterEach(() => vi.unstubAllGlobals())
const parent: ReviewDetail = { ...reviewFixture, feedback: [{finding_index:0,decision:'request_changes',comment:'<script>human comment</script>',updated_at:'2026-10-29T12:00:00Z'}] }
const child: ReviewDetail = { ...reviewFixture,review_id:'22222222-2222-4222-8222-222222222222',parent_review_id:parent.review_id,diff:'Stored child diff\r\n',feedback:[{finding_index:0,decision:'accept_risk',comment:'Independent child comment',updated_at:'2026-10-29T13:00:00Z'}] }
const family: ReviewTimeline = {review_id:child.review_id,repository:'project',repository_root:'D:/demo',items:[parent,child],missing_review_ids:[],incomplete:false,truncated:false}
const comparison = {parent:{...parent,child_review_ids:[child.review_id]},child}
const json = (data: unknown,status=200) => new Response(JSON.stringify(data),{status})
const route = `/reviews/${parent.review_id}/compare/${child.review_id}`

it('does not infer a root comparison when the selected parent relationship is missing', async () => {
  window.history.replaceState(null, '', `/reviews/${child.review_id}/evolution`)
  const fetchMock = vi.fn().mockResolvedValue(json({ ...family, items: [child], incomplete: true, missing_review_ids: [parent.review_id] }))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  expect(await screen.findByText(/relationships are incomplete/)).toBeInTheDocument()
  expect(screen.queryByRole('region', { name: 'Parent snapshot' })).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('previews the stored parent-child comparison below the timeline with only read-only API requests', async () => {
  window.history.replaceState(null, '', `/reviews/${child.review_id}/evolution`)
  const fetchMock = vi.fn().mockImplementation((url: string) => Promise.resolve(json(url.endsWith('/timeline') ? family : comparison)))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  const pane = within(await screen.findByRole('region', { name: 'Parent snapshot' }))
  expect(pane.getByText(parent.feedback[0].comment)).toBeInTheDocument()
  expect(pane.getAllByRole('button').every((button) => button.hasAttribute('aria-controls') && button.hasAttribute('aria-expanded'))).toBe(true)
  expect(pane.getByLabelText(`Parent snapshot · Original recorded diff`)).toHaveValue(parent.diff)
  expect(fetchMock).toHaveBeenCalledTimes(2)
  expect(fetchMock.mock.calls.every(([, options]) => !options.method)).toBe(true)
})

it('navigates from a detail to timeline, comparison and a stored child detail using GET only',async()=>{
  window.history.replaceState(null,'',`/reviews/${child.review_id}`)
  const fetchMock=vi.fn().mockImplementation((url: string) => Promise.resolve(json(url.endsWith('/timeline') ? family : url.includes('/compare/') ? comparison : child)))
  vi.stubGlobal('fetch',fetchMock)
  render(<App />)
  await userEvent.click(await screen.findByRole('link',{name:'View evolution'}))
  expect(await screen.findByRole('heading',{name:'Review evolution'})).toBeInTheDocument()
  expect(screen.getByRole('link',{name:child.review_id})).toHaveAttribute('aria-current','page')
  await userEvent.click(screen.getByRole('link',{name:'Compare with parent'}))
  expect(await screen.findByRole('heading',{name:'Compare stored reviews'})).toBeInTheDocument()
  expect(await screen.findByRole('region',{name:'Parent snapshot'})).toBeInTheDocument()
  expect(window.location.pathname).toBe(route)
  await userEvent.click(screen.getByRole('link',{name:'Follow-up review'}))
  expect(await screen.findByRole('heading',{name:'Review detail'})).toBeInTheDocument()
  expect(fetchMock).toHaveBeenNthCalledWith(2,`/api/reviews/${child.review_id}/timeline`,{cache:'no-store'})
  expect(fetchMock).toHaveBeenNthCalledWith(3,`/api/reviews/${parent.review_id}/compare/${child.review_id}`,{cache:'no-store'})
  expect(fetchMock.mock.calls.every(([,options])=>!options?.method || options.method==='GET')).toBe(true)
})

it.each(['en','es'] as const)('shows exact stored snapshots, original findings and separate human feedback in %s',async(language)=>{
  localStorage.setItem(LANGUAGE_KEY,language)
  const t=translator(language)
  window.history.replaceState(null,'',route)
  const fetchMock=vi.fn().mockResolvedValue(json(comparison))
  vi.stubGlobal('fetch',fetchMock)
  render(<App />)
  const left=within(await screen.findByRole('region',{name:t('parentSnapshot')}))
  const right=within(screen.getByRole('region',{name:t('childSnapshot')}))
  expect(left.getByLabelText(`${t('parentSnapshot')} · ${t('originalDiff')}`)).toHaveValue(parent.diff)
  // Textarea presentation normalizes CRLF, while the API data stays untouched.
  expect(right.getByLabelText(`${t('childSnapshot')} · ${t('originalDiff')}`)).toHaveValue(child.diff.replace(/\r\n/g,'\n'))
  expect(left.getByText(t('request_changes'))).toBeInTheDocument()
  expect(right.getByText(t('accept_risk'))).toBeInTheDocument()
  expect(left.getByText(parent.feedback[0].comment)).toBeInTheDocument()
  expect(right.getByText(child.feedback[0].comment)).toBeInTheDocument()
  expect(left.getByText(parent.analysis!.findings[0].hypothesis.title)).toBeInTheDocument()
  expect(left.getByText(t('validReferences'))).toBeInTheDocument()
  expect(left.getByText(t('tests'))).toBeInTheDocument()
  expect(screen.getByText(t('comparisonWarning'))).toBeInTheDocument()
  expect(within(screen.getByRole('main')).getAllByRole('button').every((button) => button.hasAttribute('aria-controls') && button.hasAttribute('aria-expanded'))).toBe(true)
  expect(screen.getAllByRole('textbox')).toHaveLength(2)
  expect(screen.getAllByRole('textbox').every((element)=>element.hasAttribute('readonly'))).toBe(true)
  expect(document.querySelector('script')).toBeNull()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('scopes identical parser IDs and evidence links to their comparison pane',async()=>{
  window.history.replaceState(null,'',route)
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(json(comparison)))
  render(<App />)
  await screen.findByRole('region',{name:'Parent snapshot'})
  for(const side of ['parent','child']){
    const target=`compare-${side}-hunk_test-line-5`
    expect(document.getElementById(target)).toHaveAttribute('data-hunk-id','hunk_test')
    const pane=within(screen.getByRole('region',{name:side==='parent'?'Parent snapshot':'Child snapshot'}))
    expect(pane.getByRole('link',{name:/a.txt · old:1–1/})).toHaveAttribute('href',`#${target}`)
  }
  const ids=Array.from(document.querySelectorAll('[id]'),(element)=>element.id)
  expect(new Set(ids).size).toBe(ids.length)
})

it.each(['pending','analyzing','error'] as const)('preserves the %s state beside a completed review with no findings',async(status)=>{
  window.history.replaceState(null,'',route)
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(json({parent:{...parent,analysis:{...parent.analysis,findings:[]}},child:{...child,status,analysis:null,error:status==='error'?{code:'model_timeout',message:'Original error',recoverable:true}:null}})))
  render(<App />)
  expect(await screen.findByText(/No risks were proposed/)).toBeInTheDocument()
  const pane=within(screen.getByRole('region',{name:'Child snapshot'}))
  expect(pane.getByText(new RegExp(translator('en')(status)))).toBeInTheDocument()
  if(status==='error')expect(pane.getByRole('alert')).toHaveTextContent('model_timeout')
  expect(within(screen.getByRole('main')).queryByRole('button')).not.toBeInTheDocument()
})

it('reports incomplete and truncated timelines and preserves missing references',async()=>{
  window.history.replaceState(null,'',`/reviews/${child.review_id}/evolution`)
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(json({...family,incomplete:true,truncated:true,missing_review_ids:['33333333-3333-4333-8333-333333333333']})))
  render(<App />)
  expect(await screen.findByText(/relationships are incomplete/)).toBeInTheDocument()
  expect(screen.getByText(/limited to 200/)).toBeInTheDocument()
  expect(screen.getByText(/Missing snapshot: 33333333/)).toBeInTheDocument()
})

it.each(['review_not_found','comparison_not_related'] as const)('shows recoverable %s errors without starting an analysis',async(code)=>{
  window.history.replaceState(null,'',route)
  const fetchMock=vi.fn().mockResolvedValue(json({error:{code}},code==='review_not_found'?404:409))
  vi.stubGlobal('fetch',fetchMock)
  render(<App />)
  expect(await screen.findByRole('alert')).toHaveTextContent(translator('en')(code))
  expect(screen.queryByRole('region',{name:'Parent snapshot'})).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('shows loading and changes language without refetching or mutating snapshots',async()=>{
  window.history.replaceState(null,'',route)
  let finish!:(response:Response)=>void
  const fetchMock=vi.fn(()=>new Promise<Response>((resolve)=>{finish=resolve}))
  vi.stubGlobal('fetch',fetchMock)
  render(<App />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading comparison')
  await act(async()=>finish(json(comparison)))
  await userEvent.selectOptions(screen.getByRole('combobox',{name:'Interface language'}),'es')
  expect(screen.getByRole('heading',{name:'Comparar revisiones guardadas'})).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})
