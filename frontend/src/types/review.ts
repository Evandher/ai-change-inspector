export type AgentSource = 'unknown' | 'muse_code' | 'codex' | 'claude_code' | 'other'
export interface CaptureCoverage {
  version: 1
  include_untracked: boolean
  untracked_seen: number | null
  included_untracked: string[]
  exclusions: Partial<Record<'policy' | 'sensitive' | 'binary' | 'too_large' | 'unsafe' | 'encoding' | 'budget', number>>
}

import type { AnalysisResponse, AuditRun, ProviderDiagnostic } from './analysis'
import type { ParsedDiff } from './diff'

export interface ReviewSummary {
  agent_source?: AgentSource
  review_id: string
  repository: string
  repository_root: string
  origin: 'mcp'
  scope: 'staged' | 'unstaged'
  created_at: string
  finished_at: string | null
  status: 'pending' | 'analyzing' | 'completed' | 'error'
  diff_sha256: string
  review_url: string
  error: { code: string; message: string; recoverable: boolean } | null
}

export interface ReviewDetail extends ReviewSummary {
  recovery?: RecoveryView | null
  audit?: AuditRun | null
  capture_coverage?: CaptureCoverage | null
  diff: string
  parsed_diff: ParsedDiff
  analysis: AnalysisResponse | null
  parent_review_id: string | null
  child_review_ids: string[]
  feedback: HumanFeedback[]
}

export interface ReviewPage { items: ReviewSummary[]; total: number }

export type Decision = 'request_changes' | 'accept_risk' | 'dismiss'
export interface HumanFeedback {
  finding_index: number
  decision: Decision | null
  comment: string
  updated_at: string | null
}

export interface TimelineItem extends ReviewSummary { parent_review_id: string | null }
export interface ReviewTimeline {
  review_id: string
  repository: string
  repository_root: string
  items: TimelineItem[]
  missing_review_ids: string[]
  incomplete: boolean
  truncated: boolean
}
export interface ReviewComparison { parent: ReviewDetail; child: ReviewDetail }


export interface RecoveryAttempt {
  attempt_id: string
  request_id: string
  batch_id: string
  number: number
  status: 'pending' | 'running' | 'completed' | 'failed' | 'incomplete' | 'interrupted'
  created_at: string
  started_at: string | null
  finished_at: string | null
  output_budget: number
  error_code: string | null
  diagnostics: ProviderDiagnostic | null
}
export interface RecoveryView {
  supported: boolean
  blocked_reason: string | null
  version: number
  active_request_id: string | null
  eligible_batch_ids: string[]
  batch_blockers: Record<string, string>
  attempts: RecoveryAttempt[]
  max_calls_per_action: number
  max_per_batch: number
  max_per_review: number
  remaining_review: number
  output_budget: number | null
  original_status: string
  original_finished_at: string | null
  original_audit: AuditRun | null
}
export interface RecoveryRequest {
  request_id: string
  batch_ids: string[]
  expected_version: number
  expected_output_budget: number
  confirm_paid: true
}
