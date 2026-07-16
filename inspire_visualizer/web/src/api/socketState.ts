import type {
  ChannelValues,
  HandSnapshot,
  HandSide,
  HandsSnapshot,
  TactileFrame,
  TactileFrames,
} from '../app/types'

export type ServerMessage =
  | { type: 'snapshot'; hands: Partial<Record<HandSide, Partial<HandSnapshot>>> }
  | { type: 'armed_state'; side: HandSide; armed: boolean }
  | {
      type: 'command_result'
      side: HandSide
      command_id: string
      accepted: boolean
      actual_angles: ChannelValues
    }
  | { type: 'error'; code: string; message: string }
  | TactileFrame

const OFF_TACTILE = {
  profile: 'disabled' as const,
  state: 'off' as const,
  target_hz: 20,
  sample_hz: 0,
  updated_at: null,
  error: null,
}

export const initialHands: HandsSnapshot = {
  left: {
    side: 'left',
    connection: 'offline',
    actual_angles: null,
    armed: false,
    updated_at: null,
    error: null,
    tactile: { ...OFF_TACTILE },
  },
  right: {
    side: 'right',
    connection: 'offline',
    actual_angles: null,
    armed: false,
    updated_at: null,
    error: null,
    tactile: { ...OFF_TACTILE },
  },
}

export const initialTactileFrames: TactileFrames = { left: null, right: null }

function normalizeHandSnapshot(
  side: HandSide,
  snapshot: Partial<HandSnapshot> | undefined,
): HandSnapshot {
  const fallback = initialHands[side]
  return {
    ...fallback,
    ...snapshot,
    side,
    tactile: {
      ...fallback.tactile,
      ...snapshot?.tactile,
    },
  }
}

export function reduceServerMessage(
  state: HandsSnapshot,
  message: ServerMessage,
): HandsSnapshot {
  if (message.type === 'snapshot') {
    return {
      left: normalizeHandSnapshot('left', message.hands.left),
      right: normalizeHandSnapshot('right', message.hands.right),
    }
  }
  if (message.type === 'armed_state') {
    return {
      ...state,
      [message.side]: { ...state[message.side], armed: message.armed },
    }
  }
  if (message.type === 'command_result') {
    return {
      ...state,
      [message.side]: {
        ...state[message.side],
        actual_angles: message.actual_angles,
      },
    }
  }
  return state
}

export function reduceTactileFrame(
  state: TactileFrames,
  message: TactileFrame,
): TactileFrames {
  const current = state[message.side]
  if (current && current.sequence >= message.sequence) return state
  return { ...state, [message.side]: message }
}

export function disconnectedHands(): HandsSnapshot {
  return {
    left: { ...initialHands.left, error: 'WebSocket disconnected' },
    right: { ...initialHands.right, error: 'WebSocket disconnected' },
  }
}
