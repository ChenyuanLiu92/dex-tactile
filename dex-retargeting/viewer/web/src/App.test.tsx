import { render, screen } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'

import { App } from './App'
import type { TrackingSnapshot } from './api'

vi.mock('./camera/CameraPanel', () => ({ CameraPanel: () => <div>camera</div> }))
vi.mock('./scene/RobotScene', () => ({ RobotScene: () => <div>robot</div> }))

const snapshot: TrackingSnapshot = {
  type: 'tracking',
  status: 'TRACKING',
  sequence: 8,
  captured_at: 0,
  published_at: 0,
  capture_fps: 29.8,
  tracking_fps: 27.4,
  latency_ms: 31.2,
  handedness: 'Right',
  confidence: 0.96,
  landmarks_2d: Array.from({ length: 21 }, () => [0.5, 0.5]),
  landmarks_3d: Array.from({ length: 21 }, () => [0, 0, 0]),
  joints: {
    index_proximal_joint: 0.1,
    index_intermediate_joint: 0.2,
    middle_proximal_joint: 0.3,
    middle_intermediate_joint: 0.4,
    pinky_proximal_joint: 0.5,
    pinky_intermediate_joint: 0.6,
    ring_proximal_joint: 0.7,
    ring_intermediate_joint: 0.8,
    thumb_proximal_yaw_joint: 0.9,
    thumb_proximal_pitch_joint: 0.1,
    thumb_intermediate_joint: 0.2,
    thumb_distal_joint: 0.3,
  },
  actuators: [100, 200, 300, 400, 500, 600],
  contact: null,
  error: null,
  dry_run: true,
  modbus_output: false,
  control: {
    state: 'DISARMED',
    connected: true,
    host: '192.0.2.10',
    port: 6000,
    actual: [900, 800, 700, 600, 500, 400],
    targets: [100, 200, 300, 400, 500, 600],
    commanded: [900, 800, 700, 600, 500, 400],
    speeds: null,
    last_write_at: null,
    error: null,
    preset: null,
    tracking_hold: false,
    tracking_loss_ms: null,
    modbus_output: false,
    software_hold_only: true,
  },
}

describe('App', () => {
  test('shows permanent safety state and all retargeting channels', () => {
    render(<App initialSnapshot={snapshot} connect={false} />)
    expect(screen.getAllByText('DISARMED').length).toBeGreaterThan(0)
    expect(screen.getByText('SOFTWARE HOLD ONLY')).toBeInTheDocument()
    expect(screen.getAllByText('TRACKING')).toHaveLength(2)
    expect(screen.getAllByTestId('joint-row')).toHaveLength(12)
    expect(screen.getAllByTestId('actuator-row')).toHaveLength(6)
  })
})
