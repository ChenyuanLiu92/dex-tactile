import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it } from 'vitest'

import { I18nProvider, useI18n } from '../src/i18n/I18nProvider'
import { messages } from '../src/i18n/messages'

const wrapper = ({ children }: { children: ReactNode }) => <I18nProvider>{children}</I18nProvider>

describe('viewer i18n', () => {
  beforeEach(() => {
    const values = new Map<string, string>()
    Object.defineProperty(window, 'localStorage', { configurable: true, value: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
      clear: () => values.clear(),
    } })
  })

  it('keeps English and Chinese dictionaries in exact key parity', () => {
    expect(Object.keys(messages['zh-CN']).sort()).toEqual(Object.keys(messages.en).sort())
  })

  it('defaults to English, interpolates values, and persists a switch', () => {
    const { result } = renderHook(useI18n, { wrapper })
    expect(result.current.locale).toBe('en')
    expect(result.current.t('gateway.online', { count: 2, devices: 'DEVICES' })).toBe('LINK ONLINE · 2 DEVICES')
    act(() => result.current.toggleLocale())
    expect(result.current.locale).toBe('zh-CN')
    expect(localStorage.getItem('inspire-language')).toBe('zh-CN')
    expect(result.current.t('common.leftHand')).toBe('左手')
  })

  it('restores the persisted Chinese locale', () => {
    localStorage.setItem('inspire-language', 'zh-CN')
    const { result } = renderHook(useI18n, { wrapper })
    expect(result.current.locale).toBe('zh-CN')
  })
})
