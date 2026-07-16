import { OrbitControls } from '@react-three/drei'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'
import { Vector3 } from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'

import type { ChannelValues, HandSide, TactileFrame } from '../app/types'
import { HandRobot } from '../hand-viewer/HandRobot'
import type { TactileBaseline } from './calibration'
import type { CalibrationPoint } from './spatialCalibration'
import type { GroundingFocus } from './CalibrationGroundingOverlay'

function FocusController({ focus, controls }: { focus: GroundingFocus | null; controls: RefObject<OrbitControlsImpl | null> }) {
  const { camera } = useThree()
  const active = useRef(false)
  useEffect(() => { active.current = Boolean(focus) }, [focus])
  useFrame(() => {
    if (!focus || !controls.current || !active.current) return
    const desired = focus.point.clone().addScaledVector(focus.normal, 0.13).add(new Vector3(0, 0.018, 0))
    camera.position.lerp(desired, 0.075)
    controls.current.target.lerp(focus.point, 0.1)
    controls.current.update()
    if (camera.position.distanceTo(desired) < 0.002 && controls.current.target.distanceTo(focus.point) < 0.001) active.current = false
  })
  return null
}

interface Props {
  side: HandSide
  actual: ChannelValues
  frame: TactileFrame | null
  baseline: TactileBaseline | undefined
  threshold: number
  scale: number
  regionId: string
  point: CalibrationPoint
  completedPoints: CalibrationPoint[]
  progress: number
  focusToken: number
  wrongRegionId: string | null
}

export function CalibrationScene({ side, actual, frame, baseline, threshold, scale, regionId, point, completedPoints, progress, focusToken, wrongRegionId }: Props) {
  const [resolvedFocus, setResolvedFocus] = useState<GroundingFocus | null>(null)
  const controls = useRef<OrbitControlsImpl>(null)
  const onFocus = useCallback((next: GroundingFocus) => setResolvedFocus({ point: next.point.clone(), normal: next.normal.clone() }), [focusToken])
  return (
    <Canvas camera={{ position: [0, 0.18, 0.55], fov: 35, near: 0.005, far: 10 }} dpr={[1, 2]}>
      <color attach="background" args={['#070a0b']} />
      <ambientLight intensity={0.75} />
      <directionalLight position={[0.35, 0.5, 0.4]} intensity={1.8} color="#eef4f4" />
      <directionalLight position={[-0.25, 0.1, -0.2]} intensity={0.75} color="#60b9c6" />
      <gridHelper args={[1.2, 60, '#385157', '#182226']} position={[0, -0.001, 0]} />
      <HandRobot side={side} actual={actual} target={actual} mode="tactile" tactileFrame={frame} tactileBaseline={baseline} heatStyle="smooth" tactileThreshold={threshold} tactileScale={scale} tactileDegraded={false} tactileSelection={null} onTactileSelect={() => undefined} positionX={0} showBaseFrame={false} showActuatorFrames={false} onError={() => undefined} calibrationGuide={{ regionId, point, completedPoints, progress, wrongRegionId, onFocus }} />
      <OrbitControls ref={controls} makeDefault target={[0, 0.1, 0]} minDistance={0.05} maxDistance={0.9} />
      <FocusController focus={resolvedFocus} controls={controls} />
    </Canvas>
  )
}
