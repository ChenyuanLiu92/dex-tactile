import { describe, expect, it } from 'vitest'

import { heatColor, normalizedTactileValue } from '../src/tactile/color'

describe('tactile heat scale', () => {
  it('subtracts baseline and threshold before normalization', () => {
    expect(normalizedTactileValue(25, 10, 5, 20)).toBe(0.5)
    expect(normalizedTactileValue(12, 10, 5, 20)).toBe(0)
  })

  it('uses a dark idle and a bright peak with increasing perceived brightness', () => {
    const idle = heatColor(0)
    const middle = heatColor(0.5)
    const peak = heatColor(1)
    const brightness = ([red, green, blue]: number[]) => red * 0.2126 + green * 0.7152 + blue * 0.0722

    expect(idle).toEqual([8, 16, 20, 255])
    expect(peak).toEqual([255, 250, 225, 255])
    expect(brightness(idle)).toBeLessThan(brightness(middle))
    expect(brightness(middle)).toBeLessThan(brightness(peak))
  })
})
