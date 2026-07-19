import { describe, expect, it } from 'vitest'

import {
  EMPTY_CONTROL,
  EMPTY_SNAPSHOT,
  normalizeTrackingSnapshot,
} from './api'

describe('normalizeTrackingSnapshot', () => {
  it('ignores messages belonging to the digital-twin websocket protocol', () => {
    expect(normalizeTrackingSnapshot({ type: 'snapshot', hands: {} })).toBeNull()
  })

  it('supplies safe nested defaults for a compatible partial tracking message', () => {
    const snapshot = normalizeTrackingSnapshot({
      type: 'tracking',
      status: 'TRACKING',
      sequence: 4,
    })

    expect(snapshot).toMatchObject({
      status: 'TRACKING',
      sequence: 4,
      control: EMPTY_CONTROL,
      operator_profile: EMPTY_SNAPSHOT.operator_profile,
      detected_hands: [],
    })
  })

  it('retains the last valid enum values when a message contains unknown states', () => {
    const snapshot = normalizeTrackingSnapshot({
      type: 'tracking',
      status: 'BROKEN',
      control: { state: 'UNKNOWN' },
    }, { ...EMPTY_SNAPSHOT, status: 'LOST' })

    expect(snapshot?.status).toBe('LOST')
    expect(snapshot?.control.state).toBe('DISCONNECTED')
  })
})
