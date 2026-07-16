import { AlertTriangle, RefreshCw, Settings, Wifi, WifiOff } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { useDeviceSocket } from './api/useDeviceSocket'
import { loadTactileCalibration, saveTactileCalibration, type TactileCalibrationDocument } from './tactile/calibrationApi'
import {
  onlineHands,
  type ChannelValues,
  type HandSide,
  type TactileFrame,
  type TactileFrames,
} from './app/types'
import type { WorkspaceMode } from './app/workspaceMode'
import { ConfigDialog } from './device-control/ConfigDialog'
import { ControlPanel, type HandControls } from './device-control/ControlPanel'
import { ResizableInspector } from './device-control/ResizableInspector'
import { HandScene } from './hand-viewer/HandScene'
import { baselineFromFrames, noiseFromFrames, type TactileBaseline } from './tactile/calibration'
import { CALIBRATION_POINTS, classifyCalibration, fitBilinearTransform, latestRegionFrame, targetUvForPoint, weightedCentroid, type CalibrationSample, type RegionCalibration } from './tactile/spatialCalibration'
import { tactilePatches } from './tactile/layout'
import { useI18n } from './i18n/I18nProvider'
import { TactilePanel } from './tactile/TactilePanel'
import { CalibrationWorkspace } from './tactile/CalibrationWorkspace'
import { TactileAtlas2D, type TactileAtlasView } from './tactile/TactileAtlas2D'
import { CALIBRATION_REGION_ORDER, contactStep, initialCalibrationSession, type GuidedCalibrationSession } from './tactile/calibrationSession'
import type { HeatStyle, TactileSelection } from './tactile/TactileOverlay'
import './styles.css'

const OPEN_ANGLES: ChannelValues = [1000, 1000, 1000, 1000, 1000, 1000]
const DEFAULT_SPEEDS: ChannelValues = [100, 100, 100, 100, 100, 100]
const DEFAULT_FORCES: ChannelValues = [500, 500, 500, 500, 500, 500]

function defaultControls(): Record<HandSide, HandControls> {
  return {
    left: { angles: [...OPEN_ANGLES], speeds: [...DEFAULT_SPEEDS], forces: [...DEFAULT_FORCES] },
    right: { angles: [...OPEN_ANGLES], speeds: [...DEFAULT_SPEEDS], forces: [...DEFAULT_FORCES] },
  }
}

export default function App({ controlEnabled = true }: { controlEnabled?: boolean }) {
  const { locale, t } = useI18n()
  const { hands, tactileFrames, status, lastError, clearError, send } = useDeviceSocket()
  const [controls, setControls] = useState(defaultControls)
  const [activeSide, setActiveSide] = useState<HandSide>('right')
  const [configOpen, setConfigOpen] = useState(false)
  const [modelError, setModelError] = useState<string | null>(null)
  const [workspaceMode, setWorkspaceMode] = useState<WorkspaceMode>('motion')
  const [heatStyle, setHeatStyle] = useState<HeatStyle>('raw')
  const [tactileView, setTactileView] = useState<TactileAtlasView>('heatmap')
  const [threshold, setThreshold] = useState(0)
  const [autoScale, setAutoScale] = useState(true)
  const [manualScale, setManualScale] = useState(1000)
  const [frozen, setFrozen] = useState(false)
  const [frozenFrames, setFrozenFrames] = useState<TactileFrames>({ left: null, right: null })
  const [baselines, setBaselines] = useState<Partial<Record<HandSide, TactileBaseline>>>({})
  const [noiseProfiles, setNoiseProfiles] = useState<Partial<Record<HandSide, TactileBaseline>>>({})
  const [selection, setSelection] = useState<TactileSelection | null>(null)
  const [zeroingSide, setZeroingSide] = useState<HandSide | null>(null)
  const [calibrations, setCalibrations] = useState<Partial<Record<HandSide, TactileCalibrationDocument | null>>>({})
  const [calibration, setCalibration] = useState<(GuidedCalibrationSession & { samples: CalibrationSample[]; focusToken: number }) | null>(null)
  const zeroCapture = useRef<{
    side: HandSide
    startedAt: number
    lastSequence: number
    frames: TactileFrame[]
  } | null>(null)
  const calibrationSequence = useRef(-1)
  const calibrationReference = useRef<ChannelValues | null>(null)
  const calibrationPoseMovedSince = useRef<number | null>(null)
  const previousConnections = useRef({ left: 'offline', right: 'offline' })
  const visibleSides = useMemo(() => onlineHands(hands), [hands])

  useEffect(() => {
    const newlyOnline = (['left', 'right'] as const).filter(
      (side) =>
        previousConnections.current[side] !== 'online' &&
        hands[side].connection === 'online' &&
        hands[side].actual_angles !== null,
    )
    for (const side of ['left', 'right'] as const) {
      previousConnections.current[side] = hands[side].connection
    }
    if (newlyOnline.length === 0) return

    setControls((current) => {
      let next = current
      for (const side of newlyOnline) {
        const actualAngles = hands[side].actual_angles
        if (actualAngles) {
          next = {
            ...next,
            [side]: { ...next[side], angles: [...actualAngles] as ChannelValues },
          }
        }
      }
      return next
    })
  }, [hands])

  useEffect(() => {
    if (!visibleSides.includes(activeSide) && visibleSides[0]) setActiveSide(visibleSides[0])
  }, [activeSide, visibleSides])

  useEffect(() => {
    for (const side of visibleSides) loadTactileCalibration(side).then((document) => setCalibrations((current) => ({ ...current, [side]: document }))).catch(() => undefined)
  }, [visibleSides])

  useEffect(() => {
    const capture = zeroCapture.current
    if (!capture) return
    const frame = tactileFrames[capture.side]
    if (!frame || frame.sequence === capture.lastSequence) return
    capture.lastSequence = frame.sequence
    capture.frames.push(frame)
    if (performance.now() - capture.startedAt < 1000) return
    const baseline = baselineFromFrames(capture.frames)
    setBaselines((current) => ({ ...current, [capture.side]: baseline }))
    setNoiseProfiles((current) => ({ ...current, [capture.side]: noiseFromFrames(capture.frames, baseline) }))
    setCalibration((current) => current?.side === capture.side ? { ...current, stage: 'waiting_contact' } : current)
    zeroCapture.current = null
    setZeroingSide(null)
  }, [tactileFrames])

  const refreshDiscovery = useCallback(async () => {
    const response = await fetch('/api/discovery/refresh', { method: 'POST' })
    if (!response.ok) throw new Error(t('error.discovery'))
  }, [t])

  const execute = (side: HandSide) => {
    const values = controls[side]
    send({
      type: 'execute_pose',
      side,
      command_id: crypto.randomUUID(),
      angles: values.angles,
      speeds: values.speeds,
      forces: values.forces,
    })
  }

  const startZero = (side: HandSide) => {
    const frame = tactileFrames[side]
    if (!frame) return
    zeroCapture.current = {
      side,
      startedAt: performance.now(),
      lastSequence: frame.sequence,
      frames: [frame],
    }
    setZeroingSide(side)
  }

  const startCalibration = async (side: HandSide) => {
    if (!tactileFrames[side]) return
    setFrozen(false)
    calibrationSequence.current = -1
    calibrationPoseMovedSince.current = null
    calibrationReference.current = hands[side].actual_angles ? [...hands[side].actual_angles] as ChannelValues : null
    setBaselines((current) => ({ ...current, [side]: undefined }))
    setNoiseProfiles((current) => ({ ...current, [side]: undefined }))
    if (!calibrations[side]) {
      const response = await fetch('/api/config')
      if (!response.ok) return
      const config = await response.json() as { left: { host: string; port: number; tactile_profile: string }; right: { host: string; port: number; tactile_profile: string } }
      const endpoint = config[side]
      if (endpoint.tactile_profile !== 'piezoresistive_v1') return
      setCalibrations((current) => ({
        ...current,
        [side]: { version: 1, model: 'RH56DFTP', side, host: endpoint.host, port: endpoint.port, profile: 'piezoresistive_v1', regions: {}, drafts: {}, updated_at: new Date().toISOString() },
      }))
    }
    setCalibration({ ...initialCalibrationSession(side), stage: 'preflight', samples: [], focusToken: 0 })
  }

  useEffect(() => {
    if (!calibration || !baselines[calibration.side] || calibration.stage === 'preflight' || calibration.stage === 'review') return
    const actualAngles = hands[calibration.side].actual_angles
    const poseMoved = Boolean(actualAngles && calibrationReference.current?.some((value, index) => Math.abs(value - actualAngles[index]) > 20))
    if (poseMoved) calibrationPoseMovedSince.current ??= performance.now()
    else calibrationPoseMovedSince.current = null
    const moved = calibrationPoseMovedSince.current !== null && performance.now() - calibrationPoseMovedSince.current >= 500
    if (hands[calibration.side].connection !== 'online' || moved) {
      if (calibration.stage !== 'paused') setCalibration({ ...calibration, stage: 'paused', observations: [] })
      return
    }
    if (calibration.stage === 'paused') {
      setCalibration({ ...calibration, stage: 'waiting_contact', observations: [] })
      return
    }
    const frame = tactileFrames[calibration.side]
    if (!frame || frame.sequence === calibrationSequence.current) return
    calibrationSequence.current = frame.sequence
    const region = latestRegionFrame(frame, calibration.regionId)
    const contacts = frame.regions.flatMap((candidate) => {
      const limits = candidate.values.map((_, index) => Math.max(threshold, (noiseProfiles[calibration.side]?.[candidate.id]?.[index] ?? 0) * 5 + 1))
      const value = weightedCentroid(candidate, baselines[calibration.side]?.[candidate.id], limits)
      return value ? [{ id: candidate.id, value }] : []
    }).sort((left, right) => right.value.totalWeight - left.value.totalWeight)
    const strongest = contacts[0]
    const observation = strongest?.id === calibration.regionId ? strongest.value : null
    const next = { ...contactStep(calibration, observation, performance.now()), wrongRegionId: strongest && strongest.id !== calibration.regionId ? strongest.id : null }
    let samples = calibration.samples
    if (calibration.stage !== 'waiting_release' && next.stage === 'waiting_release' && next.pendingSample && region) {
      const patch = tactilePatches(calibration.side, 'piezoresistive_v1').find((item) => item.id === calibration.regionId)
      const point = CALIBRATION_POINTS[calibration.pointIndex]
      if (patch && point) {
        samples = [...samples, { point, targetUv: targetUvForPoint(patch, point), ...next.pendingSample, capturedAt: Date.now() }]
        const incompleteDraft: RegionCalibration = { regionId: calibration.regionId, samples, status: 'incomplete', applied: false, sensorRows: region.rows, sensorColumns: region.columns }
        setCalibrations((current) => {
          const document = current[calibration.side]
          if (!document) return current
          const savedDocument = { ...document, drafts: { ...(document.drafts ?? {}), [calibration.regionId]: incompleteDraft }, updated_at: new Date().toISOString() }
          void saveTactileCalibration(savedDocument)
          return { ...current, [calibration.side]: savedDocument }
        })
      }
    }
    if (next.pointIndex >= CALIBRATION_POINTS.length && region) {
      const transform = fitBilinearTransform(samples, region.rows, region.columns)
      const draft: RegionCalibration = { regionId: calibration.regionId, samples, transform, status: classifyCalibration(samples, transform, region.rows, region.columns), applied: false, sensorRows: region.rows, sensorColumns: region.columns }
      setCalibrations((current) => {
        const document = current[calibration.side]
        if (!document) return current
        const savedDocument = { ...document, drafts: { ...(document.drafts ?? {}), [calibration.regionId]: draft }, updated_at: new Date().toISOString() }
        void saveTactileCalibration(savedDocument)
        return { ...current, [calibration.side]: savedDocument }
      })
      const regionIndex = calibration.regionIndex + 1
      if (calibration.mode === 'single' || regionIndex >= CALIBRATION_REGION_ORDER.length) setCalibration({ ...next, stage: 'review', samples, focusToken: calibration.focusToken })
      else setCalibration({ ...initialCalibrationSession(calibration.side, CALIBRATION_REGION_ORDER[regionIndex]), regionIndex, samples: [], focusToken: calibration.focusToken + 1 })
      return
    }
    setCalibration({ ...next, samples, focusToken: calibration.focusToken })
  }, [baselines, calibration, hands, noiseProfiles, tactileFrames, threshold])

  const applyCalibrationDrafts = () => {
    if (!calibration) return
    const document = calibrations[calibration.side]
    if (!document) return
    const regions = { ...document.regions }
    for (const [id, draft] of Object.entries(document.drafts ?? {})) if (draft.status !== 'poor') regions[id] = { ...draft, applied: true }
    const next = { ...document, regions, drafts: {}, updated_at: new Date().toISOString() }
    setCalibrations((current) => ({ ...current, [calibration.side]: next }))
    void saveTactileCalibration(next)
    setCalibration(null)
  }

  const setFreeze = (next: boolean) => {
    if (next) setFrozenFrames(tactileFrames)
    setFrozen(next)
  }

  const visibleTactileFrames = frozen ? frozenFrames : tactileFrames
  const scales = useMemo(() => {
    const result = { left: manualScale, right: manualScale }
    if (!autoScale) return result
    for (const side of ['left', 'right'] as const) {
      const frame = visibleTactileFrames[side]
      if (!frame) continue
      const values = frame.regions.flatMap((region) =>
        region.values.map((value, index) =>
          Math.max(0, value - (baselines[side]?.[region.id]?.[index] ?? 0) - threshold),
        ),
      )
      values.sort((left, right) => left - right)
      result[side] = Math.max(1, values[Math.floor(values.length * 0.99)] ?? 1)
    }
    return result
  }, [autoScale, baselines, manualScale, threshold, visibleTactileFrames])
  const displayedError = useMemo(() => {
    const message = modelError ?? lastError
    if (!message) return null
    if (modelError) return locale === 'zh-CN' ? t('error.model') : message
    if (message === 'Unable to connect to the device gateway') return t('error.gatewayConnect')
    if (message === 'The device gateway is not connected') return t('error.gatewayOffline')
    if (message === 'WebSocket disconnected') return t('error.websocket')
    return locale === 'zh-CN' ? t('error.deviceOperation') : message
  }, [lastError, locale, modelError, t])

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <span className="brand-mark">IH</span>
          <div>
            <strong>{t('app.brand')}</strong>
            <span>{t('app.subtitle')}</span>
          </div>
        </div>
        <div className="topbar-actions">
          <span className={`gateway-status ${status}`}>
            {status === 'connected' ? <Wifi size={15} /> : <WifiOff size={15} />}
            {status === 'connected'
              ? t('gateway.online', { count: visibleSides.length, devices: t(visibleSides.length === 1 ? 'gateway.device' : 'gateway.devices') })
              : t('gateway.connecting')}
          </span>
          <button type="button" className="icon-button" title={t('app.scanDevices')} onClick={refreshDiscovery}>
            <RefreshCw size={18} />
          </button>
          <button type="button" className="icon-button" title={t('app.deviceSettings')} onClick={() => setConfigOpen(true)}>
            <Settings size={18} />
          </button>
        </div>
      </header>

      <section className="workspace">
        <div className="viewer-column">
          {workspaceMode === 'motion' ? <HandScene
            sides={visibleSides}
            hands={hands}
            targets={{ left: controls.left.angles, right: controls.right.angles }}
            mode="motion"
            tactileFrames={visibleTactileFrames}
            baselines={baselines}
            calibrations={calibrations}
            heatStyle={heatStyle}
            threshold={threshold}
            scales={scales}
            selection={selection}
            onTactileSelect={setSelection}
            onModelError={setModelError}
          /> : workspaceMode === 'tactile' ? <TactileAtlas2D
            side={activeSide}
            frame={visibleTactileFrames[activeSide]}
            baseline={baselines[activeSide]}
            threshold={threshold}
            scale={scales[activeSide]}
            heatStyle={heatStyle}
            selection={selection}
            view={tactileView}
            onViewChange={setTactileView}
            onSelect={setSelection}
          /> : <div className="combined-workspace">
            <div className="combined-motion"><HandScene
              sides={visibleSides}
              hands={hands}
              targets={{ left: controls.left.angles, right: controls.right.angles }}
              mode="motion"
              tactileFrames={visibleTactileFrames}
              baselines={baselines}
              calibrations={calibrations}
              heatStyle={heatStyle}
              threshold={threshold}
              scales={scales}
              selection={selection}
              onTactileSelect={setSelection}
              onModelError={setModelError}
            /></div>
            <TactileAtlas2D
              compact
              side={activeSide}
              frame={visibleTactileFrames[activeSide]}
              baseline={baselines[activeSide]}
              threshold={threshold}
              scale={scales[activeSide]}
              heatStyle={heatStyle}
              selection={selection}
              view={tactileView}
              onViewChange={setTactileView}
              onSelect={setSelection}
            />
          </div>}
          {visibleSides.length === 0 ? (
            <div className="empty-state">
              <WifiOff size={30} />
              <h1>{t('app.noHand')}</h1>
              <p>{t('app.noHandHelp')}</p>
              <button type="button" className="primary-button" onClick={() => setConfigOpen(true)}>
                <Settings size={16} />
                {t('app.configureDevices')}
              </button>
            </div>
          ) : null}
          {visibleSides.length > 0 ? (
            <div className="workspace-mode-tabs" aria-label={t('app.workspaceMode')}>
              <button type="button" className={workspaceMode === 'motion' ? 'active' : ''} onClick={() => setWorkspaceMode('motion')}>{t('app.motion')}</button>
              <button type="button" className={workspaceMode === 'tactile' ? 'active' : ''} onClick={() => setWorkspaceMode('tactile')}>{t('app.tactile')}</button>
              <button type="button" className={workspaceMode === 'combined' ? 'active' : ''} onClick={() => setWorkspaceMode('combined')}>{t('app.combined')}</button>
            </div>
          ) : null}
          {visibleSides.length > 0 ? (
            <div className="hand-tabs" aria-label={t('app.activeHand')}>
              {visibleSides.map((side) => (
                <button
                  type="button"
                  key={side}
                  className={activeSide === side ? 'active' : ''}
                  onClick={() => setActiveSide(side)}
                >
                  <span className="online-pip" />
                  {t(side === 'left' ? 'common.left' : 'common.right')}
                </button>
              ))}
            </div>
          ) : null}
        </div>

        <ResizableInspector>
          {visibleSides.includes(activeSide) ? (
            workspaceMode === 'motion' ? (
              <ControlPanel
                side={activeSide}
                hand={hands[activeSide]}
                controls={controls[activeSide]}
                onControlsChange={(value) =>
                  setControls((current) => ({ ...current, [activeSide]: value }))
                }
                onSetArmed={(armed) => send({ type: 'set_armed', side: activeSide, armed })}
                onExecute={() => execute(activeSide)}
                socketConnected={status === 'connected'}
                readOnly={!controlEnabled}
              />
            ) : (
              <TactilePanel
                side={activeSide}
                hand={hands[activeSide]}
                frame={visibleTactileFrames[activeSide]}
                selection={selection}
                heatStyle={heatStyle}
                onHeatStyleChange={setHeatStyle}
                threshold={threshold}
                onThresholdChange={setThreshold}
                autoScale={autoScale}
                onAutoScaleChange={setAutoScale}
                scale={scales[activeSide]}
                onScaleChange={setManualScale}
                frozen={frozen}
                onFrozenChange={setFreeze}
                baselineReady={Boolean(baselines[activeSide])}
                zeroing={zeroingSide === activeSide}
                onZero={() => startZero(activeSide)}
                onStartCalibration={() => startCalibration(activeSide)}
              />
            )
          ) : (
            <aside className="control-panel control-panel-empty">
              <span className="eyebrow">{t('app.deviceInspector')}</span>
              <h2>{t('app.waitingHardware')}</h2>
              <p>{t('app.waitingHardwareHelp')}</p>
            </aside>
          )}
        </ResizableInspector>
      </section>

      {displayedError ? (
        <div className="error-toast" role="alert">
          <AlertTriangle size={18} />
          <span>{displayedError}</span>
          <button
            type="button"
            onClick={() => {
              setModelError(null)
              clearError()
            }}
          >
            {t('app.dismiss')}
          </button>
        </div>
      ) : null}

      {calibration ? (
        <CalibrationWorkspace
          side={calibration.side}
          frame={tactileFrames[calibration.side]}
          baseline={baselines[calibration.side]}
          threshold={threshold}
          scale={scales[calibration.side]}
          regionId={calibration.regionId}
          pointIndex={calibration.pointIndex}
          regionIndex={calibration.regionIndex}
          stage={calibration.stage}
          progress={calibration.stage === 'waiting_release' ? 1 : calibration.observations.length / 6}
          zeroing={zeroingSide === calibration.side}
          focusToken={calibration.focusToken}
          wrongRegionId={calibration.wrongRegionId}
          onClose={() => setCalibration(null)}
          onZero={() => startZero(calibration.side)}
          onRetry={() => setCalibration({ ...initialCalibrationSession(calibration.side, calibration.regionId, calibration.mode), regionIndex: calibration.regionIndex, samples: [], focusToken: calibration.focusToken + 1 })}
          onSkip={() => {
            if (calibration.mode === 'single') {
              setCalibration({ ...calibration, stage: 'review' })
              return
            }
            const nextIndex = calibration.regionIndex + 1
            if (nextIndex >= CALIBRATION_REGION_ORDER.length) setCalibration({ ...calibration, stage: 'review' })
            else setCalibration({ ...initialCalibrationSession(calibration.side, CALIBRATION_REGION_ORDER[nextIndex]), regionIndex: nextIndex, samples: [], focusToken: calibration.focusToken + 1 })
          }}
          onRefocus={() => setCalibration({ ...calibration, focusToken: calibration.focusToken + 1 })}
          onRegionSelect={(regionId) => setCalibration({ ...initialCalibrationSession(calibration.side, regionId, 'single'), samples: [], focusToken: calibration.focusToken + 1 })}
          onApply={applyCalibrationDrafts}
        />
      ) : null}

      <ConfigDialog
        open={configOpen}
        hands={hands}
        onClose={() => setConfigOpen(false)}
        onSaved={refreshDiscovery}
      />
    </main>
  )
}
