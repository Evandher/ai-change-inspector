export interface ProviderDiagnostic {
  status: string | null
  response_id: string | null
  request_id: string | null
  incomplete_details?: { reason: string | null } | null
  incomplete_details_present: boolean | null
  incomplete_reason: string | null
  provider_error_code: string | null
  http_status: number | null
  input_tokens: number | null
  output_tokens: number | null
  reasoning_tokens: number | null
  max_output_tokens: number
  outcome: string
}
export interface AuditRun {
  version: 1
  status: 'pending' | 'analyzing' | 'completed' | 'partial' | 'incomplete'
  max_requests: number
  request_count: number
  completed_hunk_ids: string[]
  unanalyzed_hunk_ids: string[]
  metadata_only_file_ids: string[]
  batches: {
    batch_id: string
    file_ids: string[]
    hunk_ids: string[]
    status: 'pending' | 'completed' | 'failed' | 'incomplete'
    error_code: string | null
    diagnostics: ProviderDiagnostic | null
    payload_bytes: number
    original_payload_bytes: number
  }[]
}

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
  batch_ids?: string[]
  attempt_ids?: string[]
  hypothesis: ModelFinding
  reference_checks: ReferenceCheck[]
  all_references_valid: boolean
}

export interface AnalysisResponse {
  audit?: AuditRun | null
  model: 'muse-spark-1.3'
  summary: string
  findings: CheckedFinding[]
  parsed_diff: ParsedDiff
}
