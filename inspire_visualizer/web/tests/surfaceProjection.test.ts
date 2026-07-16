import { BoxGeometry, Group, Mesh, MeshBasicMaterial } from 'three'
import { describe, expect, it } from 'vitest'

import type { TactilePatchLayout } from '../src/tactile/layout'
import { projectPatchToSurface, projectedCellGeometry } from '../src/tactile/surfaceProjection'

const material = new MeshBasicMaterial()

function patch(overrides: Partial<TactilePatchLayout> = {}): TactilePatchLayout {
  return {
    id: 'test',
    link: 'test_link',
    rows: 2,
    columns: 2,
    surface: {
      uAxis: 0,
      uRange: [0.25, 0.75],
      vAxis: 1,
      vRange: [0.75, 0.25],
      normalAxis: 2,
      normalSide: 'max',
      margin: 1,
    },
    ...overrides,
  }
}

describe('tactile surface projection', () => {
  it('projects a grid onto the owned mesh with the exact surface offset and row-major UVs', () => {
    const link = new Group()
    link.add(new Mesh(new BoxGeometry(2, 2, 2), material))

    const result = projectPatchToSurface(link, patch(), 2, 2)
    const positions = result.geometry.getAttribute('position')
    const uvs = result.geometry.getAttribute('uv')

    expect(result.projectedVertices).toBe(9)
    expect(result.sampledVertices).toBe(9)
    expect(result.coverage).toBe(1)
    expect(positions.count).toBe(9)
    for (let index = 0; index < positions.count; index += 1) {
      expect(positions.getZ(index)).toBeCloseTo(1.00015, 6)
    }
    expect([uvs.getX(0), uvs.getY(0)]).toEqual([0, 1])
    expect([uvs.getX(8), uvs.getY(8)]).toEqual([1, 0])

    const selected = projectedCellGeometry(result.geometry, 0, 0, 2)
    expect(selected.getAttribute('position').count).toBe(4)
    selected.dispose()
    result.geometry.dispose()
  })

  it('extracts every projected subdivision belonging to a selected taxel', () => {
    const link = new Group()
    link.add(new Mesh(new BoxGeometry(2, 2, 2), material))
    const result = projectPatchToSurface(link, patch(), 4, 4)

    const selected = projectedCellGeometry(result.geometry, 0, 0, 4, 2, 2)

    expect(selected.getAttribute('position').count).toBe(9)
    expect(selected.getIndex()?.count).toBe(24)
    selected.dispose()
    result.geometry.dispose()
  })

  it('interpolates full geometry from a lower-resolution raycast grid', () => {
    const link = new Group()
    link.add(new Mesh(new BoxGeometry(2, 2, 2), material))

    const result = projectPatchToSurface(
      link,
      patch(),
      4,
      4,
    )

    expect(result.projectedVertices).toBe(25)
    expect(result.geometry.getAttribute('position').count).toBe(25)
    expect(result.geometry.getAttribute('position').getZ(12)).toBeCloseTo(1.00015, 6)
    result.geometry.dispose()
  })

  it('does not let a nested child-link mesh capture projection rays', () => {
    const link = new Group()
    link.add(new Mesh(new BoxGeometry(2, 2, 2), material))
    const childLink = new Group() as Group & { isURDFLink: true }
    childLink.isURDFLink = true
    const childMesh = new Mesh(new BoxGeometry(2, 2, 1), material)
    childMesh.position.z = 3
    childLink.add(childMesh)
    link.add(childLink)

    const result = projectPatchToSurface(link, patch(), 1, 1)
    const positions = result.geometry.getAttribute('position')

    expect(result.projectedVertices).toBe(4)
    expect(positions.getZ(0)).toBeCloseTo(1.00015, 6)
    result.geometry.dispose()
  })

  it('returns finite fallback geometry when every ray misses', () => {
    const link = new Group()
    link.add(new Mesh(new BoxGeometry(2, 2, 2), material))

    const result = projectPatchToSurface(link, patch({
      surface: {
        ...patch().surface,
        uRange: [2, 3],
      },
    }), 2, 2)
    const positions = result.geometry.getAttribute('position')

    expect(result.projectedVertices).toBe(0)
    expect(result.geometry.getIndex()?.count).toBe(0)
    for (let index = 0; index < positions.count; index += 1) {
      expect(Number.isFinite(positions.getX(index))).toBe(true)
      expect(Number.isFinite(positions.getY(index))).toBe(true)
      expect(Number.isFinite(positions.getZ(index))).toBe(true)
    }
    result.geometry.dispose()
  })

  it('clips cells with missed vertices instead of creating floating fallback triangles', () => {
    const link = new Group()
    link.add(new Mesh(new BoxGeometry(2, 2, 2), material))

    const result = projectPatchToSurface(link, patch({
      surface: {
        ...patch().surface,
        uRange: [0.5, 1.25],
      },
    }), 2, 2)

    expect(result.projectedVertices).toBe(6)
    expect(result.sampledVertices).toBe(9)
    expect(result.coverage).toBeCloseTo(2 / 3)
    expect(result.geometry.getIndex()?.count).toBe(12)
    result.geometry.dispose()
  })

  it('bridges a narrow interior CAD seam while preserving direct-hit coverage metrics', () => {
    const link = new Group()
    const leftHalf = new Mesh(new BoxGeometry(0.9, 2, 2), material)
    const rightHalf = new Mesh(new BoxGeometry(0.9, 2, 2), material)
    leftHalf.position.x = -0.55
    rightHalf.position.x = 0.55
    link.add(leftHalf, rightHalf)

    const result = projectPatchToSurface(link, patch(), 2, 4)

    expect(result.projectedVertices).toBe(12)
    expect(result.sampledVertices).toBe(15)
    expect(result.interpolatedVertices).toBe(3)
    expect(result.coverage).toBe(0.8)
    expect(result.projectedMask.every(Boolean)).toBe(true)
    expect(result.geometry.getIndex()?.count).toBe(48)
    result.geometry.dispose()
  })
})
