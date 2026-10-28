import type { ParsedDiff } from '../types/diff'

export const MAX_DIFF_BYTES = 1024 * 1024

export async function parseDiff(diff: string): Promise<ParsedDiff> {
  let response: Response
  try {
    response = await fetch('/api/diff/parse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ diff }),
    })
  } catch {
    throw new Error('No se pudo conectar con el backend. Comprueba que esté iniciado en el puerto 8000.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    if (body?.error && typeof body.error.message === 'string') {
      const location = typeof body.error.line === 'number' ? ` Línea ${body.error.line}.` : ''
      throw new Error(`${body.error.message}${location}`)
    }
    throw new Error(`El backend respondió con HTTP ${response.status}. Comprueba que esté iniciado en el puerto 8000.`)
  }
  try {
    return await response.json() as ParsedDiff
  } catch {
    throw new Error('El backend devolvió una respuesta JSON inválida.')
  }
}
