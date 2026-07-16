import { Activity, Camera, Cpu, ShieldOff } from 'lucide-react'

import type { TrackingSnapshot } from './api'
import { CameraPanel } from './camera/CameraPanel'
import { ControlPanel } from './control/ControlPanel'
import { RobotScene } from './scene/RobotScene'
import { TelemetryPanel } from './telemetry/TelemetryPanel'
import { useI18n } from '../i18n/I18nProvider'
import { TRACKING_STATUS_KEYS } from './statusLabels'
import './styles.css'

export function VisionWorkbench({ snapshot }: { snapshot: TrackingSnapshot }) {
  const { locale, t } = useI18n()
  const alert = snapshot.status === 'CAMERA_ERROR' || snapshot.status === 'WRONG_HAND'

  return (
    <div className="vision-host">
    <main className="workbench">
      <header className="topbar">
        <div className="identity">
          <span className="machine-mark">IR</span>
          <div><strong>{t('vision.brand')}</strong><small>{t('vision.subtitle')}</small></div>
        </div>
        <div className="system-strip">
          <span className="safety"><ShieldOff size={14} />{t('vision.softwareHold')}</span>
          <ControlPanel control={snapshot.control} trackingStatus={snapshot.status} />
          <span className={`tracking-state ${alert ? 'state-alert' : ''}`}>
            <i />{t(TRACKING_STATUS_KEYS[snapshot.status])}
          </span>
        </div>
      </header>

      <section className="metrics-rail">
        <Metric icon={<Camera size={14} />} label={t('vision.capture')} value={snapshot.capture_fps} unit="FPS" />
        <Metric icon={<Activity size={14} />} label={t('vision.tracking')} value={snapshot.tracking_fps} unit="FPS" />
        <Metric icon={<Cpu size={14} />} label={t('vision.pipeline')} value={snapshot.latency_ms} unit="MS" />
        <Metric label={t('vision.hand')} text={handLabel(snapshot, locale, t)} />
        <Metric label={t('vision.confidence')} text={snapshot.confidence == null ? '---' : `${Math.round(snapshot.confidence * 100)}%`} />
        <span className="sequence">{t('vision.frame')} {String(snapshot.sequence).padStart(6, '0')}</span>
      </section>

      <div className="workspace-grid">
        <section className="panel camera-panel">
          <PanelHeader code="V01" title={t('vision.operatorVision')} detail={t('vision.landmarks')} />
          <CameraPanel landmarks={snapshot.landmarks_2d} detectedHands={snapshot.detected_hands ?? []} />
          {snapshot.status !== 'TRACKING' && (
            <div className={`tracking-notice ${alert ? 'notice-alert' : ''}`}>
              <strong>{t(TRACKING_STATUS_KEYS[snapshot.status])}</strong>
              <span>{statusMessage(snapshot, t)}</span>
            </div>
          )}
        </section>
        <section className="panel model-panel">
          <PanelHeader code="M02" title={t('vision.rightHand')} detail="12 DOF / URDF" />
          <RobotScene joints={snapshot.joints} />
          <div className="model-caption"><span>{t('vision.digitalTwin')}</span><span>{t('vision.dragOrbit')}</span></div>
        </section>
        <TelemetryPanel snapshot={snapshot} />
      </div>
    </main>
    </div>
  )
}

function Metric({ icon, label, value, unit, text }: { icon?: React.ReactNode; label: string; value?: number; unit?: string; text?: string }) {
  return <span className="metric">{icon}<small>{label}</small><strong>{text ?? value?.toFixed(1) ?? '0.0'}</strong>{unit && <em>{unit}</em>}</span>
}

function PanelHeader({ code, title, detail }: { code: string; title: string; detail: string }) {
  return <header className="panel-header"><i>{code}</i><strong>{title}</strong><span>{detail}</span></header>
}

function statusMessage(snapshot: TrackingSnapshot, t: ReturnType<typeof useI18n>['t']) {
  if (snapshot.error) return snapshot.error
  if (snapshot.status === 'WRONG_HAND') return t('vision.rightRequired')
  if (snapshot.status === 'LOST') return t('vision.returnHand')
  if (snapshot.status === 'SEARCHING') return t('vision.presentHand')
  if (snapshot.status === 'STARTING') return t('vision.initializing')
  return t('vision.checkCamera')
}

function handLabel(snapshot: TrackingSnapshot, locale: string, t: ReturnType<typeof useI18n>['t']) {
  const detected = [...new Set((snapshot.detected_hands ?? []).map((hand) => hand.handedness))]
  if (detected.length === 0 && snapshot.handedness) detected.push(snapshot.handedness as 'Left' | 'Right')
  if (detected.length === 0) return '---'
  return detected.map((hand) => locale === 'zh-CN' ? t(hand === 'Right' ? 'common.right' : 'common.left') : hand).join(' + ')
}
