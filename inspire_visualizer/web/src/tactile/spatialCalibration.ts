import type { TactileFrame, TactileRegionFrame } from '../app/types'
import type { TactilePatchLayout } from './layout'

export const CALIBRATION_POINTS = ['top_left', 'top_right', 'bottom_right', 'bottom_left', 'center'] as const
export type CalibrationPoint = (typeof CALIBRATION_POINTS)[number]

export interface CalibrationSample {
  point: CalibrationPoint
  targetUv: [number, number]
  observedRow: number
  observedColumn: number
  peak: number
  active: number
  stableMs: number
  capturedAt: number
}

export interface BilinearTransform {
  u: [number, number, number, number]
  v: [number, number, number, number]
}

export interface RegionCalibration {
  regionId: string
  status: 'incomplete' | 'good' | 'review' | 'poor'
  samples: CalibrationSample[]
  transform?: BilinearTransform
  residual?: number
  applied: boolean
  sensorRows?: number
  sensorColumns?: number
}

export interface CalibrationObservation {
  row: number
  column: number
  peak: number
  active: number
  totalWeight: number
}

export function targetUvForPoint(patch: TactilePatchLayout, point: CalibrationPoint): [number, number] {
  const inset = 0.12
  const u = point === 'top_left' || point === 'bottom_left' ? inset : point === 'top_right' || point === 'bottom_right' ? 1 - inset : 0.5
  const v = point === 'top_left' || point === 'top_right' ? inset : point === 'bottom_left' || point === 'bottom_right' ? 1 - inset : 0.5
  const [u0, u1] = patch.surface.uRange
  const [v0, v1] = patch.surface.vRange
  return [u0 + (u1 - u0) * u, v0 + (v1 - v0) * v]
}

export function weightedCentroid(
  region: TactileRegionFrame,
  baseline: number[] | undefined,
  threshold: number | number[],
): CalibrationObservation | null {
  let rowWeight = 0
  let columnWeight = 0
  let totalWeight = 0
  let peak = 0
  let active = 0
  region.values.forEach((value, index) => {
    const delta = value - (baseline?.[index] ?? 0)
    const limit = typeof threshold === 'number' ? threshold : threshold[index] ?? 0
    const weight = Math.max(0, delta - limit)
    if (weight <= 0) return
    const row = Math.floor(index / region.columns)
    const column = index % region.columns
    rowWeight += row * weight
    columnWeight += column * weight
    totalWeight += weight
    peak = Math.max(peak, delta)
    active += 1
  })
  if (totalWeight <= 0) return null
  return { row: rowWeight / totalWeight, column: columnWeight / totalWeight, peak, active, totalWeight }
}

export function stableContact(observations: CalibrationObservation[], required = 6): boolean {
  if (observations.length < required) return false
  const recent = observations.slice(-required)
  const peakMean = recent.reduce((sum, item) => sum + item.peak, 0) / recent.length
  const peakVariation = Math.max(...recent.map((item) => Math.abs(item.peak - peakMean))) / Math.max(1, peakMean)
  const first = recent[0]!
  const centroidMovement = Math.max(...recent.map((item) => Math.hypot(item.row - first.row, item.column - first.column)))
  return peakVariation <= 0.2 && centroidMovement <= 0.75
}

function solve(matrix: number[][], vector: number[]): number[] {
  const augmented = matrix.map((row, index) => [...row, vector[index]])
  for (let column = 0; column < 4; column += 1) {
    let pivot = column
    for (let row = column + 1; row < 4; row += 1) if (Math.abs(augmented[row]![column]!) > Math.abs(augmented[pivot]![column]!)) pivot = row
    ;[augmented[column], augmented[pivot]] = [augmented[pivot]!, augmented[column]!]
    const divisor = augmented[column]![column]!
    if (Math.abs(divisor) < 1e-8) throw new Error('Calibration samples are degenerate')
    for (let item = column; item <= 4; item += 1) augmented[column]![item] /= divisor
    for (let row = 0; row < 4; row += 1) {
      if (row === column) continue
      const factor = augmented[row]![column]!
      for (let item = column; item <= 4; item += 1) augmented[row]![item] -= factor * augmented[column]![item]!
    }
  }
  return augmented.map((row) => row[4]!)
}

export function fitBilinearTransform(samples: CalibrationSample[], rows?: number, columns?: number): BilinearTransform {
  if (samples.length < 4) throw new Error('At least four calibration samples are required')
  const matrix = Array.from({ length: 4 }, () => Array(4).fill(0) as number[])
  const uVector = [0, 0, 0, 0]
  const vVector = [0, 0, 0, 0]
  const maxRow = Math.max(1, (rows ?? 1) - 1, ...samples.map((sample) => sample.observedRow))
  const maxColumn = Math.max(1, (columns ?? 1) - 1, ...samples.map((sample) => sample.observedColumn))
  for (const sample of samples) {
    const r = sample.observedRow / maxRow
    const c = sample.observedColumn / maxColumn
    const basis = [1, r, c, r * c]
    for (let row = 0; row < 4; row += 1) for (let column = 0; column < 4; column += 1) matrix[row]![column] += basis[row]! * basis[column]!
    for (let row = 0; row < 4; row += 1) { uVector[row] += basis[row]! * sample.targetUv[0]; vVector[row] += basis[row]! * sample.targetUv[1] }
  }
  return { u: solve(matrix, uVector) as BilinearTransform['u'], v: solve(matrix, vVector) as BilinearTransform['v'] }
}

export function applyBilinearTransform(transform: BilinearTransform, row: number, column: number, rows: number, columns: number): [number, number] {
  const r = row / Math.max(1, rows - 1)
  const c = column / Math.max(1, columns - 1)
  const basis = [1, r, c, r * c]
  return [transform.u.reduce((sum, value, index) => sum + value * basis[index]!, 0), transform.v.reduce((sum, value, index) => sum + value * basis[index]!, 0)]
}

export function classifyCalibration(samples: CalibrationSample[], transform: BilinearTransform, rows?: number, columns?: number): RegionCalibration['status'] {
  if (samples.length < 4) return 'poor'
  const residual = Math.max(...samples.map((sample) => {
    const uv = applyBilinearTransform(transform, sample.observedRow, sample.observedColumn, rows ?? Math.max(2, ...samples.map((item) => item.observedRow + 1)), columns ?? Math.max(2, ...samples.map((item) => item.observedColumn + 1)))
    return Math.hypot(uv[0] - sample.targetUv[0], uv[1] - sample.targetUv[1])
  }))
  if (samples.length >= 5 && residual <= 0.05) return 'good'
  if (samples.length >= 4 && residual <= 0.12) return 'review'
  return 'poor'
}

export function latestRegionFrame(frame: TactileFrame | null, regionId: string): TactileRegionFrame | null {
  return frame?.regions.find((region) => region.id === regionId) ?? null
}
