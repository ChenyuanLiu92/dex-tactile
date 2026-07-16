import { Color, Group, Mesh, MeshBasicMaterial } from 'three'
import { describe, expect, it } from 'vitest'

import { tintUrdfVisuals } from '../src/hand-viewer/robotAppearance'

describe('URDF robot appearance', () => {
  it('tints only official visual meshes and leaves overlays and frame markers unchanged', () => {
    const robot = new Group()
    const visual = new Group() as Group & { isURDFVisual: true }
    visual.isURDFVisual = true
    const modelMaterial = new MeshBasicMaterial({ color: '#dde5e8' })
    const modelMesh = new Mesh(undefined, modelMaterial)
    visual.add(modelMesh)

    const helperMaterial = new MeshBasicMaterial({ color: '#d3913b' })
    const helperMesh = new Mesh(undefined, helperMaterial)
    robot.add(visual, helperMesh)

    const restore = tintUrdfVisuals(robot, '#50595c')

    expect(modelMaterial.color).toEqual(new Color('#50595c'))
    expect(helperMaterial.color).toEqual(new Color('#d3913b'))

    restore()
    expect(modelMaterial.color).toEqual(new Color('#dde5e8'))
  })
})
