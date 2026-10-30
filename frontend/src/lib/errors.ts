import { en } from './translations'
import type { TranslationKey } from './translations'
import { translator } from './i18n'
import type { Translate } from './i18n'

export class DisplayError extends Error {
  code: string
  line?: number
  status?: number
  constructor(code: string, line?: number, status?: number) {
    super(errorText({ code, line, status }, translator('en')))
    this.code = code
    this.line = line
    this.status = status
  }
}
export function errorText(error: unknown, t: Translate): string {
  const data = typeof error === 'object' && error !== null && 'code' in error ? error as { code: string; line?: number; status?: number } : { code: 'unknownError' }
  const key = Object.prototype.hasOwnProperty.call(en, data.code) ? data.code as TranslationKey : 'unknownError'
  const code = /^[a-zA-Z0-9_]{1,64}$/.test(data.code) ? data.code : 'unknown_error'
  const message = t(key, { status: data.status ?? '' })
  return `${message}${key === 'unknownError' ? ` (${code})` : ''}${typeof data.line === 'number' ? ` ${t('errorLine', { line: data.line })}` : ''}`
}
