import type { AnalysisResponse } from './analysis'
import type { ParsedDiff } from './diff'

export interface ReviewSummary {
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
