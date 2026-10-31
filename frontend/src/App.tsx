import { AppShell } from './components/AppShell'
import { Overview } from './components/Overview'
import { ReviewEvolution } from './components/ReviewEvolution'
import { ReviewCompare } from './components/ReviewCompare'
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
    <div className="manual-inspector">
      <main className="page manual-page space-y-8">
        <div className="page-heading"><h1>{t('manual')}</h1><p>{t('tagline')}</p></div>
        <section aria-labelledby="input-title" className="rounded-lg border border-edge bg-panel p-5 sm:p-6">
          <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
            <div><h2 id="input-title" className="text-lg font-semibold text-primary">{t('inspect')}</h2>
              <p className="mt-1 text-sm text-secondary">{t('pasteOutput')} <code>git diff --no-ext-diff --no-color --src-prefix=a/ --dst-prefix=b/</code>.</p></div>
            <div className="flex flex-wrap gap-2" aria-label={t('examples')}>
              {examples.map((example) => <button key={example.label} type="button" className="secondary-button" disabled={busy} onClick={() => updateDiff(example.diff)}>{t(example.label)}</button>)}
            </div>
          </div>
          <form onSubmit={handleSubmit}>
            <label htmlFor="diff-input" className="mb-2 block text-sm font-medium">{t('gitDiff')}</label>
            <textarea id="diff-input" value={diff} onChange={(event) => updateDiff(event.target.value)} disabled={busy} wrap="off"
              spellCheck={false} placeholder={'diff --git a/example.py b/example.py\n--- a/example.py\n+++ b/example.py\n@@ -1 +1 @@\n-old\n+new'}
              aria-describedby="size-help" className="h-64 w-full resize-y rounded-lg border border-edge-strong bg-canvas p-4 font-mono text-sm leading-6 text-primary placeholder:text-muted" />
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p id="size-help" className={`text-xs ${bytes > MAX_DIFF_BYTES ? 'text-danger' : 'text-secondary'}`}>{bytes.toLocaleString(language)} / {MAX_DIFF_BYTES.toLocaleString(language)} bytes · UTF-8</p>
              <div className="flex gap-3">
                <button type="button" className="secondary-button" disabled={busy || !diff} onClick={() => updateDiff('')}>{t('clear')}</button>
                <button type="submit" disabled={busy} className="primary-button">{loading ? t('parsing') : t('parse')}</button>
              </div>
            </div>
          </form>
          {loading && <p role="status" className="mt-4 text-sm text-info">{t('processing')}</p>}
          {error != null && <p role="alert" className="mt-4 rounded-lg border border-danger bg-danger-soft p-3 text-sm text-danger">{errorText(error, t)}</p>}
        </section>
        <div className="grid items-start gap-6 review-layout">
          <DiffExplorer result={result} />
          <FindingsPanel analysis={analysis} loading={reviewLoading} error={reviewError == null ? '' : errorText(reviewError, t)}
            canReview={!!result && !busy} onReview={handleReview} />
        </div>
      </main>
      <footer className="mx-auto max-w-screen-2xl px-6 pb-8 text-xs text-muted">{t('footer')}</footer>
    </div>
  )
}

function AppContent() {
  const { t } = useLanguage()
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
  const evolution = /^\/reviews\/([0-9a-f-]{36})\/evolution$/.exec(path)
  const comparison = /^\/reviews\/([0-9a-f-]{36})\/compare\/([0-9a-f-]{36})$/.exec(path)
  const detail = /^\/reviews\/([0-9a-f-]{36})$/.exec(path)
  return <AppShell path={path} navigate={navigate}>
    {path === '/' ? <Overview navigate={navigate} /> : path === '/diff' ? <ManualInspector /> : path === '/reviews' ? <ReviewInbox navigate={navigate} />
      : evolution ? <ReviewEvolution key={evolution[1]} id={evolution[1]} navigate={navigate} />
      : comparison ? <ReviewCompare key={`${comparison[1]}-${comparison[2]}`} id={comparison[1]} otherId={comparison[2]} navigate={navigate} />
      : detail ? <ReviewDetail key={detail[1]} id={detail[1]} navigate={navigate} />
        : <p role="alert" className="p-6">{t('invalidRoute')}</p>}
  </AppShell>
}

export default function App() {
  return <LanguageProvider><AppContent /></LanguageProvider>
}
