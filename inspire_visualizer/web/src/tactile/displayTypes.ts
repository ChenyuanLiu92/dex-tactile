import type { HandSide } from '../app/types'

export type HeatStyle = 'raw' | 'smooth'

export interface TactileSelection {
  side: HandSide
  regionId: string
  row: number
  column: number
  value: number
}
