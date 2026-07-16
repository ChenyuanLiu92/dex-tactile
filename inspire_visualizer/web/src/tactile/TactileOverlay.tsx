import { createPortal, type ThreeEvent } from '@react-three/fiber'
import { Fragment, useEffect, useMemo } from 'react'
import {
  DataTexture,
  DoubleSide,
  LinearFilter,
  NearestFilter,
  RGBAFormat,
  SRGBColorSpace,
  UnsignedByteType,
} from 'three'
import type { URDFLink, URDFRobot } from 'urdf-loader'

import type { HandSide, TactileFrame, TactileRegionFrame } from '../app/types'
import type { TactileBaseline } from './calibration'
import type { TactileCalibrationDocument } from './calibrationApi'
import { heatColor, normalizedTactileValue } from './color'
import { tactilePatches, type TactilePatchLayout } from './layout'
import { projectPatchToSurface, projectedCellGeometry } from './surfaceProjection'

export type HeatStyle = 'raw' | 'smooth'

export interface TactileSelection {
  side: HandSide
  regionId: string
  row: number
  column: number
  value: number
}

interface PatchProps {
  side: HandSide
  link: URDFLink
  patch: TactilePatchLayout
  region: TactileRegionFrame
  baseline: number[] | undefined
  threshold: number
  scale: number
  style: HeatStyle
  degraded: boolean
  selected: TactileSelection | null
  onSelect: (selection: TactileSelection) => void
  calibration?: TactileCalibrationDocument | null
}

function TactilePatch({
  side,
  link,
  patch,
  region,
  baseline,
  threshold,
  scale,
  style,
  degraded,
  selected,
  onSelect,
  calibration,
}: PatchProps) {
  const surfaceRows = patch.surfaceRows ?? region.rows
  const surfaceColumns = patch.surfaceColumns ?? region.columns
  const projectedSurface = useMemo(
    () => {
      const transform = calibration?.regions[patch.id]?.applied ? calibration.regions[patch.id]?.transform : undefined
      const projected = projectPatchToSurface(link, patch, surfaceRows, surfaceColumns, transform)
      projected.geometry.userData.tactileProjection = {
        side,
        regionId: patch.id,
        link: patch.link,
        projectedVertices: projected.projectedVertices,
        sampledVertices: projected.sampledVertices,
        coverage: projected.coverage,
        interpolatedVertices: projected.interpolatedVertices,
      }
      return projected
    },
    [calibration, link, patch, side, surfaceColumns, surfaceRows],
  )
  const texture = useMemo(() => {
    const data = new Uint8Array(region.rows * region.columns * 4)
    const next = new DataTexture(
      data,
      region.columns,
      region.rows,
      RGBAFormat,
      UnsignedByteType,
    )
    next.colorSpace = SRGBColorSpace
    next.generateMipmaps = false
    return next
  }, [region.columns, region.rows])

  useEffect(() => () => projectedSurface.geometry.dispose(), [projectedSurface])
  useEffect(() => {
    if (!import.meta.env.DEV) return
    console.debug(`[tactile-map] ${side}/${patch.id}`, {
      link: patch.link,
      projected: projectedSurface.projectedVertices,
      sampled: projectedSurface.sampledVertices,
      coverage: Number(projectedSurface.coverage.toFixed(4)),
      interpolated: projectedSurface.interpolatedVertices,
    })
  }, [patch.id, patch.link, projectedSurface, side])
  useEffect(() => () => texture.dispose(), [texture])
  useEffect(() => {
    texture.magFilter = style === 'raw' ? NearestFilter : LinearFilter
    texture.minFilter = style === 'raw' ? NearestFilter : LinearFilter
    texture.needsUpdate = true
  }, [style, texture])
  useEffect(() => {
    const data = texture.image.data as Uint8Array
    for (let row = 0; row < region.rows; row += 1) {
      for (let column = 0; column < region.columns; column += 1) {
        const sourceIndex = row * region.columns + column
        const textureIndex = ((region.rows - row - 1) * region.columns + column) * 4
        const normalized = normalizedTactileValue(
          region.values[sourceIndex] ?? 0,
          baseline?.[sourceIndex] ?? 0,
          threshold,
          scale,
        )
        const color = heatColor(normalized)
        data.set(color, textureIndex)
      }
    }
    texture.needsUpdate = true
  }, [baseline, region, scale, texture, threshold])

  const patchSelected = selected?.side === side && selected.regionId === region.id
  const selectedRowSpan = surfaceRows / region.rows
  const selectedColumnSpan = surfaceColumns / region.columns
  const selectedGeometry = useMemo(
    () => patchSelected
      ? projectedCellGeometry(
          projectedSurface.geometry,
          selected.row * selectedRowSpan,
          selected.column * selectedColumnSpan,
          surfaceColumns,
          selectedRowSpan,
          selectedColumnSpan,
        )
      : null,
    [
      patchSelected,
      projectedSurface,
      selected?.column,
      selected?.row,
      selectedColumnSpan,
      selectedRowSpan,
      surfaceColumns,
    ],
  )
  useEffect(() => () => selectedGeometry?.dispose(), [selectedGeometry])

  const selectTaxel = (event: ThreeEvent<PointerEvent>) => {
    if (!event.uv) return
    event.stopPropagation()
    const column = Math.min(region.columns - 1, Math.max(0, Math.floor(event.uv.x * region.columns)))
    const row = Math.min(region.rows - 1, Math.max(0, Math.floor((1 - event.uv.y) * region.rows)))
    const index = row * region.columns + column
    onSelect({ side, regionId: region.id, row, column, value: region.values[index] ?? 0 })
  }

  return (
    <>
      <mesh geometry={projectedSurface.geometry} onPointerDown={selectTaxel} renderOrder={20}>
        <meshBasicMaterial
          map={texture}
          side={DoubleSide}
          transparent
          opacity={degraded ? 0.28 : 0.94}
          depthWrite={false}
          polygonOffset
          polygonOffsetFactor={-2}
          toneMapped={false}
        />
      </mesh>
      {selectedGeometry ? (
        <mesh geometry={selectedGeometry} renderOrder={21}>
          <meshBasicMaterial
            color="#ffffff"
            side={DoubleSide}
            wireframe
            transparent
            opacity={0.95}
            depthWrite={false}
            polygonOffset
            polygonOffsetFactor={-4}
          />
        </mesh>
      ) : null}
    </>
  )
}

interface TactileOverlayProps {
  side: HandSide
  robot: URDFRobot
  frame: TactileFrame
  baseline: TactileBaseline | undefined
  threshold: number
  scale: number
  style: HeatStyle
  degraded: boolean
  selected: TactileSelection | null
  onSelect: (selection: TactileSelection) => void
  calibration?: TactileCalibrationDocument | null
}

export function TactileOverlay({
  side,
  robot,
  frame,
  baseline,
  threshold,
  scale,
  style,
  degraded,
  selected,
  onSelect,
  calibration,
}: TactileOverlayProps) {
  const patches = useMemo(() => tactilePatches(side, frame.profile), [frame.profile, side])
  const regions = new Map(frame.regions.map((region) => [region.id, region]))
  return (
    <>
      {patches.map((patch) => {
        const link = robot.links[patch.link]
        const region = regions.get(patch.id)
        if (!link || !region) return null
        return (
          <Fragment key={patch.id}>
            {createPortal(
              <TactilePatch
                side={side}
                link={link}
                patch={patch}
                region={region}
                baseline={baseline?.[region.id]}
                threshold={threshold}
                scale={scale}
                style={style}
                degraded={degraded}
                selected={selected}
                onSelect={onSelect}
                calibration={calibration}
              />,
              link,
            )}
          </Fragment>
        )
      })}
    </>
  )
}
