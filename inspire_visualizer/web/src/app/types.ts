export type HandSide = 'left' | 'right'
export type ConnectionState = 'offline' | 'connecting' | 'online'
export type ChannelValues = [number, number, number, number, number, number]
export type TactileProfile = 'disabled' | 'piezoresistive_v1' | 'capacitive_v1'
export type TactileState = 'off' | 'waiting' | 'live' | 'degraded'

export interface TactileStatus {
  profile: TactileProfile
  state: TactileState
  target_hz: number
  sample_hz: number
  updated_at: number | null
  error: string | null
}

export interface TactileRegionFrame {
  id: string
  rows: number
  columns: number
  values: number[]
  metrics: Record<string, number> | null
}

export interface TactileFrame {
  type: 'tactile_frame'
  side: HandSide
  profile: Exclude<TactileProfile, 'disabled'>
  sequence: number
  captured_at: number
  regions: TactileRegionFrame[]
}

export type TactileFrames = Record<HandSide, TactileFrame | null>

export interface HandSnapshot {
  side: HandSide
  connection: ConnectionState
  actual_angles: ChannelValues | null
  armed: boolean
  updated_at: number | null
  error: string | null
  tactile: TactileStatus
}

export type HandsSnapshot = Record<HandSide, HandSnapshot>

export interface EndpointConfig {
  enabled: boolean
  host: string
  port: number
  tactile_profile: TactileProfile
  tactile_target_hz: number
}

export interface HandsConfig {
  left: EndpointConfig
  right: EndpointConfig
}

export const CHANNELS = [
  { key: 'little', label: 'Little' },
  { key: 'ring', label: 'Ring' },
  { key: 'middle', label: 'Middle' },
  { key: 'index', label: 'Index' },
  { key: 'thumb_bend', label: 'Thumb bend' },
  { key: 'thumb_rotate', label: 'Thumb rotation' },
] as const

export function onlineHands(hands: HandsSnapshot): HandSide[] {
  return (['left', 'right'] as const).filter(
    (side) => hands[side].connection === 'online' && hands[side].actual_angles !== null,
  )
}
