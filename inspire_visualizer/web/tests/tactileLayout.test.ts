import { describe, expect, it } from 'vitest'

import { tactilePatches } from '../src/tactile/layout'

describe('tactile surface layout', () => {
  it.each(['left', 'right'] as const)('maps all 1062 piezoresistive taxels for %s hand', (side) => {
    const patches = tactilePatches(side, 'piezoresistive_v1')

    expect(patches).toHaveLength(17)
    expect(patches.reduce((total, patch) => total + patch.rows * patch.columns, 0)).toBe(1062)
    expect(new Set(patches.map((patch) => patch.id)).size).toBe(17)
    expect(patches.every((patch) => patch.link.startsWith(side) || patch.link === 'base_link')).toBe(true)
    expect(patches.every((patch) => new Set([
      patch.surface.uAxis,
      patch.surface.vAxis,
      patch.surface.normalAxis,
    ]).size === 3)).toBe(true)
    expect(patches.every((patch) => patch.surface.margin > 0)).toBe(true)
    expect(patches.every((patch) => [
      ...patch.surface.uRange,
      ...patch.surface.vRange,
    ].every((value) => value >= 0 && value <= 1))).toBe(true)

    const thumbPad = patches.find((patch) => patch.id === 'thumb_pad')
    expect(thumbPad?.link).toBe(`${side}_thumb_${side === 'left' ? 1 : 2}`)
    const palm = patches.find((patch) => patch.id === 'palm')
    expect(Math.abs((palm?.surface.vRange[0] ?? 0) - (palm?.surface.vRange[1] ?? 0)))
      .toBeGreaterThanOrEqual(0.65)

    const curvedLowResolutionPatches = patches.filter(
      (patch) => patch.id.endsWith('_tip_end') || patch.id === 'thumb_middle',
    )
    expect(curvedLowResolutionPatches.every(
      (patch) => (patch.surfaceRows ?? patch.rows) >= patch.rows * 2
        && (patch.surfaceColumns ?? patch.columns) >= patch.columns * 2,
    )).toBe(true)
    expect(patches.every(
      (patch) => (patch.surfaceRows ?? patch.rows) >= patch.rows
        && (patch.surfaceColumns ?? patch.columns) >= patch.columns,
    )).toBe(true)
    const projectedVertexBudget = patches.reduce(
      (total, patch) => total
        + ((patch.surfaceRows ?? patch.rows) + 1)
        * ((patch.surfaceColumns ?? patch.columns) + 1),
      0,
    )
    expect(projectedVertexBudget).toBeLessThanOrEqual(2000)
  })

  it('maps capacitive data to five fingertip surfaces', () => {
    const patches = tactilePatches('left', 'capacitive_v1')

    expect(patches.map((patch) => patch.id)).toEqual([
      'little_tip',
      'ring_tip',
      'middle_tip',
      'index_tip',
      'thumb_tip',
    ])
    expect(patches.every((patch) => patch.rows === 1 && patch.columns === 8)).toBe(true)
  })

  it.each(['left', 'right'] as const)('places %s-hand tip-end arrays on the palmar surface above the tip arrays', (side) => {
    const patches = tactilePatches(side, 'piezoresistive_v1')
    for (const finger of ['little', 'ring', 'middle', 'index', 'thumb']) {
      const tipEnd = patches.find((patch) => patch.id === `${finger}_tip_end`)!
      const tip = patches.find((patch) => patch.id === `${finger}_tip`)!
      expect.soft(tipEnd.surface.normalAxis, `${finger} normal axis`).toBe(tip.surface.normalAxis)
      expect.soft(tipEnd.surface.normalSide, `${finger} normal side`).toBe(tip.surface.normalSide)
      expect.soft(tipEnd.surface.uAxis, `${finger} transverse axis`).toBe(tip.surface.uAxis)
      expect.soft(tipEnd.surface.vAxis, `${finger} longitudinal axis`).toBe(tip.surface.vAxis)
      expect.soft(tipEnd.surface.vRange[1], `${finger} adjacent edge`).toBeCloseTo(tip.surface.vRange[0], 6)
    }
  })
})
