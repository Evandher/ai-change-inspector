import { LanguageProvider } from './components/LanguageProvider'
import { DisplayError, errorText } from './lib/errors'
import { useLanguage } from './lib/i18n'
import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { DiffExplorer } from './components/DiffExplorer'
import { FindingsPanel } from './components/FindingsPanel'
import { MAX_DIFF_BYTES, analyzeDiff, parseDiff } from './lib/api'
import { examples } from './lib/examples'
import type { ParsedDiff } from './types/diff'
import type { AnalysisResponse } from './types/analysis'
import { ReviewInbox } from './components/ReviewInbox'
import { ReviewDetail } from './components/ReviewDetail'

function ManualInspector() {
  const { t, language } = useLanguage()
  const [diff, setDiff] = useState('')
  const [result, setResult] = useState<ParsedDiff | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(false)
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewError, setReviewError] = useState<unknown>(null)
  const busy = loading || reviewLoading
  const bytes = new TextEncoder().encode(diff).length

  function updateDiff(value: string) {
    setDiff(value)
    setResult(null)
    setError(null)
    setAnalysis(null)
    setReviewError(null)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setResult(null)
    setAnalysis(null)
    setReviewError(null)
    if (!diff.trim()) {
      setError(new DisplayError('empty_diff'))
      return
    }
    if (bytes > MAX_DIFF_BYTES) {
      setError(new DisplayError('diff_too_large'))
      return
    }
    setLoading(true)
    try {
      setResult(await parseDiff(diff))
    } catch (cause) {
      setError(cause)
    } finally {
      setLoading(false)
    }
  }

  async function handleReview() {
    if (!result || busy) return
    setReviewLoading(true)
    setReviewError(null)
    setAnalysis(null)
    try {
      const review = await analyzeDiff(diff)
      setResult(review.parsed_diff)
      setAnalysis(review)
    } catch (cause) {
      setReviewError(cause)
    } finally {
      setReviewLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      <header className="border-b border-slate-800">
        <div className="mx-auto flex max-w-screen-2xl flex-wrap items-center justify-between gap-4 px-6 py-6">
          <div className="flex items-center gap-3">
            <span aria-hidden="true" className="rounded-xl bg-teal-300 p-3 font-mono font-bold text-slate-950">±</span>
            <div><h1 className="text-xl font-semibold tracking-tight text-white">AI Change Inspector</h1>
              <p className="mt-1 text-sm text-slate-400">{t('tagline')}</p></div>
          </div>
          <span className="rounded-full border border-teal-800 bg-teal-950 px-3 py-1 text-xs text-teal-200">{t('badge')}</span>
        </div>
      </header>
      <main className="mx-auto max-w-screen-2xl space-y-8 px-6 py-8">
        <section aria-labelledby="input-title" className="rounded-2xl border border-slate-800 bg-slate-900 p-5 sm:p-6">
          <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
            <div><h2 id="input-title" className="text-lg font-semibold text-white">{t('inspect')}</h2>
              <p className="mt-1 text-sm text-slate-400">{t('pasteOutput')} <code className="text-teal-200">git diff --no-ext-diff --no-color --src-prefix=a/ --dst-prefix=b/</code>.</p></div>
            <div className="flex flex-wrap gap-2" aria-label={t('examples')}>
              {examples.map((example) => <button key={example.label} type="button" className="secondary-button" disabled={busy} onClick={() => updateDiff(example.diff)}>{t(example.label)}</button>)}
            </div>
          </div>
          <form onSubmit={handleSubmit}>
            <label htmlFor="diff-input" className="mb-2 block text-sm font-medium">{t('gitDiff')}</label>
            <textarea id="diff-input" value={diff} onChange={(event) => updateDiff(event.target.value)} disabled={busy}
              spellCheck={false} placeholder={'diff --git a/example.py b/example.py\n--- a/example.py\n+++ b/example.py\n@@ -1 +1 @@\n-old\n+new'}
              aria-describedby="size-help" className="h-64 w-full resize-y rounded-xl border border-slate-700 bg-slate-950 p-4 font-mono text-sm leading-6 text-slate-200 placeholder:text-slate-600" />
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p id="size-help" className={`text-xs ${bytes > MAX_DIFF_BYTES ? 'text-rose-300' : 'text-slate-400'}`}>{bytes.toLocaleString(language)} / {MAX_DIFF_BYTES.toLocaleString(language)} bytes · UTF-8</p>
              <div className="flex gap-3">
                <button type="button" className="secondary-button" disabled={busy || !diff} onClick={() => updateDiff('')}>{t('clear')}</button>
                <button type="submit" disabled={busy} className="rounded-lg bg-teal-300 px-5 py-2 text-sm font-semibold text-slate-950 hover:bg-teal-200 disabled:opacity-50">{loading ? t('parsing') : t('parse')}</button>
              </div>
            </div>
          </form>
          {loading && <p role="status" className="mt-4 text-sm text-teal-200">{t('processing')}</p>}
          {error != null && <p role="alert" className="mt-4 rounded-lg border border-rose-900 bg-rose-950 p-3 text-sm text-rose-200">{errorText(error, t)}</p>}
        </section>
        <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_19rem]">
          <DiffExplorer result={result} />
          <FindingsPanel analysis={analysis} loading={reviewLoading} error={reviewError == null ? '' : errorText(reviewError, t)}
            canReview={!!result && !busy} onReview={handleReview} />
        </div>
      </main>
      <footer className="mx-auto max-w-screen-2xl px-6 pb-8 text-xs text-slate-500">{t('footer')}</footer>
    </div>
  )
}

function AppContent() {
  const { t, language, setLanguage } = useLanguage()
  const [path, setPath] = useState(window.location.pathname)
  useEffect(() => {
    const update = () => setPath(window.location.pathname)
    window.addEventListener('popstate', update)
    return () => window.removeEventListener('popstate', update)
  }, [])
  function navigate(target: string) {
    window.history.pushState(null, '', target)
    setPath(target)
  }
  const detail = /^\/reviews\/([0-9a-f-]{36})$/.exec(path)
  return <div className="min-h-screen bg-slate-950 text-slate-200">
    <nav aria-label={t('navigation')} className="mx-auto flex max-w-screen-2xl gap-5 border-b border-slate-800 px-6 py-4 text-sm">
      <a href="/" className="text-teal-200" onClick={(event) => { event.preventDefault(); navigate('/') }}>{t('manual')}</a>
      <a href="/reviews" className="text-teal-200" onClick={(event) => { event.preventDefault(); navigate('/reviews') }}>{t('inbox')}</a>
      <label className="ml-auto flex items-center gap-2 text-xs text-slate-400">
        <span className="sr-only">{t('language')}</span>
        <select value={language} onChange={(event) => setLanguage(event.target.value === 'es' ? 'es' : 'en')} className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-slate-200">
          <option value="en" lang="en">EN</option><option value="es" lang="es">ES</option>
        </select>
      </label>
    </nav>
    {path === '/' ? <ManualInspector /> : path === '/reviews' ? <ReviewInbox navigate={navigate} />
      : detail ? <ReviewDetail key={detail[1]} id={detail[1]} />
        : <p role="alert" className="p-6">{t('invalidRoute')}</p>}
  </div>
}

export default function App() {
  return <LanguageProvider><AppContent /></LanguageProvider>
}
