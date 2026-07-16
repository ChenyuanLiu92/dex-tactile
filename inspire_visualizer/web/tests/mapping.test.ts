import { describe, expect, it } from 'vitest'

import { ACTUATOR_REFERENCES, mapDeviceAngles } from '../src/hand-viewer/jointMapping'
import { onlineHands } from '../src/app/types'

describe('mapDeviceAngles', () => {
  it('maps all six device channels to their controlled URDF joint axes', () => {
    expect(ACTUATOR_REFERENCES.left).toEqual([
      { channel: 'J1', name: 'Little', joint: 'left_little_1_joint' },
      { channel: 'J2', name: 'Ring', joint: 'left_ring_1_joint' },
      { channel: 'J3', name: 'Middle', joint: 'left_middle_1_joint' },
      { channel: 'J4', name: 'Index', joint: 'left_index_1_joint' },
      { channel: 'J5', name: 'Thumb bend', joint: 'left_thumb_1_joint' },
      { channel: 'J6', name: 'Thumb rotation', joint: 'left_thumb_swing_joint' },
    ])
    expect(ACTUATOR_REFERENCES.right.map(({ channel, joint }) => ({ channel, joint }))).toEqual([
      { channel: 'J1', joint: 'right_little_1_joint' },
      { channel: 'J2', joint: 'right_ring_1_joint' },
      { channel: 'J3', joint: 'right_middle_1_joint' },
      { channel: 'J4', joint: 'right_index_1_joint' },
      { channel: 'J5', joint: 'right_thumb_2_joint' },
      { channel: 'J6', joint: 'right_thumb_1_joint' },
    ])
  })

  it('maps right-hand device values from 1000 open to 0 closed', () => {
    expect(mapDeviceAngles('right', [1000, 1000, 1000, 1000, 1000, 1000])).toEqual({
      right_little_1_joint: 0,
      right_ring_1_joint: 0,
      right_middle_1_joint: 0,
      right_index_1_joint: 0,
      right_thumb_2_joint: 0,
      right_thumb_1_joint: 0,
    })
    expect(mapDeviceAngles('right', [0, 0, 0, 0, 0, 0])).toEqual({
      right_little_1_joint: 1.6,
      right_ring_1_joint: 1.6,
      right_middle_1_joint: 1.6,
      right_index_1_joint: 1.6,
      right_thumb_2_joint: 0.75,
      right_thumb_1_joint: 1.7,
    })
  })

  it('maps the left thumb bend through its negative URDF range', () => {
    const values = mapDeviceAngles('left', [500, 500, 500, 500, 500, 500])

    expect(values.left_thumb_1_joint).toBeCloseTo(-0.475)
    expect(values.left_thumb_swing_joint).toBeCloseTo(0.85)
  })
})

describe('onlineHands', () => {
  it('returns only sides with a valid online state', () => {
    expect(
      onlineHands({
        left: {
          side: 'left',
          connection: 'online',
          actual_angles: [1000, 1000, 1000, 1000, 1000, 1000],
          armed: false,
        updated_at: 1,
        error: null,
        tactile: {
          profile: 'piezoresistive_v1',
          state: 'live',
          target_hz: 20,
          sample_hz: 20,
          updated_at: 1,
          error: null,
        },
        },
        right: {
          side: 'right',
          connection: 'offline',
          actual_angles: null,
          armed: false,
        updated_at: null,
        error: 'offline',
        tactile: {
          profile: 'disabled',
          state: 'off',
          target_hz: 20,
          sample_hz: 0,
          updated_at: null,
          error: null,
        },
        },
      }),
    ).toEqual(['left'])
  })
})
