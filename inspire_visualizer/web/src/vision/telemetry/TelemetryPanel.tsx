import type { TrackingSnapshot } from '../api'
import type { MessageKey } from '../../i18n/messages'
import { useI18n } from '../../i18n/I18nProvider'

const JOINTS = [
  ['telemetry.indexProx', 'index_proximal_joint'], ['telemetry.indexMid', 'index_intermediate_joint'],
  ['telemetry.middleProx', 'middle_proximal_joint'], ['telemetry.middleMid', 'middle_intermediate_joint'],
  ['telemetry.ringProx', 'ring_proximal_joint'], ['telemetry.ringMid', 'ring_intermediate_joint'],
  ['telemetry.pinkyProx', 'pinky_proximal_joint'], ['telemetry.pinkyMid', 'pinky_intermediate_joint'],
  ['telemetry.thumbYaw', 'thumb_proximal_yaw_joint'], ['telemetry.thumbPitch', 'thumb_proximal_pitch_joint'],
  ['telemetry.thumbMid', 'thumb_intermediate_joint'], ['telemetry.thumbDist', 'thumb_distal_joint'],
] as const satisfies ReadonlyArray<readonly [MessageKey, string]>

const ACTUATORS: MessageKey[] = ['telemetry.pinky', 'telemetry.ring', 'telemetry.middle', 'telemetry.index', 'telemetry.thumbBend', 'telemetry.thumbRot']

function valueOrDash(value: number | undefined, digits = 3) {
  return value === undefined ? '---' : value.toFixed(digits)
}

export function TelemetryPanel({ snapshot }: { snapshot: TrackingSnapshot }) {
  const { t } = useI18n()
  return (
    <aside className="telemetry-panel">
      <section className="data-section joint-section">
        <header><span>{t('telemetry.joints')}</span><b>12 DOF</b></header>
        <div className="data-list">
          {JOINTS.map(([label, key], index) => (
            <div className="data-row" data-testid="joint-row" key={key}>
              <i>{String(index + 1).padStart(2, '0')}</i>
              <span>{t(label)}</span>
              <strong>{valueOrDash(snapshot.joints?.[key])}</strong>
              <small>rad</small>
            </div>
          ))}
        </div>
      </section>
      <section className="data-section actuator-section">
        <header><span>{t('telemetry.targets')}</span><b>6 CH</b></header>
        <div className="data-list">
          {ACTUATORS.map((label, index) => (
            <div className="data-row actuator-row" data-testid="actuator-row" key={label}>
              <i>A{index + 1}</i>
              <span>{t(label)}</span>
              <strong>{snapshot.actuators?.[index] ?? '---'}</strong>
              <small>cnt</small>
            </div>
          ))}
        </div>
      </section>
      <section className="data-section control-data-section">
        <header><span>{t('telemetry.feedback')}</span><b>{t(snapshot.control.connected ? 'common.online' : 'common.offline')}</b></header>
        <div className="control-channel-head"><span>{t('telemetry.channel')}</span><span>{t('telemetry.actual')}</span><span>{t('telemetry.command')}</span><span>{t('telemetry.speed')}</span></div>
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
