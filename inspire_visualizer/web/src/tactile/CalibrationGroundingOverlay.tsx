import { createPortal, useFrame } from '@react-three/fiber'
import { Fragment, useEffect, useMemo, useRef } from 'react'
import { Group, Quaternion, Vector3 } from 'three'
import type { URDFRobot } from 'urdf-loader'

import type { CalibrationPoint } from './spatialCalibration'
import { targetUvForPoint } from './spatialCalibration'
import { tactilePatches } from './layout'
import { projectPatchToSurface, projectPointToSurface } from './surfaceProjection'
import type { HandSide } from '../app/types'

export interface GroundingFocus {
  point: Vector3
  normal: Vector3
}

interface MarkerProps {
  position: Vector3
  normal: Vector3
  color: string
  current?: boolean
  progress?: number
}

function GroundedMarker({ position, normal, color, current = false, progress = 0 }: MarkerProps) {
  const ref = useRef<Group>(null)
  const quaternion = useMemo(() => new Quaternion().setFromUnitVectors(new Vector3(0, 0, 1), normal), [normal])
  useFrame(({ clock }) => {
    if (!ref.current || !current) return
    const scale = 1 + Math.sin(clock.elapsedTime * 4) * 0.08
    ref.current.scale.setScalar(scale)
  })
  return (
    <group ref={ref} position={position} quaternion={quaternion} renderOrder={40}>
      <mesh><circleGeometry args={[current ? 0.0032 : 0.0022, 28]} /><meshBasicMaterial color={color} transparent opacity={current ? 0.32 : 0.9} depthTest={false} /></mesh>
      <mesh position={[0, 0, 0.00015]}><torusGeometry args={[current ? 0.005 : 0.003, 0.00045, 8, 40]} /><meshBasicMaterial color={color} depthTest={false} /></mesh>
      {current && progress > 0 ? <mesh position={[0, 0, 0.0003]} rotation={[0, 0, -Math.PI / 2]}><torusGeometry args={[0.0066, 0.0007, 8, 48, Math.PI * 2 * Math.min(1, progress)]} /><meshBasicMaterial color="#ffffff" depthTest={false} /></mesh> : null}
      {current ? <mesh position={[0, 0, 0.004]} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[0.00035, 0.00035, 0.008, 8]} /><meshBasicMaterial color={color} transparent opacity={0.8} depthTest={false} /></mesh> : null}
    </group>
  )
}

interface Props {
  robot: URDFRobot
  side: HandSide
  regionId: string
  point: CalibrationPoint
  completedPoints: CalibrationPoint[]
  progress: number
  wrongRegionId: string | null
  onFocus: (focus: GroundingFocus) => void
}

export function CalibrationGroundingOverlay({ robot, side, regionId, point, completedPoints, progress, wrongRegionId, onFocus }: Props) {
  const patch = useMemo(() => tactilePatches(side, 'piezoresistive_v1').find((item) => item.id === regionId), [regionId, side])
  const link = patch ? robot.links[patch.link] : undefined
  const surface = useMemo(() => link && patch ? projectPatchToSurface(link, patch, patch.surfaceRows ?? patch.rows, patch.surfaceColumns ?? patch.columns) : null, [link, patch])
  const target = useMemo(() => link && patch ? projectPointToSurface(link, patch, targetUvForPoint(patch, point), 0.0008) : null, [link, patch, point])
  const completed = useMemo(() => link && patch ? completedPoints.flatMap((item) => {
    const hit = projectPointToSurface(link, patch, targetUvForPoint(patch, item), 0.0008)
    return hit ? [{ item, hit }] : []
  }) : [], [completedPoints, link, patch])
  const wrongPatch = useMemo(() => wrongRegionId ? tactilePatches(side, 'piezoresistive_v1').find((item) => item.id === wrongRegionId) : undefined, [side, wrongRegionId])
  const wrongLink = wrongPatch ? robot.links[wrongPatch.link] : undefined
  const wrongSurface = useMemo(() => wrongLink && wrongPatch ? projectPatchToSurface(wrongLink, wrongPatch, wrongPatch.surfaceRows ?? wrongPatch.rows, wrongPatch.surfaceColumns ?? wrongPatch.columns) : null, [wrongLink, wrongPatch])

  useEffect(() => () => surface?.geometry.dispose(), [surface])
  useEffect(() => () => wrongSurface?.geometry.dispose(), [wrongSurface])
  useEffect(() => {
    if (!target || !link) return
    link.updateWorldMatrix(true, false)
    const pointWorld = link.localToWorld(target.point.clone())
    const normalWorld = target.normal.clone().transformDirection(link.matrixWorld)
    onFocus({ point: pointWorld, normal: normalWorld })
  }, [link, onFocus, target])
  if (!link || !surface || !target) return null
  return <>
    {createPortal(<>
      <mesh geometry={surface.geometry} renderOrder={35}><meshBasicMaterial color="#55d7df" transparent opacity={0.2} depthWrite={false} polygonOffset polygonOffsetFactor={-5} /></mesh>
      {completed.map(({ item, hit }) => <Fragment key={item}><GroundedMarker position={hit.point} normal={hit.normal} color="#72cf88" /></Fragment>)}
      <GroundedMarker position={target.point} normal={target.normal} color="#59d8e2" current progress={progress} />
    </>, link)}
    {wrongLink && wrongSurface ? createPortal(<mesh geometry={wrongSurface.geometry} renderOrder={36}><meshBasicMaterial color="#e0a34b" transparent opacity={0.48} depthWrite={false} polygonOffset polygonOffsetFactor={-6} /></mesh>, wrongLink) : null}
  </>
}
