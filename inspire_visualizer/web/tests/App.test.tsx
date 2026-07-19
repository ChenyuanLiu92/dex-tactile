import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { HandSide, HandsSnapshot } from '../src/app/types'
import { initialHands } from '../src/api/socketState'
import { initialTactileFrames } from '../src/api/socketState'
import App from '../src/App'
import { I18nProvider, useI18n } from '../src/i18n/I18nProvider'

let mockedHands: HandsSnapshot

vi.mock('../src/api/useDeviceSocket', () => ({
  useDeviceSocket: () => ({
    hands: mockedHands,
    tactileFrames: initialTactileFrames,
    status: 'connected' as const,
    lastError: null,
    clearError: vi.fn(),
    send: vi.fn(),
  }),
}))

vi.mock('../src/hand-viewer/HandScene', () => ({
  HandScene: ({ sides, mode }: { sides: HandSide[]; mode: string }) => (
    <div data-testid="hand-scene" data-workspace-mode={mode}>{sides.join(',')}</div>
  ),
}))

function online(side: HandSide): HandsSnapshot[HandSide] {
  return {
    side,
    connection: 'online',
    actual_angles: [800, 700, 600, 500, 650, 400],
    armed: false,
    updated_at: 1,
    error: null,
    tactile: {
      profile: 'piezoresistive_v1',
      state: 'live',
      target_hz: 20,
      sample_hz: 19.8,
      updated_at: 1,
      error: null,
    },
  }
}

function renderApp() {
  return render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

function renderLocalizedApp() {
  return render(<I18nProvider><TestLanguageButton /><App /></I18nProvider>)
}

function TestLanguageButton() {
  const { toggleLocale } = useI18n()
  return <button type="button" onClick={toggleLocale}>中文</button>
}

describe('App device-dependent layout', () => {
  afterEach(cleanup)

  beforeEach(() => {
    mockedHands = {
      left: { ...initialHands.left },
      right: { ...initialHands.right },
    }
  })

  it('shows the empty state when neither hand is online', () => {
    renderApp()

    expect(screen.getByText('No hand connected')).toBeInTheDocument()
    expect(screen.getByTestId('hand-scene')).toHaveTextContent('')
  })

  it('shows only the left hand and selects its controls', async () => {
    mockedHands.left = online('left')
    renderApp()

    expect(screen.getByTestId('hand-scene')).toHaveTextContent('left')
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Left hand' })).toBeInTheDocument())
    await waitFor(() => expect(screen.getByRole('spinbutton', { name: 'J1 Little position' })).toHaveValue(800))
    expect(screen.queryByRole('button', { name: 'Right' })).not.toBeInTheDocument()
  })

  it('shows only the right hand and its controls', () => {
    mockedHands.right = online('right')
    renderApp()

    expect(screen.getByTestId('hand-scene')).toHaveTextContent('right')
    expect(screen.getByRole('heading', { name: 'Right hand' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Left' })).not.toBeInTheDocument()
  })

  it('shows both hand selectors and both models when both are online', () => {
    mockedHands.left = online('left')
    mockedHands.right = online('right')
    renderApp()

    expect(screen.getByTestId('hand-scene')).toHaveTextContent('left,right')
    expect(screen.getByRole('button', { name: 'Left' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Right' })).toBeInTheDocument()
  })

  it('loads tactile calibration once when online status is unchanged', async () => {
    mockedHands.right = online('right')
    const fetchMock = vi.fn(async () => new Response('null', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)
    const { rerender } = render(<App />)

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    mockedHands = {
      left: { ...mockedHands.left },
      right: { ...mockedHands.right, updated_at: 2 },
    }
    rerender(<App />)

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(fetchMock).toHaveBeenCalledTimes(1)
    vi.unstubAllGlobals()
  })

  it('does not reload tactile calibration during a device reconnect flap', async () => {
    mockedHands.right = online('right')
    const fetchMock = vi.fn(async () => new Response('null', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)
    const { rerender } = render(<App />)

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    mockedHands = {
      left: { ...mockedHands.left },
      right: { ...initialHands.right },
    }
    rerender(<App />)
    mockedHands = {
      left: { ...mockedHands.left },
      right: online('right'),
    }
    rerender(<App />)

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(fetchMock).toHaveBeenCalledTimes(1)
    vi.unstubAllGlobals()
  })

  it('exposes a resizable device inspector on desktop', () => {
    mockedHands.left = online('left')
    renderApp()

    const separator = screen.getByRole('separator', { name: 'Resize control panel' })
    expect(separator).toHaveAttribute('aria-valuemin', '320')
    expect(separator).toHaveAttribute('aria-valuemax', '520')
    expect(separator).toHaveAttribute('aria-valuenow', '380')
  })

  it('switches the active hand inspector to tactile telemetry', () => {
    mockedHands.left = online('left')
    renderApp()

    fireEvent.click(screen.getByRole('button', { name: 'Tactile' }))

    expect(screen.getByRole('heading', { name: 'Surface telemetry' })).toBeInTheDocument()
    expect(screen.getByText('PIEZO / 1062')).toBeInTheDocument()
  })

  it('shows the motion scene beside the 2D tactile atlas in combined mode', () => {
    mockedHands.left = online('left')
    renderApp()

    fireEvent.click(screen.getByRole('button', { name: 'Motion + Tactile' }))

    expect(screen.getByTestId('hand-scene')).toHaveAttribute('data-workspace-mode', 'motion')
    expect(screen.getByTestId('tactile-atlas')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Surface telemetry' })).toBeInTheDocument()
  })

  it('switches all representative workstation copy to Chinese while preserving identifiers', async () => {
    mockedHands.left = online('left')
    renderLocalizedApp()
    fireEvent.click(screen.getByRole('button', { name: '中文' }))

    expect(screen.getByText('灵巧机器人工作台')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '运动' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '左手' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '执行姿态' })).toBeInTheDocument()
    expect(screen.getByRole('spinbutton', { name: 'J1 小指位置' })).toBeInTheDocument()
    expect(screen.getByText('INSPIRE / 灵巧手控制工作台')).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('zh-CN')
  })
})
