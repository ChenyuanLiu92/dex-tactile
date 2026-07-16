import { describe, expect, it } from 'vitest'

import { appendHistory, summarizeFrame } from '../src/tactile/history'
import { baselineFromFrames } from '../src/tactile/calibration'
import type { TactileFrame } from '../src/app/types'

function frame(capturedAt: number, values: number[]): TactileFrame {
  return {
    type: 'tactile_frame',
    side: 'left',
    profile: 'piezoresistive_v1',
    sequence: capturedAt,
    captured_at: capturedAt,
    regions: [{ id: 'palm', rows: 1, columns: values.length, values, metrics: null }],
  }
}

describe('tactile history', () => {
  it('summarizes peak, mean and active taxels per region', () => {
    expect(summarizeFrame(frame(1, [0, 5, 10]), 4).regions.palm).toEqual({
      mean: 5,
      peak: 10,
      active: 2,
      total: 3,
    })
  })

  it('keeps only the latest ten seconds', () => {
    let history = appendHistory([], frame(1, [1]), 0)
    history = appendHistory(history, frame(10, [2]), 0)
    history = appendHistory(history, frame(12, [3]), 0)

    expect(history.map((sample) => sample.capturedAt)).toEqual([10, 12])
  })

  it('calculates a per-taxel median baseline across captured frames', () => {
    const baseline = baselineFromFrames([
      frame(1, [1, 20]),
      frame(2, [3, 10]),
      frame(3, [2, 30]),
    ])

    expect(baseline.palm).toEqual([2, 20])
  })
})
