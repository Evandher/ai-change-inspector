import type { ReactNode } from 'react'
import { useLanguage } from '../lib/i18n'
import type { AnalysisResponse } from '../types/analysis'
import { Icon } from './Icon'
import { AnimatedDisclosure } from './AnimatedDisclosure'

interface Props {
  analysis: AnalysisResponse | null
  loading: boolean
  error: string
  canReview: boolean
  onReview: () => void
  idPrefix?: string
  readOnly?: boolean
  renderFeedback?: (index: number) => ReactNode
}

export function FindingsPanel({ analysis, loading, error, canReview, onReview, readOnly = false, renderFeedback, idPrefix = '' }: Props) {
  const { t } = useLanguage()
  return (
    <aside aria-labelledby={`${idPrefix}findings-title`} className="findings-panel">
      <div className="findings-heading"><h2 id={`${idPrefix}findings-title`}>{t('findings')}</h2><span>Muse Spark 1.3</span></div>
      <p className="findings-boundary">{t('hypothesisHelp')}</p>
      {!readOnly && <><button type="button" disabled={!canReview || loading} onClick={onReview}
        className="primary-button mt-4 w-full">{loading ? t('reviewing') : t('review')}</button>
      <p className="mt-3 text-xs leading-5 text-muted">{t('creditsHelp')}</p></>}
      {loading && <p role="status" className="mt-4 text-sm text-info">{t('waiting')}</p>}
      {error && <p role="alert" className="mt-4 break-words text-sm text-danger">{error}</p>}
      {analysis && <div className="mt-5 space-y-5">
        <details className="model-summary" open={!readOnly}><summary>{t('summary')}</summary>
          <p className="mt-2 text-sm whitespace-pre-wrap text-secondary">{analysis.summary}</p></details>
        {analysis.findings.length === 0 && <p role="status" className="text-sm text-secondary">{t('noFindings')}</p>}
        {analysis.findings.map(({ hypothesis, reference_checks, all_references_valid }, index) => (
          <article key={index} className="finding min-w-0">
            <div className="finding-header"><span className={`finding-symbol severity-${hypothesis.severity}`}><Icon name="alert" /></span><div><h3 className="break-words text-sm font-semibold text-primary">{hypothesis.title}</h3><p className={`severity severity-${hypothesis.severity}`}>{t('severity')} {t(hypothesis.severity)}</p></div></div>
            <AnimatedDisclosure label={t('findingDetails')} defaultOpen={index === 0}>
            <p className="mt-3 break-words text-sm whitespace-pre-wrap text-secondary">{hypothesis.explanation}</p>
            <div className="finding-columns"><div><h4>{t('structuralEvidence')}</h4>
            <p className={`text-xs ${all_references_valid ? 'evidence-valid' : 'text-warning'}`}>
              {all_references_valid ? t('validReferences') : t('invalidReferences')}
            </p>
            <ul className="space-y-3">{reference_checks.map((check, refIndex) => {
              const ref = check.reference
              const location = `${ref.path} · ${ref.side === 'old' ? t('oldSide') : t('newSide')}:${ref.line_start}–${ref.line_end}`
              return <li key={refIndex} className="break-all text-xs">
                {check.status === 'valid' && check.diff_line !== null
                  ? <a href={`#${idPrefix}${ref.hunk_id}-line-${check.diff_line}`} className="text-accent-hover underline">{location}</a>
                  : <span className="text-warning">{location}</span>}
                <p className="mt-1 text-secondary">{t(check.reason)}</p>
                <pre className="mt-2 max-h-40 overflow-auto rounded bg-canvas p-2 whitespace-pre text-primary">{ref.quote}</pre>
              </li>
            })}</ul>
            </div><div><h4 className="text-xs font-semibold text-primary">{t('tests')}</h4>
            <ul className="list-disc space-y-2 pl-4 text-xs text-secondary">{hypothesis.suggested_tests.map((test, testIndex) => <li key={testIndex} className="break-words whitespace-pre-wrap">{test}</li>)}</ul>
            </div></div></AnimatedDisclosure>
            {renderFeedback?.(index)}
          </article>
        ))}
      </div>}
    </aside>
  )
}
