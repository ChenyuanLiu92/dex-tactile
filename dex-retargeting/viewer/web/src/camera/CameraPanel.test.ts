import { describe, expect, test } from 'vitest'

import { containPoint } from './CameraPanel'

describe('containPoint', () => {
  test('accounts for letterboxing around a 16:9 camera image', () => {
    expect(containPoint(0, 0, 1000, 1000)).toEqual([0, 218.75])
    expect(containPoint(1, 1, 1000, 1000)).toEqual([1000, 781.25])
  })
})
