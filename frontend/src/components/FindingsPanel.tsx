import type { AnalysisResponse, ReferenceCheck } from '../types/analysis'

const severityLabels = { low: 'Baja', medium: 'Media', high: 'Alta', critical: 'Crítica' }
const reasonLabels: Record<ReferenceCheck['reason'], string> = {
  matched: 'Ruta, hunk, lado, líneas y cita coinciden con el diff.',
  file_not_found: 'El archivo citado no existe en el diff.',
  hunk_not_found: 'El hunk no pertenece al archivo citado.',
  path_mismatch: 'La ruta no coincide con el lado citado.',
  invalid_range: 'El rango de líneas no es válido.',
  line_not_found: 'Las líneas no existen en ese hunk y lado.',
  quote_mismatch: 'El fragmento citado no coincide exactamente.',
}

interface Props {
  analysis: AnalysisResponse | null
  loading: boolean
  error: string
  canReview: boolean
  onReview: () => void
}

export function FindingsPanel({ analysis, loading, error, canReview, onReview }: Props) {
  return (
    <aside aria-labelledby="findings-title" className="rounded-2xl border border-dashed border-slate-700 p-6">
      <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">Muse Spark 1.3</span>
      <h2 id="findings-title" className="mt-3 text-lg font-semibold text-slate-300">Hallazgos de IA</h2>
      <p className="mt-3 text-sm leading-6 text-slate-400">El modelo propone hipótesis. El backend comprueba las referencias contra el diff; eso no demuestra que el riesgo exista.</p>
      <button type="button" disabled={!canReview || loading} onClick={onReview}
        className="secondary-button mt-4 w-full">{loading ? 'Revisando con Muse Spark…' : 'Revisar con Muse Spark'}</button>
      <p className="mt-3 text-xs leading-5 text-slate-500">Primero analiza el diff. Al revisar, se envía a Meta y se consumen créditos. No se ejecuta código ni pruebas sugeridas.</p>
      {loading && <p role="status" className="mt-4 text-sm text-teal-200">Esperando la revisión del modelo…</p>}
      {error && <p role="alert" className="mt-4 break-words text-sm text-rose-200">{error}</p>}
      {analysis && <div className="mt-5 space-y-5">
        <div><h3 className="text-sm font-semibold">Resumen del modelo · hipótesis</h3>
          <p className="mt-2 text-sm whitespace-pre-wrap text-slate-400">{analysis.summary}</p></div>
        {analysis.findings.length === 0 && <p role="status" className="text-sm text-slate-400">No se propusieron riesgos. Esto no garantiza que el cambio esté libre de problemas.</p>}
        {analysis.findings.map(({ hypothesis, reference_checks, all_references_valid }, index) => (
          <article key={index} className="min-w-0 space-y-3 border-t border-slate-700 pt-4">
            <p className="text-xs text-amber-200">Hipótesis del modelo · Severidad estimada: {severityLabels[hypothesis.severity]}</p>
            <h3 className="break-words text-sm font-semibold text-white">{hypothesis.title}</h3>
            <p className="break-words text-sm whitespace-pre-wrap text-slate-400">{hypothesis.explanation}</p>
            <p className={`text-xs ${all_references_valid ? 'text-teal-200' : 'text-amber-200'}`}>
              {all_references_valid ? 'Referencias estructuralmente válidas' : 'Hay referencias no válidas'}
            </p>
            <ul className="space-y-3">{reference_checks.map((check, refIndex) => {
              const ref = check.reference
              const location = `${ref.path} · ${ref.side === 'old' ? 'anterior' : 'nueva'}:${ref.line_start}–${ref.line_end}`
              return <li key={refIndex} className="break-all text-xs">
                {check.status === 'valid' && check.diff_line !== null
                  ? <a href={`#${ref.hunk_id}-line-${check.diff_line}`} className="text-teal-200 underline">{location}</a>
                  : <span className="text-amber-200">{location}</span>}
                <p className="mt-1 text-slate-400">{reasonLabels[check.reason]}</p>
                <pre className="mt-2 max-h-40 overflow-auto rounded bg-slate-950 p-2 whitespace-pre text-slate-300">{ref.quote}</pre>
              </li>
            })}</ul>
            <h4 className="text-xs font-semibold text-slate-300">Pruebas sugeridas · sin ejecutar</h4>
            <ul className="list-disc space-y-2 pl-4 text-xs text-slate-400">{hypothesis.suggested_tests.map((test, testIndex) => <li key={testIndex} className="break-words whitespace-pre-wrap">{test}</li>)}</ul>
          </article>
        ))}
      </div>}
    </aside>
  )
}
