import type { HandSide, TactileProfile } from '../app/types'

export type SurfaceAxis = 0 | 1 | 2

export interface TactileSurfaceFit {
  uAxis: SurfaceAxis
  uRange: [number, number]
  vAxis: SurfaceAxis
  vRange: [number, number]
  normalAxis: SurfaceAxis
  normalSide: 'min' | 'max'
  margin: number
}

export interface TactilePatchLayout {
  id: string
  link: string
  rows: number
  columns: number
  surface: TactileSurfaceFit
  surfaceRows?: number
  surfaceColumns?: number
}

const FOUR_FINGERS = ['little', 'ring', 'middle', 'index'] as const
const SURFACE_MARGIN = 0.003

function fit(
  uAxis: SurfaceAxis,
  uRange: [number, number],
  vAxis: SurfaceAxis,
  vRange: [number, number],
  normalAxis: SurfaceAxis,
  normalSide: 'min' | 'max',
): TactileSurfaceFit {
  return { uAxis, uRange, vAxis, vRange, normalAxis, normalSide, margin: SURFACE_MARGIN }
}

function standardFingerPatches(side: HandSide): TactilePatchLayout[] {
  const patches: TactilePatchLayout[] = []
  for (const finger of FOUR_FINGERS) {
    const distal = `${side}_${finger}_2`
    const proximal = `${side}_${finger}_1`
    const sideways = side === 'right' && finger === 'little'
    const tipEndTransverse: [number, number] = side === 'left' ? [0.42, 0.68] : [0.32, 0.58]
    patches.push(
      {
        id: `${finger}_tip_end`,
        link: distal,
        rows: 3,
        columns: 3,
        surface: sideways
          ? fit(1, [0.68, 0.32], 0, [0.86, 0.74], 2, 'max')
          : fit(0, tipEndTransverse, 1, [0.86, 0.74], 2, 'max'),
      },
      {
        id: `${finger}_tip`,
        link: distal,
        rows: 12,
        columns: 8,
        surface: sideways
          ? fit(1, [0.72, 0.28], 0, [0.74, 0.37], 2, 'max')
          : fit(0, [0.28, 0.72], 1, [0.74, 0.37], 2, 'max'),
      },
      {
        id: `${finger}_pad`,
        link: proximal,
        rows: 10,
        columns: 8,
        surface: fit(0, [0.21, 0.79], 1, [0.79, 0.32], 2, 'max'),
      },
    )
  }
  return patches
}

function thumbPatches(side: HandSide): TactilePatchLayout[] {
  const left = side === 'left'
  const proximal = `${side}_thumb_${left ? 1 : 2}`
  const middle = `${side}_thumb_${left ? 2 : 3}`
  const distal = `${side}_thumb_${left ? 3 : 4}`
  const transverse: [number, number] = left ? [0.68, 0.32] : [0.32, 0.68]
  const narrowTransverse: [number, number] = left ? [0.62, 0.38] : [0.38, 0.62]
  return [
    {
      id: 'thumb_tip_end',
      link: distal,
      rows: 3,
      columns: 3,
      surface: fit(1, narrowTransverse, 0, left ? [0.82, 0.7] : [0.18, 0.3], 2, 'max'),
    },
    {
      id: 'thumb_tip',
      link: distal,
      rows: 12,
      columns: 8,
      surface: fit(1, transverse, 0, left ? [0.7, 0.28] : [0.3, 0.72], 2, 'max'),
    },
    {
      id: 'thumb_middle',
      link: middle,
      rows: 3,
      columns: 3,
      surface: fit(1, narrowTransverse, 0, left ? [0.45, 0.1] : [0.55, 0.9], 2, 'max'),
    },
    {
      id: 'thumb_pad',
      link: proximal,
      rows: 12,
      columns: 8,
      surface: fit(1, transverse, 0, left ? [0.78, 0.24] : [0.22, 0.76], 2, 'max'),
    },
  ]
}

function palmPatch(side: HandSide): TactilePatchLayout {
  const left = side === 'left'
  return {
    id: 'palm',
    link: 'base_link',
    rows: 8,
    columns: 14,
    surface: fit(
      0,
      [0.16, 0.92],
      2,
      left ? [0.82, 0.14] : [0.14, 0.82],
      1,
      left ? 'min' : 'max',
    ),
    surfaceRows: 16,
    surfaceColumns: 14,
  }
}

function withSurfaceDensity(patch: TactilePatchLayout): TactilePatchLayout {
  const isSmallCurvedPatch = patch.id.endsWith('_tip_end') || patch.id === 'thumb_middle'
  if (!isSmallCurvedPatch) return patch
  return {
    ...patch,
    surfaceRows: patch.rows * 2,
    surfaceColumns: patch.columns * 2,
  }
}

export function tactilePatches(
  side: HandSide,
  profile: Exclude<TactileProfile, 'disabled'>,
): TactilePatchLayout[] {
  const piezoresistive = [
    ...standardFingerPatches(side),
    ...thumbPatches(side),
    palmPatch(side),
  ].map(withSurfaceDensity)
  if (profile === 'piezoresistive_v1') return piezoresistive
  const fingertipIds = new Set(['little_tip', 'ring_tip', 'middle_tip', 'index_tip', 'thumb_tip'])
  return piezoresistive
    .filter((patch) => fingertipIds.has(patch.id))
    .map((patch) => ({ ...patch, rows: 1, columns: 8 }))
}
