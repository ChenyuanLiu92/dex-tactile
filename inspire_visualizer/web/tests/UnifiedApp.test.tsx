import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'

import { UnifiedApp } from '../src/UnifiedApp'
import { I18nProvider } from '../src/i18n/I18nProvider'

vi.mock('../src/App', () => ({
  default: ({ controlEnabled }: { controlEnabled?: boolean }) => (
    <div>DIGITAL MOCK {controlEnabled ? 'CONTROL' : 'READ ONLY'}</div>
  ),
}))
vi.mock('../src/vision/VisionWorkbench', () => ({
  VisionWorkbench: ({ controlEnabled }: { controlEnabled?: boolean }) => <div>VISION MOCK {controlEnabled ? 'CONTROL' : 'READ ONLY'}</div>,
}))

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
    const requested = init?.body ? JSON.parse(String(init.body)).owner : 'vision'
    return new Response(JSON.stringify({
      owner: requested,
      vision_state: 'DISARMED',
      manual_control_enabled: requested === 'manual',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }))
})
vi.mock('../src/vision/api', () => ({
  EMPTY_SNAPSHOT: {},
  useTrackingSnapshot: () => ({
    status: 'TRACKING',
    control: { state: 'DISARMED' },
  }),
}))

test('switches views independently while Vision retains exclusive control', () => {
  render(<UnifiedApp />)

  expect(screen.getByText('VISION MOCK CONTROL').parentElement).toHaveAttribute('aria-hidden', 'false')
  expect(screen.getByText('DIGITAL MOCK READ ONLY').parentElement).toHaveAttribute('aria-hidden', 'true')
  expect(screen.getByText('TRACKING')).toBeVisible()
  expect(screen.getByText('DISARMED')).toBeVisible()

  fireEvent.click(screen.getByRole('button', { name: /DIGITAL TWIN/ }))

  expect(screen.getByText('DIGITAL MOCK READ ONLY').parentElement).toHaveAttribute('aria-hidden', 'false')
  expect(screen.getByText('VISION MOCK CONTROL').parentElement).toHaveAttribute('aria-hidden', 'true')
})

test('hands exclusive control to Digital Twin and makes Vision read only', async () => {
  render(<UnifiedApp />)

  fireEvent.click(screen.getByRole('button', { name: 'MANUAL' }))

  await waitFor(() => expect(screen.getByText('DIGITAL MOCK CONTROL')).toBeInTheDocument())
  expect(screen.getByText('DIGITAL MOCK CONTROL').parentElement).toHaveAttribute('aria-hidden', 'false')
  expect(screen.getByText('VISION MOCK READ ONLY')).toBeInTheDocument()
  expect(fetch).toHaveBeenCalledWith('/api/control-owner', expect.objectContaining({ method: 'PUT' }))
})

test('switches the complete workbench command bar to Chinese', () => {
  render(<I18nProvider><UnifiedApp /></I18nProvider>)

  fireEvent.click(screen.getByRole('button', { name: '中文' }))

  expect(screen.getByRole('button', { name: /视觉控制/ })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /数字孪生/ })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '手动' })).toBeInTheDocument()
  expect(screen.getByText('正在跟踪')).toBeVisible()
  expect(screen.getByText('未启用')).toBeVisible()
  expect(screen.getByRole('button', { name: 'EN' })).toBeInTheDocument()
})
