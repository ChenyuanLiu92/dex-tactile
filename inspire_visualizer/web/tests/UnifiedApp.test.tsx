import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { UnifiedApp } from '../src/UnifiedApp'
import { I18nProvider } from '../src/i18n/I18nProvider'

vi.mock('../src/App', () => ({
  default: ({ controlEnabled }: { controlEnabled?: boolean }) => (
    <div>DIGITAL MOCK {controlEnabled ? 'CONTROL' : 'READ ONLY'}</div>
  ),
}))
vi.mock('../src/vision/VisionWorkbench', () => ({
  VisionWorkbench: () => <div>VISION MOCK</div>,
}))
vi.mock('../src/vision/api', () => ({
  EMPTY_SNAPSHOT: {},
  useTrackingSnapshot: () => ({
    status: 'TRACKING',
    control: { state: 'DISARMED' },
  }),
}))

test('switches between integrated workbenches and keeps digital motion read only', () => {
  render(<UnifiedApp />)

  expect(screen.getByText('VISION MOCK').parentElement).toHaveAttribute('aria-hidden', 'false')
  expect(screen.getByText('DIGITAL MOCK READ ONLY').parentElement).toHaveAttribute('aria-hidden', 'true')
  expect(screen.getByText('TRACKING')).toBeVisible()
  expect(screen.getByText('DISARMED')).toBeVisible()

  fireEvent.click(screen.getByRole('button', { name: /DIGITAL TWIN/ }))

  expect(screen.getByText('DIGITAL MOCK READ ONLY').parentElement).toHaveAttribute('aria-hidden', 'false')
  expect(screen.getByText('VISION MOCK').parentElement).toHaveAttribute('aria-hidden', 'true')
})

test('switches the complete workbench command bar to Chinese', () => {
  render(<I18nProvider><UnifiedApp /></I18nProvider>)

  fireEvent.click(screen.getByRole('button', { name: '中文' }))

  expect(screen.getByRole('button', { name: /视觉控制/ })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /数字孪生/ })).toBeInTheDocument()
  expect(screen.getByText('正在跟踪')).toBeVisible()
  expect(screen.getByText('未启用')).toBeVisible()
  expect(screen.getByRole('button', { name: 'EN' })).toBeInTheDocument()
})
