import { describe, expect, it } from 'vitest'

import { gridLevelForDistance } from '../src/hand-viewer/AdaptiveGrid'

describe('adaptive grid levels', () => {
  it.each([
    [1.1, 'coarse', 0.02, 0.1],
    [0.85, 'standard', 0.01, 0.05],
    [0.6, 'standard', 0.01, 0.05],
    [0.42, 'fine', 0.005, 0.025],
    [0.3, 'fine', 0.005, 0.025],
    [0.24, 'micro', 0.0025, 0.0125],
    [0.18, 'micro', 0.0025, 0.0125],
  ] as const)(
    'uses the %s level at camera distance %s',
    (distance, name, cellSize, sectionSize) => {
      expect(gridLevelForDistance(distance)).toEqual({ name, cellSize, sectionSize })
    },
  )
})
