import type { ReactNode } from 'react'
import { useLanguage } from '../lib/i18n'
import type { AnalysisResponse } from '../types/analysis'

interface Props {
  analysis: AnalysisResponse | null
  loading: boolean
  error: string
  canReview: boolean
  onReview: () => void
  readOnly?: boolean
  renderFeedback?: (index: number) => ReactNode
}

export function FindingsPanel({ analysis, loading, error, canReview, onReview, readOnly = false, renderFeedback }: Props) {
  const { t } = useLanguage()
  return (
    <aside aria-labelledby="findings-title" className="rounded-2xl border border-dashed border-slate-700 p-6">
      <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">Muse Spark 1.3</span>
      <h2 id="findings-title" className="mt-3 text-lg font-semibold text-slate-300">{t('findings')}</h2>
      <p className="mt-3 text-sm leading-6 text-slate-400">{t('hypothesisHelp')}</p>
      {!readOnly && <><button type="button" disabled={!canReview || loading} onClick={onReview}
        className="secondary-button mt-4 w-full">{loading ? t('reviewing') : t('review')}</button>
      <p className="mt-3 text-xs leading-5 text-slate-500">{t('creditsHelp')}</p></>}
      {loading && <p role="status" className="mt-4 text-sm text-teal-200">{t('waiting')}</p>}
      {error && <p role="alert" className="mt-4 break-words text-sm text-rose-200">{error}</p>}
      {analysis && <div className="mt-5 space-y-5">
        <div><h3 className="text-sm font-semibold">{t('summary')}</h3>
          <p className="mt-2 text-sm whitespace-pre-wrap text-slate-400">{analysis.summary}</p></div>
        {analysis.findings.length === 0 && <p role="status" className="text-sm text-slate-400">{t('noFindings')}</p>}
        {analysis.findings.map(({ hypothesis, reference_checks, all_references_valid }, index) => (
          <article key={index} className="min-w-0 space-y-3 border-t border-slate-700 pt-4">
            <p className="text-xs text-amber-200">{t('severity')} {t(hypothesis.severity)}</p>
            <h3 className="break-words text-sm font-semibold text-white">{hypothesis.title}</h3>
            <p className="break-words text-sm whitespace-pre-wrap text-slate-400">{hypothesis.explanation}</p>
            <p className={`text-xs ${all_references_valid ? 'text-teal-200' : 'text-amber-200'}`}>
              {all_references_valid ? t('validReferences') : t('invalidReferences')}
            </p>
            <ul className="space-y-3">{reference_checks.map((check, refIndex) => {
              const ref = check.reference
              const location = `${ref.path} · ${ref.side === 'old' ? t('oldSide') : t('newSide')}:${ref.line_start}–${ref.line_end}`
              return <li key={refIndex} className="break-all text-xs">
                {check.status === 'valid' && check.diff_line !== null
                  ? <a href={`#${ref.hunk_id}-line-${check.diff_line}`} className="text-teal-200 underline">{location}</a>
                  : <span className="text-amber-200">{location}</span>}
                <p className="mt-1 text-slate-400">{t(check.reason)}</p>
                <pre className="mt-2 max-h-40 overflow-auto rounded bg-slate-950 p-2 whitespace-pre text-slate-300">{ref.quote}</pre>
              </li>
            })}</ul>
            <h4 className="text-xs font-semibold text-slate-300">{t('tests')}</h4>
            <ul className="list-disc space-y-2 pl-4 text-xs text-slate-400">{hypothesis.suggested_tests.map((test, testIndex) => <li key={testIndex} className="break-words whitespace-pre-wrap">{test}</li>)}</ul>
            {renderFeedback?.(index)}
          </article>
        ))}
      </div>}
    </aside>
  )
}
