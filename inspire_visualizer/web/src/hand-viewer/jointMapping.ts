import type { ChannelValues, HandSide } from '../app/types'

type MotionRange = readonly [opened: number, closed: number]

export interface ActuatorReference {
  channel: `J${1 | 2 | 3 | 4 | 5 | 6}`
  name: string
  joint: string
}

export const ACTUATOR_REFERENCES: Record<HandSide, readonly ActuatorReference[]> = {
  left: [
    { channel: 'J1', name: 'Little', joint: 'left_little_1_joint' },
    { channel: 'J2', name: 'Ring', joint: 'left_ring_1_joint' },
    { channel: 'J3', name: 'Middle', joint: 'left_middle_1_joint' },
    { channel: 'J4', name: 'Index', joint: 'left_index_1_joint' },
    { channel: 'J5', name: 'Thumb bend', joint: 'left_thumb_1_joint' },
    { channel: 'J6', name: 'Thumb rotation', joint: 'left_thumb_swing_joint' },
  ],
  right: [
    { channel: 'J1', name: 'Little', joint: 'right_little_1_joint' },
    { channel: 'J2', name: 'Ring', joint: 'right_ring_1_joint' },
    { channel: 'J3', name: 'Middle', joint: 'right_middle_1_joint' },
    { channel: 'J4', name: 'Index', joint: 'right_index_1_joint' },
    { channel: 'J5', name: 'Thumb bend', joint: 'right_thumb_2_joint' },
    { channel: 'J6', name: 'Thumb rotation', joint: 'right_thumb_1_joint' },
  ],
}

const MOTION_RANGES: Record<HandSide, readonly MotionRange[]> = {
  left: [
    [0, 1.6],
    [0, 1.6],
    [0, 1.6],
    [0, 1.6],
    [0, -0.95],
    [0, 1.7],
  ],
  right: [
    [0, 1.6],
    [0, 1.6],
    [0, 1.6],
    [0, 1.6],
    [0, 0.75],
    [0, 1.7],
  ],
}

export function mapDeviceAngles(side: HandSide, values: ChannelValues): Record<string, number> {
  return Object.fromEntries(
    MOTION_RANGES[side].map(([opened, closed], index) => {
      const openness = values[index] / 1000
      return [ACTUATOR_REFERENCES[side][index].joint, closed + openness * (opened - closed)]
    }),
  )
}
