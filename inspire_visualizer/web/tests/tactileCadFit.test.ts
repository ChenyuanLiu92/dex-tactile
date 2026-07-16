import fs from 'node:fs'

import { Mesh, MeshBasicMaterial, Group } from 'three'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { describe, expect, it } from 'vitest'

import { tactilePatches } from '../src/tactile/layout'
import { projectPatchToSurface, projectPointToSurface } from '../src/tactile/surfaceProjection'
import { targetUvForPoint } from '../src/tactile/spatialCalibration'

const loader = new STLLoader()
const material = new MeshBasicMaterial()

function loadLink(side: 'left' | 'right', linkName: string): Group {
  const file = fs.readFileSync(`public/models/${side}/meshes/${linkName}.STL`)
  const data = file.buffer.slice(file.byteOffset, file.byteOffset + file.byteLength)
  const geometry = loader.parse(data)
  const link = new Group()
  link.add(new Mesh(geometry, material))
  return link
}

describe('official CAD-derived tactile fit', () => {
  it('grounds a calibration target and normal on the intended CAD surface', () => {
    const patch = tactilePatches('left', 'piezoresistive_v1').find((item) => item.id === 'index_tip')!
    const hit = projectPointToSurface(loadLink('left', patch.link), patch, targetUvForPoint(patch, 'center'))
    expect(hit).not.toBeNull()
    expect(hit?.normal.length()).toBeCloseTo(1, 4)
  })
  it.each(['left', 'right'] as const)(
    'projects every %s-hand region onto its official link mesh without floating cells',
    (side) => {
      for (const patch of tactilePatches(side, 'piezoresistive_v1')) {
        const link = loadLink(side, patch.link)
        const rows = patch.surfaceRows ?? patch.rows
        const columns = patch.surfaceColumns ?? patch.columns
        const result = projectPatchToSurface(link, patch, rows, columns)
        const rowCoverage = Array.from({ length: rows + 1 }, (_, row) => {
          const start = row * (columns + 1)
          const hits = result.projectedMask.slice(start, start + columns + 1).filter(Boolean).length
          return `${hits}/${columns + 1}`
        }).join(',')

        expect.soft(
          result.coverage,
          `${side}/${patch.id} row hits [${rowCoverage}]`,
        ).toBeGreaterThanOrEqual(0.9)
        expect.soft(result.geometry.getIndex()?.count, `${side}/${patch.id}`).toBeGreaterThan(0)
        result.geometry.dispose()
      }
    },
    20_000,
  )
})
