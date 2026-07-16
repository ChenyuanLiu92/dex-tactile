import { describe, expect, it } from 'vitest'

import { atlasRegionGroups, taxelAtPoint } from '../src/tactile/TactileAtlas2D'

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
})
