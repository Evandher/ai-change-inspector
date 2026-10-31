import { DisplayError } from './errors'
import type { ReviewDetail, ReviewPage, HumanFeedback, Decision, ReviewTimeline, ReviewComparison } from '../types/review'

async function request<T>(url: string, method = 'GET', body: unknown = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, method === 'GET' ? { cache: 'no-store' } : {
      method, headers: { 'Content-Type': 'application/json', 'X-Inspector-Request': '1' },
      body: JSON.stringify(body),
    })
  } catch {
    throw new DisplayError('inboxConnection')
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new DisplayError(typeof data?.error?.code === 'string' ? data.error.code : 'httpError', undefined, response.status)
  }
  try { return await response.json() as T }
  catch { throw new DisplayError('invalidJson') }
}

export const listReviews = (offset = 0) => request<ReviewPage>(`/api/reviews?limit=20&offset=${offset}`)
export const getReview = (id: string) => request<ReviewDetail>(`/api/reviews/${encodeURIComponent(id)}`)
export const analyzeReview = (id: string) => request<ReviewDetail>(`/api/reviews/${encodeURIComponent(id)}/analyze`, 'POST')

export const saveFeedback = (id: string, index: number, data: { decision: Decision; comment: string }) =>
  request<HumanFeedback>(`/api/reviews/${encodeURIComponent(id)}/feedback/${index}`, 'PUT', data)

export const getTimeline = (id: string) => request<ReviewTimeline>(`/api/reviews/${encodeURIComponent(id)}/timeline`)
export const compareReviews = (id: string, otherId: string) => request<ReviewComparison>(`/api/reviews/${encodeURIComponent(id)}/compare/${encodeURIComponent(otherId)}`)
