import { describe, expect, it } from 'vitest'

import { showsTactile, showsTargetPose } from '../src/app/workspaceMode'

describe('workspace modes', () => {
  it.each([
    ['motion', true, false],
    ['tactile', false, true],
    ['combined', true, true],
  ] as const)('%s mode controls target and tactile layers', (mode, targetVisible, tactileVisible) => {
    expect(showsTargetPose(mode)).toBe(targetVisible)
    expect(showsTactile(mode)).toBe(tactileVisible)
  })
})
