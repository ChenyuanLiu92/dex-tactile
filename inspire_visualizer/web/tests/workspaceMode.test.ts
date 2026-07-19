import { describe, expect, it } from 'vitest'

import { showsTargetPose } from '../src/app/workspaceMode'

describe('workspace modes', () => {
  it.each([
    ['motion', true],
    ['tactile', false],
    ['combined', true],
  ] as const)('%s mode controls the target pose layer', (mode, targetVisible) => {
    expect(showsTargetPose(mode)).toBe(targetVisible)
  })
})
