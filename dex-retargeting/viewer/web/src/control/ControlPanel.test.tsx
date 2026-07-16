import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'

import type { ControlSnapshot } from '../api'
import { ControlPanel } from './ControlPanel'

const disarmed: ControlSnapshot = {
  state: 'DISARMED',
  connected: true,
  host: '192.0.2.10',
  port: 6000,
  actual: [900, 800, 700, 600, 500, 400],
  targets: [850, 750, 650, 550, 450, 350],
  commanded: [900, 800, 700, 600, 500, 400],
  speeds: null,
  last_write_at: null,
  error: null,
  preset: null,
  tracking_hold: false,
  tracking_loss_ms: null,
  modbus_output: false,
  software_hold_only: true,
}

test('ARM is disabled without right-hand tracking', () => {
  render(<ControlPanel control={disarmed} trackingStatus="SEARCHING" request={vi.fn()} />)
  expect(screen.getByRole('button', { name: 'ARM' })).toBeDisabled()
})

test('ARM confirmation shows measured and vision positions before request', async () => {
  const request = vi.fn().mockResolvedValue(disarmed)
  render(<ControlPanel control={disarmed} trackingStatus="TRACKING" request={request} />)

  fireEvent.click(screen.getByRole('button', { name: 'ARM' }))
  expect(screen.getByRole('dialog')).toHaveTextContent('192.0.2.10:6000')
  expect(screen.getByRole('dialog')).toHaveTextContent('900 800 700 600 500 400')
  expect(screen.getByRole('dialog')).toHaveTextContent('850 750 650 550 450 350')
  fireEvent.click(screen.getByRole('button', { name: 'Confirm ARM' }))

  await waitFor(() => expect(request).toHaveBeenCalledWith('arm'))
})

describe('guarded recovery actions', () => {
  test('armed state exposes DISARM and immediate E-STOP', async () => {
    const request = vi.fn().mockResolvedValue(disarmed)
    render(
      <ControlPanel
        control={{ ...disarmed, state: 'ARMED', modbus_output: true }}
        trackingStatus="TRACKING"
        request={request}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'E-STOP' }))
    await waitFor(() => expect(request).toHaveBeenCalledWith('estop'))
    expect(screen.getByRole('button', { name: 'DISARM' })).toBeInTheDocument()
  })

  test('brief tracking loss is shown as a recovery hold', () => {
    render(
      <ControlPanel
        control={{
          ...disarmed,
          state: 'ARMED',
          tracking_hold: true,
          tracking_loss_ms: 120,
          modbus_output: true,
        }}
        trackingStatus="LOST"
        request={vi.fn()}
      />,
    )
    expect(screen.getByText('RECOVERY HOLD')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'DISARM' })).toBeInTheDocument()
  })

  test('estopped state exposes RESET but no ARM', () => {
    render(
      <ControlPanel
        control={{ ...disarmed, state: 'ESTOPPED' }}
        trackingStatus="TRACKING"
        request={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: 'RESET' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'ARM' })).not.toBeInTheDocument()
  })

  test('fault state exposes RECONNECT and error', () => {
    render(
      <ControlPanel
        control={{ ...disarmed, state: 'FAULT', error: 'write failed' }}
        trackingStatus="TRACKING"
        request={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: 'RECONNECT' })).toBeInTheDocument()
    expect(screen.getByText('write failed')).toBeInTheDocument()
  })
})
