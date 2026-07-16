import { Crosshair, LocateFixed, RotateCcw, SkipForward, X } from 'lucide-react'
import type { HandSide, TactileFrame } from '../app/types'
import { regionKey, useI18n } from '../i18n/I18nProvider'
import type { MessageKey } from '../i18n/messages'
import type { TactileBaseline } from './calibration'
import { CALIBRATION_REGION_ORDER, type CalibrationStage } from './calibrationSession'
import { CALIBRATION_POINTS, type CalibrationPoint } from './spatialCalibration'
import { TactileAtlas2D } from './TactileAtlas2D'

interface Props {
  side: HandSide
  frame: TactileFrame | null
  baseline: TactileBaseline | undefined
  threshold: number
  scale: number
  regionId: string
  pointIndex: number
  stage: CalibrationStage
  progress: number
  regionIndex: number
  zeroing: boolean
  focusToken: number
  wrongRegionId: string | null
  onZero: () => void
  onClose: () => void
  onRetry: () => void
  onSkip: () => void
  onRefocus: () => void
  onRegionSelect: (regionId: string) => void
  onApply: () => void
}

export function CalibrationWorkspace(props: Props) {
  const { t } = useI18n()
  const ready = Boolean(props.baseline)
  const point = CALIBRATION_POINTS[Math.min(props.pointIndex, 4)] as CalibrationPoint
  const completedPoints = CALIBRATION_POINTS.slice(0, Math.min(props.pointIndex, 5)) as unknown as CalibrationPoint[]
  const statusKey: MessageKey = props.stage === 'paused' ? 'calibration.paused' : props.stage === 'sampling' ? 'calibration.sampling' : props.stage === 'waiting_release' ? 'calibration.release' : 'calibration.waiting'
  return (
    <div className="calibration-workspace" role="dialog" aria-modal="true" aria-label={t('calibration.workspace')}>
      <div className="calibration-canvas-shell">
        {ready ? <TactileAtlas2D side={props.side} frame={props.frame} baseline={props.baseline} threshold={props.threshold} scale={props.scale} heatStyle="raw" selection={null} view="heatmap" guide={{ regionId: props.regionId, point, completedPoints, progress: props.progress, focusToken: props.focusToken, wrongRegionId: props.wrongRegionId }} /> : <div className="calibration-preflight-visual"><Crosshair size={48} /><span>ZERO / RH56DFTP</span></div>}
        <button type="button" className="calibration-refocus" onClick={props.onRefocus}><LocateFixed size={16} />{t('calibration.refocus')}</button>
      </div>
      <aside className="calibration-rail">
        <header><div><span className="eyebrow">{t('calibration.autoCapture')}</span><h2>{t('calibration.workspace')}</h2></div><button type="button" className="icon-button" title={t('calibration.exit')} onClick={props.onClose}><X size={18} /></button></header>
        {!ready ? <section className="calibration-preflight"><h3>ZERO</h3><p>{t('calibration.preflight')}</p><button type="button" className="primary-button" disabled={props.zeroing || !props.frame} onClick={props.onZero}><Crosshair size={16} />{props.zeroing ? t('tactile.zeroing') : t('calibration.startZero')}</button></section> : <>
          <section className="calibration-current"><span>{t('calibration.fullProgress', { current: props.regionIndex + 1, total: CALIBRATION_REGION_ORDER.length })}</span><h3>{t(regionKey(props.regionId))}</h3><p>{t('calibration.focusHint')}</p><div className={`calibration-live-state ${props.stage} ${props.wrongRegionId ? 'wrong' : ''}`}><i /><strong>{props.wrongRegionId ? t('calibration.wrongRegion', { region: t(regionKey(props.wrongRegionId)) }) : t(statusKey)}</strong><b>{Math.round(props.progress * 100)}%</b></div><div className="calibration-point-strip">{CALIBRATION_POINTS.map((item, index) => <span key={item} className={index < props.pointIndex ? 'done' : index === props.pointIndex ? 'current' : ''} title={t(`point.${item}` as MessageKey)}>{index + 1}</span>)}</div></section>
          <section className="calibration-region-picker"><header><span>{t('calibration.regions')}</span><b>{props.regionIndex + 1}/{CALIBRATION_REGION_ORDER.length}</b></header><div>{CALIBRATION_REGION_ORDER.map((id) => <button type="button" key={id} className={id === props.regionId ? 'active' : ''} onClick={() => props.onRegionSelect(id)}><i />{t(regionKey(id))}</button>)}</div></section>
          <footer>{props.stage === 'review' ? <button type="button" className="primary-button" onClick={props.onApply}>{t('calibration.apply')}</button> : <><button type="button" onClick={props.onRetry}><RotateCcw size={15} />{t('calibration.retry')}</button><button type="button" onClick={props.onSkip}><SkipForward size={15} />{t('calibration.skip')}</button></>}</footer>
        </>}
      </aside>
    </div>
  )
}
