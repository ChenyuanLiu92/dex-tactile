import { useState } from 'react'
import { Octagon, Power, RotateCcw, Unplug } from 'lucide-react'

import type { ControlAction, ControlSnapshot, TrackingStatus } from '../api'
import { requestControl } from '../api'
import { useI18n } from '../../i18n/I18nProvider'
import { CONTROL_STATE_KEYS } from '../statusLabels'

export function ControlPanel({
  control,
  trackingStatus,
  controlEnabled = true,
  request = requestControl,
}: {
  control: ControlSnapshot
  trackingStatus: TrackingStatus
  controlEnabled?: boolean
  request?: (action: ControlAction) => Promise<ControlSnapshot>
}) {
  const { t } = useI18n()
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const armAllowed = controlEnabled && control.connected && trackingStatus === 'TRACKING'
  const stateLabel = t(control.tracking_hold ? 'control.recoveryHold' : CONTROL_STATE_KEYS[control.state])

  const invoke = async (action: ControlAction) => {
    setBusy(true)
    setError(null)
    try {
      await request(action)
      setConfirming(false)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="control-cluster">
      <span className={`control-state control-${control.tracking_hold ? 'recovery' : control.state.toLowerCase()}`}>
        <i />{stateLabel}
      </span>
      {control.state === 'DISARMED' && (
        <button className="control-button arm-button" disabled={!armAllowed || busy} onClick={() => setConfirming(true)}>
          <Power size={13} />{t('control.arm')}
        </button>
      )}
      {control.state === 'ARMED' && (
        <button className="control-button" disabled={busy} onClick={() => void invoke('disarm')}>
          <Unplug size={13} />{t('control.disarm')}
        </button>
      )}
      {control.state === 'ESTOPPED' && (
        <button className="control-button" disabled={busy} onClick={() => void invoke('reset')}>
          <RotateCcw size={13} />{t('control.reset')}
        </button>
      )}
      {(control.state === 'FAULT' || control.state === 'DISCONNECTED') && (
        <button className="control-button" disabled={busy} onClick={() => void invoke('reconnect')}>
          <RotateCcw size={13} />{t('control.reconnect')}
        </button>
      )}
      {control.connected && control.state !== 'ESTOPPED' && (
        <button className="control-button estop-button" disabled={busy} onClick={() => void invoke('estop')}>
          <Octagon size={13} />{t('control.estop')}
        </button>
      )}
      {(error || control.error) && <span className="control-error">{error || control.error}</span>}

      {confirming && (
        <div className="modal-backdrop" role="presentation">
          <section className="arm-modal" role="dialog" aria-modal="true" aria-labelledby="arm-title">
            <header><span>{t('arm.authorization')}</span><button aria-label={t('arm.close')} onClick={() => setConfirming(false)}>X</button></header>
            <div className="arm-modal-body">
              <span className="modal-code">RH56 / VISION / 30 HZ</span>
              <h2 id="arm-title">{t('arm.title')}</h2>
              <p>{t('arm.description')}</p>
              <dl>
                <div><dt>{t('arm.device')}</dt><dd>{control.host}:{control.port}</dd></div>
                <div><dt>{t('arm.measured')}</dt><dd>{formatChannels(control.actual)}</dd></div>
                <div><dt>{t('arm.target')}</dt><dd>{formatChannels(control.targets)}</dd></div>
              </dl>
              <div className="software-warning">{t('arm.warning')}</div>
            </div>
            <footer>
              <button className="modal-cancel" onClick={() => setConfirming(false)}>{t('arm.cancel')}</button>
              <button className="modal-confirm" disabled={busy} onClick={() => void invoke('arm')}>{t('arm.confirm')}</button>
            </footer>
          </section>
        </div>
      )}
    </div>
  )
}

function formatChannels(values: number[] | null) {
  return values?.join(' ') ?? '--- --- --- --- --- ---'
}
