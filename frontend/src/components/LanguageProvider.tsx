import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { LANGUAGE_KEY, LanguageContext, savedLanguage, translator } from '../lib/i18n'
import type { Language } from '../lib/i18n'

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(savedLanguage)
  useEffect(() => {
    document.documentElement.lang = language
    try { localStorage.setItem(LANGUAGE_KEY, language) } catch { /* Session-only if storage is disabled. */ }
  }, [language])
  return <LanguageContext.Provider value={{ language, setLanguage, t: translator(language) }}>{children}</LanguageContext.Provider>
}
