import type { HandSide } from '../app/types'
import type { RegionCalibration } from './spatialCalibration'

export interface TactileCalibrationDocument {
  version: 1
  model: 'RH56DFTP'
  side: HandSide
  host: string
  port: number
  profile: 'piezoresistive_v1'
  regions: Record<string, RegionCalibration>
  drafts?: Record<string, RegionCalibration>
  updated_at: string
}

export async function loadTactileCalibration(side: HandSide): Promise<TactileCalibrationDocument | null> {
  const response = await fetch(`/api/tactile-calibration/${side}`)
  if (!response.ok) throw new Error(`Unable to load ${side} tactile calibration`)
  return response.json() as Promise<TactileCalibrationDocument | null>
}

export async function saveTactileCalibration(document: TactileCalibrationDocument): Promise<TactileCalibrationDocument> {
  const response = await fetch(`/api/tactile-calibration/${document.side}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(document),
  })
  if (!response.ok) throw new Error('Unable to save tactile calibration')
  return response.json() as Promise<TactileCalibrationDocument>
}
