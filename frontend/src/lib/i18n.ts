import { createContext, useContext } from 'react'
import { en, es } from './translations'
import type { TranslationKey } from './translations'

export type Language = 'en' | 'es'
export const LANGUAGE_KEY = 'ai-change-inspector.language'
export type Translate = (key: TranslationKey, params?: Record<string, string | number>) => string
export function translator(language: Language): Translate {
  const messages = language === 'es' ? es : en
  return (key, params = {}) => messages[key].replace(/\{(\w+)\}/g, (_, name: string) => String(params[name] ?? `{${name}}`))
}
export function savedLanguage(): Language {
  try { return localStorage.getItem(LANGUAGE_KEY) === 'es' ? 'es' : 'en' }
  catch { return 'en' }
}
export const LanguageContext = createContext({ language: 'en' as Language, t: translator('en'), setLanguage: (language: Language) => { void language } })
export const useLanguage = () => useContext(LanguageContext)
