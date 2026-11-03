import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import type { AnalysisResponse } from '../types/analysis'
import type { ParsedDiff } from '../types/diff'
import { EvidenceContext } from '../lib/evidenceNavigation'
import type { EvidenceSelection } from '../lib/evidenceNavigation'

// Immediate scrolling avoids motion, including on repeated activation of an anchor.
function reveal(id: string) {
  const element = document.getElementById(id)
  element?.focus({ preventScroll: true })
  element?.scrollIntoView?.({ block: 'center', inline: 'nearest', behavior: 'instant' })
}

export function EvidenceNavigation({ analysis, parsed, prefix = '', scope, children }: {
  analysis: AnalysisResponse | null; parsed: ParsedDiff | null; prefix?: string; scope?: string; children: ReactNode
}) {
  const [selected, setSelected] = useState<EvidenceSelection | null>(null)
  useEffect(() => {
    function resolveHash() {
      const hash = window.location.hash.slice(1)
      if (!hash) return
      for (const [findingIndex, finding] of (analysis?.findings ?? []).entries()) {
        for (const [refIndex, check] of finding.reference_checks.entries()) {
          const targetId = `${prefix}${check.reference.hunk_id}-line-${check.diff_line}`
          if (check.status === 'valid' && check.diff_line !== null && hash === targetId) {
            setSelected({ reference: check.reference, title: finding.hypothesis.title,
              originId: `${prefix}evidence-${findingIndex}-${refIndex}`, targetId })
            reveal(targetId)
            return
          }
        }
      }
      // Keep existing file/hunk/line fragments usable without inventing evidence.
      if (parsed?.files.some(file => hash === `${prefix}${file.file_id}` || file.hunks.some(hunk =>
        hash === `${prefix}${hunk.hunk_id}` || hunk.lines.some(line => hash === `${prefix}${hunk.hunk_id}-line-${line.diff_line}`)))) reveal(hash)
    }
    resolveHash()
    window.addEventListener('hashchange', resolveHash)
    return () => window.removeEventListener('hashchange', resolveHash)
  }, [analysis, parsed, prefix])
  function activate(selection: EvidenceSelection) {
    setSelected(selection)
    if (window.location.hash !== `#${selection.targetId}`) window.history.pushState(null, '', `#${selection.targetId}`)
    reveal(selection.targetId)
  }
  function back() {
    if (!selected) return
    const origin = document.getElementById(selected.originId)
    const toggle = origin?.closest('.finding-body')?.querySelector<HTMLButtonElement>('.disclosure-toggle')
    if (toggle?.getAttribute('aria-expanded') === 'false') toggle.click()
    requestAnimationFrame(() => reveal(selected.originId))
  }
  return <EvidenceContext.Provider value={{ selected, scope, activate, back }}>{children}</EvidenceContext.Provider>
}
