import { describe, expect, it } from 'vitest'

import { applyBilinearTransform, fitBilinearTransform, stableContact, weightedCentroid } from '../src/tactile/spatialCalibration'

describe('tactile spatial calibration', () => {
  it('finds the weighted sensor centroid', () => {
    const result = weightedCentroid({ id: 'index_tip', rows: 2, columns: 2, values: [0, 10, 20, 0], metrics: {} }, [0, 0, 0, 0], 1)
    expect(result?.row).toBeCloseTo(19 / 28)
    expect(result?.column).toBeCloseTo(9 / 28)
  })

  it('accepts six stable observations and rejects drift', () => {
    const stable = Array.from({ length: 6 }, () => ({ row: 1, column: 2, peak: 100, active: 2, totalWeight: 100 }))
    expect(stableContact(stable)).toBe(true)
    expect(stableContact(stable.map((item, index) => ({ ...item, row: index })))).toBe(false)
  })

  it('fits and evaluates a bilinear row-column transform', () => {
    const samples = [
      { point: 'top_left' as const, targetUv: [0.1, 0.2] as [number, number], observedRow: 0, observedColumn: 0, peak: 100, active: 1, stableMs: 400, capturedAt: 0 },
      { point: 'top_right' as const, targetUv: [0.9, 0.2] as [number, number], observedRow: 0, observedColumn: 7, peak: 100, active: 1, stableMs: 400, capturedAt: 0 },
      { point: 'bottom_left' as const, targetUv: [0.1, 0.8] as [number, number], observedRow: 11, observedColumn: 0, peak: 100, active: 1, stableMs: 400, capturedAt: 0 },
      { point: 'bottom_right' as const, targetUv: [0.9, 0.8] as [number, number], observedRow: 11, observedColumn: 7, peak: 100, active: 1, stableMs: 400, capturedAt: 0 },
    ]
    const transform = fitBilinearTransform(samples, 12, 8)
    expect(applyBilinearTransform(transform, 11, 7, 12, 8)[0]).toBeCloseTo(0.9, 2)
  })
})
