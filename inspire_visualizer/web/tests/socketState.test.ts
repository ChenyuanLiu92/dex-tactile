import { describe, expect, it } from 'vitest'

import {
  initialHands,
  initialTactileFrames,
  reduceServerMessage,
  reduceTactileFrame,
} from '../src/api/socketState'

describe('reduceServerMessage', () => {
  it('replaces device state from a server snapshot', () => {
    const state = reduceServerMessage(initialHands, {
      type: 'snapshot',
      hands: {
        left: {
          side: 'left',
          connection: 'online',
          actual_angles: [1000, 900, 800, 700, 600, 500],
          armed: false,
          updated_at: 10,
          error: null,
          tactile: initialHands.left.tactile,
        },
        right: initialHands.right,
      },
    })

    expect(state.left.connection).toBe('online')
    expect(state.left.actual_angles).toEqual([1000, 900, 800, 700, 600, 500])
  })

  it('updates arming and command readback for one side only', () => {
    const armed = reduceServerMessage(initialHands, {
      type: 'armed_state',
      side: 'right',
      armed: true,
    })
    const commanded = reduceServerMessage(armed, {
      type: 'command_result',
      side: 'right',
      command_id: 'pose-1',
      accepted: true,
      actual_angles: [500, 500, 500, 500, 500, 500],
    })

    expect(commanded.right.armed).toBe(true)
    expect(commanded.right.actual_angles).toEqual([500, 500, 500, 500, 500, 500])
    expect(commanded.left).toEqual(initialHands.left)
  })

  it('normalizes a legacy motion-only snapshot without tactile status', () => {
    const state = reduceServerMessage(initialHands, {
      type: 'snapshot',
      hands: {
        left: {
          side: 'left',
          connection: 'online',
          actual_angles: [800, 700, 600, 500, 400, 300],
          armed: false,
          updated_at: 20,
          error: null,
        },
      },
    })

    expect(state.left.connection).toBe('online')
    expect(state.left.tactile).toEqual({
      profile: 'disabled',
      state: 'off',
      target_hz: 20,
      sample_hz: 0,
      updated_at: null,
      error: null,
    })
    expect(state.right).toEqual(initialHands.right)
  })

  it('keeps the latest complete tactile frame for each hand', () => {
    const frame = {
      type: 'tactile_frame' as const,
      side: 'left' as const,
      profile: 'piezoresistive_v1' as const,
      sequence: 4,
      captured_at: 12,
      regions: [{ id: 'palm', rows: 1, columns: 2, values: [10, 20], metrics: null }],
    }

    const state = reduceTactileFrame(initialTactileFrames, frame)

    expect(state.left).toEqual(frame)
    expect(state.right).toBeNull()
  })
})
