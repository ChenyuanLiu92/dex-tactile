import type { HandSide } from '../app/types'
import type { CalibrationObservation } from './spatialCalibration'

export const CALIBRATION_REGION_ORDER = ['little_tip_end','little_tip','little_pad','ring_tip_end','ring_tip','ring_pad','middle_tip_end','middle_tip','middle_pad','index_tip_end','index_tip','index_pad','thumb_tip_end','thumb_tip','thumb_middle','thumb_pad','palm'] as const

export type CalibrationStage = 'preflight' | 'overview' | 'waiting_contact' | 'sampling' | 'waiting_release' | 'review' | 'paused'

export interface PendingCapture {
  observedRow: number
  observedColumn: number
  peak: number
  active: number
  stableMs: number
}

export interface GuidedCalibrationSession {
  side: HandSide
  mode: 'full' | 'single'
  regionId: string
  regionIndex: number
  pointIndex: number
  stage: CalibrationStage
  observations: CalibrationObservation[]
  pendingSample: PendingCapture | null
  releaseStartedAt: number | null
  startedAt: number | null
  wrongRegionId: string | null
}

export function initialCalibrationSession(side: HandSide, regionId: string = CALIBRATION_REGION_ORDER[0], mode: 'full' | 'single' = 'full'): GuidedCalibrationSession {
  return { side, mode, regionId, regionIndex: Math.max(0, CALIBRATION_REGION_ORDER.indexOf(regionId as typeof CALIBRATION_REGION_ORDER[number])), pointIndex: 0, stage: 'waiting_contact', observations: [], pendingSample: null, releaseStartedAt: null, startedAt: null, wrongRegionId: null }
}

export function contactStep(session: GuidedCalibrationSession, observation: CalibrationObservation | null, now: number): GuidedCalibrationSession {
  if (session.stage === 'waiting_release') {
    if (observation) return { ...session, releaseStartedAt: null }
    const releaseStartedAt = session.releaseStartedAt ?? now
    if (now - releaseStartedAt < 300) return { ...session, releaseStartedAt }
    return { ...session, pointIndex: session.pointIndex + 1, stage: 'waiting_contact', observations: [], pendingSample: null, releaseStartedAt: null, startedAt: null }
  }
  if (!observation) return { ...session, stage: 'waiting_contact', observations: [], startedAt: null }
  const observations = [...session.observations, observation].slice(-6)
  const startedAt = session.startedAt ?? now
  if (observations.length < 6) return { ...session, stage: 'sampling', observations, startedAt }
  const peakMean = observations.reduce((sum, item) => sum + item.peak, 0) / observations.length
  const peakVariation = Math.max(...observations.map((item) => Math.abs(item.peak - peakMean))) / Math.max(1, peakMean)
  const first = observations[0]!
  const movement = Math.max(...observations.map((item) => Math.hypot(item.row - first.row, item.column - first.column)))
  if (peakVariation > 0.2 || movement > 0.75) return { ...session, stage: 'sampling', observations, startedAt }
  const average = (key: 'row' | 'column' | 'peak' | 'active') => observations.reduce((sum, item) => sum + item[key], 0) / observations.length
  return { ...session, stage: 'waiting_release', observations, pendingSample: { observedRow: average('row'), observedColumn: average('column'), peak: average('peak'), active: Math.round(average('active')), stableMs: now - startedAt }, releaseStartedAt: null, startedAt }
}
