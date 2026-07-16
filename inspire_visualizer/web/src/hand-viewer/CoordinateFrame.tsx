import { Html } from '@react-three/drei'

export type FrameMode = 'all' | 'world' | 'base' | 'actuators' | 'off'

export const FRAME_OPTIONS = [
  { value: 'all', label: 'All', labelKey: 'viewer.frameAll' },
  { value: 'world', label: 'World', labelKey: 'viewer.frameWorld' },
  { value: 'base', label: 'Base / mount', labelKey: 'viewer.frameBase' },
  { value: 'actuators', label: 'Drive joint axes', labelKey: 'viewer.frameActuators' },
  { value: 'off', label: 'Off', labelKey: 'viewer.frameOff' },
] as const satisfies ReadonlyArray<{ value: FrameMode; label: string; labelKey: string }>

export function showsWorldFrame(mode: FrameMode): boolean {
  return mode === 'all' || mode === 'world'
}

export function showsBaseFrames(mode: FrameMode): boolean {
  return mode === 'all' || mode === 'base'
}

export function showsActuatorFrames(mode: FrameMode): boolean {
  return mode === 'all' || mode === 'actuators'
}

interface CoordinateFrameProps {
  label: string
  size: number
  position?: [number, number, number]
  kind: 'world' | 'base' | 'actuator'
}

export function CoordinateFrame({
  label,
  size,
  position = [0, 0, 0],
  kind,
}: CoordinateFrameProps) {
  return (
    <group position={position}>
      <axesHelper args={[size]} />
      {kind === 'actuator' ? (
        <mesh renderOrder={30}>
          <sphereGeometry args={[size * 0.17, 14, 10]} />
          <meshBasicMaterial
            color="#d3913b"
            depthTest={false}
            depthWrite={false}
            toneMapped={false}
          />
        </mesh>
      ) : null}
      <Html
        center
        position={[size * 0.42, size * 0.62, 0]}
        distanceFactor={0.55}
        zIndexRange={[4, 0]}
        style={{ pointerEvents: 'none' }}
      >
        <span className={`frame-label ${kind}`}>{label}</span>
      </Html>
    </group>
  )
}
