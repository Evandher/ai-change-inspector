import { afterEach, expect, it, vi } from 'vitest'
import { parseDiff } from './api'

afterEach(() => vi.unstubAllGlobals())

it('handles proxy failures that are not JSON', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('unavailable', { status: 502 })))
  await expect(parseDiff('diff')).rejects.toThrow('HTTP 502')
})

it('handles malformed successful JSON', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('not JSON')))
  await expect(parseDiff('diff')).rejects.toThrow('invalid JSON')
})
