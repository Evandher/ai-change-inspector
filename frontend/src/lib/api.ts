import { DisplayError } from './errors'
import type { ParsedDiff } from '../types/diff'
import type { AnalysisResponse } from '../types/analysis'

export const MAX_DIFF_BYTES = 1024 * 1024

async function requestDiff<T>(endpoint: string, diff: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ diff }),
    })
  } catch {
    throw new DisplayError('connection')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    if (typeof body?.error?.code === 'string') {
      throw new DisplayError(body.error.code, typeof body.error.line === 'number' ? body.error.line : undefined)
    }
    throw new DisplayError('httpError', undefined, response.status)
  }
  try {
    return await response.json() as T
  } catch {
    throw new DisplayError('invalidJson')
  }
}

export function parseDiff(diff: string): Promise<ParsedDiff> {
  return requestDiff('/api/diff/parse', diff)
}

export function analyzeDiff(diff: string): Promise<AnalysisResponse> {
  return requestDiff('/api/diff/analyze', diff)
}
