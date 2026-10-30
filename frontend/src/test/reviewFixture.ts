import type { ReviewDetail } from '../types/review'
import { analysisFixture } from './analysisFixture'
import { parsedFixture } from './fixture'

export const reviewFixture: ReviewDetail = {
  parent_review_id: null, child_review_ids: [], feedback: [],
  review_id: '11111111-1111-4111-8111-111111111111', repository: 'project',
  repository_root: 'D:/demo', origin: 'mcp', scope: 'unstaged',
  created_at: '2026-10-28T12:00:00+00:00', finished_at: '2026-10-28T12:01:00+00:00',
  status: 'completed', diff_sha256: 'a'.repeat(64),
  review_url: 'http://127.0.0.1:5173/reviews/11111111-1111-4111-8111-111111111111',
  error: null, diff: 'diff --git a/a.txt b/a.txt\n-original snapshot\n+stored snapshot\n',
  parsed_diff: parsedFixture, analysis: analysisFixture,
}
