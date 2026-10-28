import { useState } from 'react'
import type { FormEvent } from 'react'
import { DiffExplorer } from './components/DiffExplorer'
import { FindingsPanel } from './components/FindingsPanel'
import { MAX_DIFF_BYTES, parseDiff } from './lib/api'
import { examples } from './lib/examples'
import type { ParsedDiff } from './types/diff'

export default function App() {
  const [diff, setDiff] = useState('')
  const [result, setResult] = useState<ParsedDiff | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const bytes = new TextEncoder().encode(diff).length

  function updateDiff(value: string) {
    setDiff(value)
    setResult(null)
    setError('')
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setResult(null)
    if (!diff.trim()) {
      setError('Pega un diff de Git antes de continuar.')
      return
    }
    if (bytes > MAX_DIFF_BYTES) {
      setError('El diff supera el límite de 1 MiB en UTF-8.')
      return
    }
    setLoading(true)
    try {
      setResult(await parseDiff(diff))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo analizar el diff.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      <header className="border-b border-slate-800">
        <div className="mx-auto flex max-w-screen-2xl flex-wrap items-center justify-between gap-4 px-6 py-6">
          <div className="flex items-center gap-3">
            <span aria-hidden="true" className="rounded-xl bg-teal-300 p-3 font-mono font-bold text-slate-950">±</span>
            <div><h1 className="text-xl font-semibold tracking-tight text-white">AI Change Inspector</h1>
              <p className="mt-1 text-sm text-slate-400">Cada cambio, en contexto.</p></div>
          </div>
          <span className="rounded-full border border-teal-800 bg-teal-950 px-3 py-1 text-xs text-teal-200">Sprint 1 · Explorador de diffs</span>
        </div>
      </header>
      <main className="mx-auto max-w-screen-2xl space-y-8 px-6 py-8">
        <section aria-labelledby="input-title" className="rounded-2xl border border-slate-800 bg-slate-900 p-5 sm:p-6">
          <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
            <div><h2 id="input-title" className="text-lg font-semibold text-white">Inspecciona un cambio</h2>
              <p className="mt-1 text-sm text-slate-400">Pega la salida de <code className="text-teal-200">git diff --no-ext-diff --no-color --src-prefix=a/ --dst-prefix=b/</code>.</p></div>
            <div className="flex flex-wrap gap-2" aria-label="Ejemplos de diff">
              {examples.map((example) => <button key={example.label} type="button" className="secondary-button" disabled={loading} onClick={() => updateDiff(example.diff)}>{example.label}</button>)}
            </div>
          </div>
          <form onSubmit={handleSubmit}>
            <label htmlFor="diff-input" className="mb-2 block text-sm font-medium">Diff de Git</label>
            <textarea id="diff-input" value={diff} onChange={(event) => updateDiff(event.target.value)} disabled={loading}
              spellCheck={false} placeholder={'diff --git a/example.py b/example.py\n--- a/example.py\n+++ b/example.py\n@@ -1 +1 @@\n-old\n+new'}
              aria-describedby="size-help" className="h-64 w-full resize-y rounded-xl border border-slate-700 bg-slate-950 p-4 font-mono text-sm leading-6 text-slate-200 placeholder:text-slate-600" />
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p id="size-help" className={`text-xs ${bytes > MAX_DIFF_BYTES ? 'text-rose-300' : 'text-slate-400'}`}>{bytes.toLocaleString('es')} / 1.048.576 bytes · UTF-8</p>
              <div className="flex gap-3">
                <button type="button" className="secondary-button" disabled={loading || !diff} onClick={() => updateDiff('')}>Limpiar</button>
                <button type="submit" disabled={loading} className="rounded-lg bg-teal-300 px-5 py-2 text-sm font-semibold text-slate-950 hover:bg-teal-200 disabled:opacity-50">{loading ? 'Analizando…' : 'Analizar diff'}</button>
              </div>
            </div>
          </form>
          {loading && <p role="status" className="mt-4 text-sm text-teal-200">Procesando el diff…</p>}
          {error && <p role="alert" className="mt-4 rounded-lg border border-rose-900 bg-rose-950 p-3 text-sm text-rose-200">{error}</p>}
        </section>
        <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_19rem]">
          <DiffExplorer result={result} />
          <FindingsPanel />
        </div>
      </main>
      <footer className="mx-auto max-w-screen-2xl px-6 pb-8 text-xs text-slate-500">Meta AI Developer Hackathon 2026 · GPL v3 · Procesamiento local sin persistencia.</footer>
    </div>
  )
}
