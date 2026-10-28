import type { ParsedDiff } from './diff'

export interface Reference {
  file_id: string
  hunk_id: string
  path: string
  side: 'old' | 'new'
  line_start: number
  line_end: number
  quote: string
}

export interface ModelFinding {
  title: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  explanation: string
  references: Reference[]
  suggested_tests: string[]
}

export interface ReferenceCheck {
  reference: Reference
  status: 'valid' | 'invalid'
  reason: 'matched' | 'file_not_found' | 'hunk_not_found' | 'path_mismatch' | 'invalid_range' | 'line_not_found' | 'quote_mismatch'
  diff_line: number | null
}

export interface CheckedFinding {
  hypothesis: ModelFinding
  reference_checks: ReferenceCheck[]
  all_references_valid: boolean
}

export interface AnalysisResponse {
  model: 'muse-spark-1.3'
  summary: string
  findings: CheckedFinding[]
  parsed_diff: ParsedDiff
}
