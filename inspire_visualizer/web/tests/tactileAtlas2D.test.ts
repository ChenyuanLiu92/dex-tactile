import { describe, expect, it } from 'vitest'

import {
  atlasRegionGroups,
  nearestPositionedTaxel,
  positionedTaxels,
  taxelAtPoint,
} from '../src/tactile/TactileAtlas2D'

describe('2D tactile atlas', () => {
  it('organizes every RH56DFTP region and all 1062 taxels', () => {
    const groups = atlasRegionGroups('right', 'piezoresistive_v1')
    const patches = groups.flatMap((group) => group.patches)

    expect(groups.map((group) => group.id)).toEqual([
      'little', 'ring', 'middle', 'index', 'thumb', 'palm',
    ])
    expect(patches).toHaveLength(17)
    expect(new Set(patches.map((patch) => patch.id)).size).toBe(17)
    expect(patches.reduce((total, patch) => total + patch.rows * patch.columns, 0)).toBe(1062)
  })

  it('maps pointer coordinates to the correct taxel and clamps the edges', () => {
    expect(taxelAtPoint(25, 25, 100, 120, 12, 8)).toEqual({ row: 2, column: 2 })
    expect(taxelAtPoint(100, 120, 100, 120, 12, 8)).toEqual({ row: 11, column: 7 })
    expect(taxelAtPoint(-5, -2, 100, 120, 12, 8)).toEqual({ row: 0, column: 0 })
  })

  it('applies the saved spatial calibration to 2D taxel placement and hit testing', () => {
    const patch = atlasRegionGroups('right', 'piezoresistive_v1')
      .flatMap((group) => group.patches)
      .find((item) => item.id === 'index_tip')!
    const [u0, u1] = patch.surface.uRange
    const [v0, v1] = patch.surface.vRange
    const positions = positionedTaxels(2, 2, patch, {
      u: [u0, 0, u1 - u0, 0],
      v: [v0, v1 - v0, 0, 0],
    })

    expect(positions).toEqual([
      { row: 0, column: 0, u: 0, v: 0 },
      { row: 0, column: 1, u: 1, v: 0 },
      { row: 1, column: 0, u: 0, v: 1 },
      { row: 1, column: 1, u: 1, v: 1 },
    ])
    expect(nearestPositionedTaxel(0.9, 0.1, positions)).toMatchObject({ row: 0, column: 1 })
  })
})
