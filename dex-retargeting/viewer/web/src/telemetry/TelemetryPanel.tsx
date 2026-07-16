import type { TrackingSnapshot } from '../api'

const JOINTS = [
  ['INDEX / PROX', 'index_proximal_joint'],
  ['INDEX / MID', 'index_intermediate_joint'],
  ['MIDDLE / PROX', 'middle_proximal_joint'],
  ['MIDDLE / MID', 'middle_intermediate_joint'],
  ['RING / PROX', 'ring_proximal_joint'],
  ['RING / MID', 'ring_intermediate_joint'],
  ['PINKY / PROX', 'pinky_proximal_joint'],
  ['PINKY / MID', 'pinky_intermediate_joint'],
  ['THUMB / YAW', 'thumb_proximal_yaw_joint'],
  ['THUMB / PITCH', 'thumb_proximal_pitch_joint'],
  ['THUMB / MID', 'thumb_intermediate_joint'],
  ['THUMB / DIST', 'thumb_distal_joint'],
] as const

const ACTUATORS = ['PINKY', 'RING', 'MIDDLE', 'INDEX', 'THUMB BEND', 'THUMB ROT']

function valueOrDash(value: number | undefined, digits = 3) {
  return value === undefined ? '---' : value.toFixed(digits)
}

export function TelemetryPanel({ snapshot }: { snapshot: TrackingSnapshot }) {
  return (
    <aside className="telemetry-panel">
      <section className="data-section joint-section">
        <header><span>RETARGETED JOINTS</span><b>12 DOF</b></header>
        <div className="data-list">
          {JOINTS.map(([label, key], index) => (
            <div className="data-row" data-testid="joint-row" key={key}>
              <i>{String(index + 1).padStart(2, '0')}</i>
              <span>{label}</span>
              <strong>{valueOrDash(snapshot.joints?.[key])}</strong>
              <small>rad</small>
            </div>
          ))}
        </div>
      </section>
      <section className="data-section actuator-section">
        <header><span>ESTIMATED DRIVE TARGETS</span><b>6 CH</b></header>
        <div className="data-list">
          {ACTUATORS.map((label, index) => (
            <div className="data-row actuator-row" data-testid="actuator-row" key={label}>
              <i>A{index + 1}</i>
              <span>{label}</span>
              <strong>{snapshot.actuators?.[index] ?? '---'}</strong>
              <small>cnt</small>
            </div>
          ))}
        </div>
      </section>
      <section className="data-section control-data-section">
        <header><span>RH56 CONTROL FEEDBACK</span><b>{snapshot.control.connected ? 'ONLINE' : 'OFFLINE'}</b></header>
        <div className="control-channel-head"><span>CH</span><span>ACT</span><span>CMD</span><span>SPD</span></div>
        {Array.from({ length: 6 }, (_, index) => (
          <div className="control-channel-row" key={index}>
            <i>A{index + 1}</i>
            <strong>{snapshot.control.actual?.[index] ?? '---'}</strong>
            <strong>{snapshot.control.commanded?.[index] ?? '---'}</strong>
            <strong>{snapshot.control.speeds?.[index] ?? '---'}</strong>
          </div>
        ))}
      </section>
    </aside>
  )
}
