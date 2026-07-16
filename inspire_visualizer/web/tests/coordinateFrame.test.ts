import { describe, expect, it } from 'vitest'

import {
  FRAME_OPTIONS,
  showsActuatorFrames,
  showsBaseFrames,
  showsWorldFrame,
} from '../src/hand-viewer/CoordinateFrame'

describe('coordinate frame modes', () => {
  it('offers a dedicated actuator-reference mode', () => {
    expect(FRAME_OPTIONS).toContainEqual(expect.objectContaining({ value: 'actuators', label: 'Drive joint axes' }))
  })

  it('shows actuator frames in all and actuator-only modes', () => {
    expect(showsActuatorFrames('all')).toBe(true)
    expect(showsActuatorFrames('actuators')).toBe(true)
    expect(showsActuatorFrames('base')).toBe(false)
    expect(showsActuatorFrames('off')).toBe(false)
  })

  it('keeps world and base visibility independent from actuator-only mode', () => {
    expect(showsWorldFrame('actuators')).toBe(false)
    expect(showsBaseFrames('actuators')).toBe(false)
  })
})
