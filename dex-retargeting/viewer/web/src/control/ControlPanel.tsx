import { useState } from 'react'
import { Octagon, Power, RotateCcw, Unplug } from 'lucide-react'

import type { ControlAction, ControlSnapshot, TrackingStatus } from '../api'
import { requestControl } from '../api'

export function ControlPanel({
  control,
  trackingStatus,
  request = requestControl,
}: {
  control: ControlSnapshot
  trackingStatus: TrackingStatus
  request?: (action: ControlAction) => Promise<ControlSnapshot>
}) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const armAllowed = control.connected && trackingStatus === 'TRACKING'
  const stateLabel = control.tracking_hold ? 'RECOVERY HOLD' : control.state

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
          <Power size={13} />ARM
        </button>
      )}
      {control.state === 'ARMED' && (
        <button className="control-button" disabled={busy} onClick={() => void invoke('disarm')}>
          <Unplug size={13} />DISARM
        </button>
      )}
      {control.state === 'ESTOPPED' && (
        <button className="control-button" disabled={busy} onClick={() => void invoke('reset')}>
          <RotateCcw size={13} />RESET
        </button>
      )}
      {(control.state === 'FAULT' || control.state === 'DISCONNECTED') && (
        <button className="control-button" disabled={busy} onClick={() => void invoke('reconnect')}>
          <RotateCcw size={13} />RECONNECT
        </button>
      )}
      {control.connected && control.state !== 'ESTOPPED' && (
        <button className="control-button estop-button" disabled={busy} onClick={() => void invoke('estop')}>
          <Octagon size={13} />E-STOP
        </button>
      )}
      {(error || control.error) && <span className="control-error">{error || control.error}</span>}

      {confirming && (
        <div className="modal-backdrop" role="presentation">
          <section className="arm-modal" role="dialog" aria-modal="true" aria-labelledby="arm-title">
            <header><span>CONTROL AUTHORIZATION</span><button aria-label="Close ARM confirmation" onClick={() => setConfirming(false)}>X</button></header>
            <div className="arm-modal-body">
              <span className="modal-code">RH56 / VISION / 30 HZ</span>
              <h2 id="arm-title">Arm vision control</h2>
              <p>The controller will start at the measured hand position and slew toward the current vision target.</p>
              <dl>
                <div><dt>DEVICE</dt><dd>{control.host}:{control.port}</dd></div>
                <div><dt>MEASURED</dt><dd>{formatChannels(control.actual)}</dd></div>
                <div><dt>VISION TARGET</dt><dd>{formatChannels(control.targets)}</dd></div>
              </dl>
              <div className="software-warning">SOFTWARE HOLD IS NOT A HARDWARE SAFETY STOP</div>
            </div>
            <footer>
              <button className="modal-cancel" onClick={() => setConfirming(false)}>Cancel</button>
              <button className="modal-confirm" disabled={busy} onClick={() => void invoke('arm')}>Confirm ARM</button>
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
