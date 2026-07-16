import { GizmoHelper, GizmoViewport, OrbitControls } from '@react-three/drei'
import { Canvas, useThree } from '@react-three/fiber'
import { Axis3D, Check, Grid3X3, RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import type { ChannelValues, HandSide, HandsSnapshot, TactileFrames } from '../app/types'
import { showsTactile, type WorkspaceMode } from '../app/workspaceMode'
import type { TactileBaseline } from '../tactile/calibration'
import type { TactileCalibrationDocument } from '../tactile/calibrationApi'
import type { HeatStyle, TactileSelection } from '../tactile/TactileOverlay'
import { AdaptiveGrid, type GridLevelName } from './AdaptiveGrid'
import {
  CoordinateFrame,
  FRAME_OPTIONS,
  type FrameMode,
  showsActuatorFrames,
  showsBaseFrames,
  showsWorldFrame,
} from './CoordinateFrame'
import { HandRobot } from './HandRobot'
import { useI18n } from '../i18n/I18nProvider'
import type { MessageKey } from '../i18n/messages'

function CameraReset({ token }: { token: number }) {
  const { camera } = useThree()
  useEffect(() => {
    camera.position.set(0, 0.22, 0.72)
    camera.lookAt(0, 0.1, 0)
    camera.updateProjectionMatrix()
  }, [camera, token])
  return null
}

interface HandSceneProps {
  sides: HandSide[]
  hands: HandsSnapshot
  targets: Record<HandSide, ChannelValues>
  mode: WorkspaceMode
  tactileFrames: TactileFrames
  baselines: Partial<Record<HandSide, TactileBaseline>>
  heatStyle: HeatStyle
  threshold: number
  scales: Record<HandSide, number>
  selection: TactileSelection | null
  onTactileSelect: (selection: TactileSelection) => void
  onModelError: (message: string) => void
  calibrations?: Partial<Record<HandSide, TactileCalibrationDocument | null>>
}

export function HandScene({
  sides,
  hands,
  targets,
  mode,
  tactileFrames,
  baselines,
  heatStyle,
  threshold,
  scales,
  selection,
  onTactileSelect,
  onModelError,
  calibrations,
}: HandSceneProps) {
  const { t } = useI18n()
  const [showGrid, setShowGrid] = useState(true)
  const [gridLevel, setGridLevel] = useState<GridLevelName>('standard')
  const [frameMode, setFrameMode] = useState<FrameMode>('all')
  const [frameMenuOpen, setFrameMenuOpen] = useState(false)
  const [resetToken, setResetToken] = useState(0)
  const frameMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!frameMenuOpen) return
    const closeMenu = (event: PointerEvent) => {
      if (!frameMenuRef.current?.contains(event.target as Node)) setFrameMenuOpen(false)
    }
    document.addEventListener('pointerdown', closeMenu)
    return () => document.removeEventListener('pointerdown', closeMenu)
  }, [frameMenuOpen])

  return (
    <div
      className="scene-shell"
      data-testid="scene-shell"
      data-grid-level={showGrid ? gridLevel : 'off'}
      data-workspace-mode={mode}
    >
      <div className="scene-tools" aria-label={t('viewer.tools')}>
        <button type="button" title={t('viewer.reset')} onClick={() => setResetToken((value) => value + 1)}>
          <RotateCcw size={17} />
        </button>
        <button
          type="button"
          className={showGrid ? 'active' : ''}
          title={t('viewer.grid')}
          onClick={() => setShowGrid((value) => !value)}
        >
          <Grid3X3 size={17} />
        </button>
        <div className="frame-control" ref={frameMenuRef}>
          <button
            type="button"
            className={frameMode !== 'off' ? 'active' : ''}
            title={t('viewer.frames')}
            aria-haspopup="menu"
            aria-expanded={frameMenuOpen}
            onClick={() => setFrameMenuOpen((value) => !value)}
          >
            <Axis3D size={17} />
          </button>
          {frameMenuOpen ? (
            <div
              className="frame-menu"
              role="menu"
              aria-label={t('viewer.frames')}
              onKeyDown={(event) => {
                if (event.key === 'Escape') setFrameMenuOpen(false)
              }}
            >
              <span>{t('viewer.frames')}</span>
              {FRAME_OPTIONS.map((option) => (
                <button
                  type="button"
                  key={option.value}
                  role="menuitemradio"
                  aria-checked={frameMode === option.value}
                  onClick={() => {
                    setFrameMode(option.value)
                    setFrameMenuOpen(false)
                  }}
                >
                  <Check size={13} className={frameMode === option.value ? 'selected' : ''} />
                  {t(option.labelKey as MessageKey)}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>
      <Canvas
        shadows
        dpr={[1, 2]}
        camera={{ position: [0, 0.22, 0.72], fov: 38, near: 0.01, far: 10 }}
        gl={{ antialias: true, alpha: false }}
      >
        <color attach="background" args={['#0b0e0f']} />
        <ambientLight intensity={0.72} />
        <directionalLight castShadow position={[0.3, 0.5, 0.35]} intensity={1.8} color="#f0f4f4" />
        <directionalLight position={[-0.35, 0.2, -0.2]} intensity={0.8} color="#72afc0" />
        {showGrid ? <AdaptiveGrid onLevelChange={setGridLevel} /> : null}
        {showsWorldFrame(frameMode) ? (
          <CoordinateFrame label="WORLD" size={0.072} position={[0, 0.003, 0]} kind="world" />
        ) : null}
        {sides.map((side, index) => {
          const offset = sides.length === 2 ? (index === 0 ? -0.105 : 0.105) : 0
          const actual = hands[side].actual_angles
          return actual ? (
            <HandRobot
              key={side}
              side={side}
              actual={actual}
              target={targets[side]}
              mode={mode}
              tactileFrame={tactileFrames[side]}
              tactileBaseline={baselines[side]}
              heatStyle={heatStyle}
              tactileThreshold={threshold}
              tactileScale={scales[side]}
              tactileDegraded={hands[side].tactile.state === 'degraded'}
              tactileSelection={selection}
              onTactileSelect={onTactileSelect}
              positionX={offset}
              showBaseFrame={showsBaseFrames(frameMode)}
              showActuatorFrames={showsActuatorFrames(frameMode)}
              onError={onModelError}
              tactileCalibration={calibrations?.[side]}
            />
          ) : null
        })}
        <CameraReset token={resetToken} />
        <OrbitControls makeDefault target={[0, 0.1, 0]} minDistance={0.15} maxDistance={1.2} />
        <GizmoHelper alignment="bottom-left" margin={[76, 76]}>
          <GizmoViewport axisColors={['#e05b52', '#65b96e', '#4f86d9']} labelColor="#e7ebec" />
        </GizmoHelper>
      </Canvas>
      <div className="scene-labels">
        {sides.map((side) => (
          <span key={side} className={`scene-label ${side}`}>
            {t(side === 'left' ? 'common.left' : 'common.right').toUpperCase()}
          </span>
        ))}
      </div>
      {showsTactile(mode) ? (
        <div className="heat-legend" aria-label={t('viewer.heatScale')}>
          <span>{t('viewer.contact')}</span><i /><span>{t('viewer.peak')}</span><b>{t('viewer.rawCounts')}</b>
        </div>
      ) : null}
    </div>
  )
}
