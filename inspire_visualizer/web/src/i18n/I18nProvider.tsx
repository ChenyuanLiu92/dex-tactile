import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { messages, type Locale, type MessageKey } from './messages'

const STORAGE_KEY = 'inspire-language'
type Values = Record<string, string | number>

function interpolate(message: string, values?: Values): string {
  let result = message
  for (const [name, replacement] of Object.entries(values ?? {})) result = result.replaceAll(`{${name}}`, String(replacement))
  return result
}

interface I18nValue {
  locale: Locale
  setLocale: (locale: Locale) => void
  toggleLocale: () => void
  t: (key: MessageKey, values?: Values) => string
}

const englishFallback: I18nValue = {
  locale: 'en',
  setLocale: () => undefined,
  toggleLocale: () => undefined,
  t: (key, values) => interpolate(messages.en[key], values),
}
const I18nContext = createContext<I18nValue>(englishFallback)

function initialLocale(): Locale {
  try { return localStorage.getItem(STORAGE_KEY) === 'zh-CN' ? 'zh-CN' : 'en' } catch { return 'en' }
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale)
  const setLocale = (next: Locale) => {
    setLocaleState(next)
    try { localStorage.setItem(STORAGE_KEY, next) } catch { /* Storage may be unavailable. */ }
  }
  useEffect(() => { document.documentElement.lang = locale }, [locale])
  const value = useMemo<I18nValue>(() => ({
    locale,
    setLocale,
    toggleLocale: () => setLocale(locale === 'en' ? 'zh-CN' : 'en'),
    t: (key, values) => interpolate(messages[locale][key], values),
  }), [locale])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  return useContext(I18nContext)
}

export function regionKey(id: string): MessageKey {
  const key = `region.${id}` as MessageKey
  return key in messages.en ? key : 'region.palm'
}

export type { Locale, MessageKey }
