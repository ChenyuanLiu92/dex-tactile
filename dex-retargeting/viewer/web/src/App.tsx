import { Activity, Camera, Cpu, ShieldOff } from 'lucide-react'

import { EMPTY_SNAPSHOT, type TrackingSnapshot, useTrackingSnapshot } from './api'
import { CameraPanel } from './camera/CameraPanel'
import { ControlPanel } from './control/ControlPanel'
import { RobotScene } from './scene/RobotScene'
import { TelemetryPanel } from './telemetry/TelemetryPanel'

export function App({
  initialSnapshot = EMPTY_SNAPSHOT,
  connect = true,
}: {
  initialSnapshot?: TrackingSnapshot
  connect?: boolean
}) {
  const snapshot = useTrackingSnapshot(connect, initialSnapshot)
  const alert = snapshot.status === 'CAMERA_ERROR' || snapshot.status === 'WRONG_HAND'

  return (
    <main className="workbench">
      <header className="topbar">
        <div className="identity">
          <span className="machine-mark">IR</span>
          <div><strong>INSPIRE VISION RETARGETER</strong><small>D435 OPTICAL WORKBENCH</small></div>
        </div>
        <div className="system-strip">
          <span className="safety"><ShieldOff size={14} />SOFTWARE HOLD ONLY</span>
          <ControlPanel control={snapshot.control} trackingStatus={snapshot.status} />
          <span className={`tracking-state ${alert ? 'state-alert' : ''}`}>
            <i />{snapshot.status}
          </span>
        </div>
      </header>

      <section className="metrics-rail">
        <Metric icon={<Camera size={14} />} label="CAPTURE" value={snapshot.capture_fps} unit="FPS" />
        <Metric icon={<Activity size={14} />} label="TRACKING" value={snapshot.tracking_fps} unit="FPS" />
        <Metric icon={<Cpu size={14} />} label="PIPELINE" value={snapshot.latency_ms} unit="MS" />
        <Metric label="HAND" text={snapshot.handedness ?? '---'} />
        <Metric label="CONF" text={snapshot.confidence == null ? '---' : `${Math.round(snapshot.confidence * 100)}%`} />
        <span className="sequence">FRAME {String(snapshot.sequence).padStart(6, '0')}</span>
      </section>

      <div className="workspace-grid">
        <section className="panel camera-panel">
          <PanelHeader code="V01" title="OPERATOR VISION" detail="21 LANDMARKS" />
          <CameraPanel landmarks={snapshot.landmarks_2d} />
          {snapshot.status !== 'TRACKING' && (
            <div className={`tracking-notice ${alert ? 'notice-alert' : ''}`}>
              <strong>{snapshot.status.replace('_', ' ')}</strong>
              <span>{statusMessage(snapshot)}</span>
            </div>
          )}
        </section>
        <section className="panel model-panel">
          <PanelHeader code="M02" title="INSPIRE RIGHT HAND" detail="12 DOF / URDF" />
          <RobotScene joints={snapshot.joints} />
          <div className="model-caption"><span>DIGITAL TWIN</span><span>DRAG TO ORBIT</span></div>
        </section>
        <TelemetryPanel snapshot={snapshot} />
      </div>
    </main>
  )
}

function Metric({ icon, label, value, unit, text }: { icon?: React.ReactNode; label: string; value?: number; unit?: string; text?: string }) {
  return <span className="metric">{icon}<small>{label}</small><strong>{text ?? value?.toFixed(1) ?? '0.0'}</strong>{unit && <em>{unit}</em>}</span>
}

function PanelHeader({ code, title, detail }: { code: string; title: string; detail: string }) {
  return <header className="panel-header"><i>{code}</i><strong>{title}</strong><span>{detail}</span></header>
}

function statusMessage(snapshot: TrackingSnapshot) {
  if (snapshot.error) return snapshot.error
  if (snapshot.status === 'WRONG_HAND') return 'RIGHT HAND REQUIRED'
  if (snapshot.status === 'LOST') return 'RETURN RIGHT HAND TO CAMERA'
  if (snapshot.status === 'SEARCHING') return 'PRESENT RIGHT HAND TO CAMERA'
  if (snapshot.status === 'STARTING') return 'INITIALIZING VISION PIPELINE'
  return 'CHECK D435 CAMERA CONNECTION'
}
