import { Boxes, Camera, Languages, ShieldOff, SlidersHorizontal } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import DeviceWorkbench from './App'
import { EMPTY_SNAPSHOT, useTrackingSnapshot } from './vision/api'
import { VisionWorkbench } from './vision/VisionWorkbench'
import { useI18n } from './i18n/I18nProvider'
import { CONTROL_STATE_KEYS, TRACKING_STATUS_KEYS } from './vision/statusLabels'

type Workbench = 'vision' | 'digital-twin'
type ControlOwner = 'vision' | 'manual'

interface ControlOwnerSnapshot {
  owner: ControlOwner
  vision_state: string
  manual_control_enabled: boolean
}

export function UnifiedApp() {
  const { locale, t, toggleLocale } = useI18n()
  const [active, setActive] = useState<Workbench>('vision')
  const [owner, setOwner] = useState<ControlOwner>('vision')
  const [ownerBusy, setOwnerBusy] = useState(false)
  const [ownerError, setOwnerError] = useState<string | null>(null)
  const ownerRequestVersion = useRef(0)
  const vision = useTrackingSnapshot(true, EMPTY_SNAPSHOT)
  const controlAlert = ['ESTOPPED', 'FAULT', 'DISCONNECTED'].includes(vision.control.state)

  useEffect(() => {
    let live = true
    const requestVersion = ownerRequestVersion.current
    fetch('/api/control-owner')
      .then(async (response) => {
        if (!response.ok) throw new Error(await response.text())
        return response.json() as Promise<ControlOwnerSnapshot>
      })
      .then((snapshot) => {
        if (live && ownerRequestVersion.current === requestVersion) setOwner(snapshot.owner)
      })
      .catch((error) => { if (live) setOwnerError(error instanceof Error ? error.message : String(error)) })
    return () => { live = false }
  }, [])

  const changeOwner = async (nextOwner: ControlOwner) => {
    if (ownerBusy || nextOwner === owner) return
    ownerRequestVersion.current += 1
    setOwnerBusy(true)
    setOwnerError(null)
    try {
      const response = await fetch('/api/control-owner', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-RH56-Control': 'operator-confirmed' },
        body: JSON.stringify({ owner: nextOwner }),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => null) as { detail?: string } | null
        throw new Error(body?.detail ?? `Control mode switch failed (${response.status})`)
      }
      const snapshot = await response.json() as ControlOwnerSnapshot
      setOwner(snapshot.owner)
      setActive(snapshot.owner === 'vision' ? 'vision' : 'digital-twin')
    } catch (error) {
      setOwnerError(error instanceof Error ? error.message : String(error))
    } finally {
      setOwnerBusy(false)
    }
  }

  return (
    <main className="unified-shell">
      <header className="unified-commandbar">
        <div className="unified-identity">
          <span>DX</span>
          <div><strong>INSPIRE HAND WORKBENCH</strong><small>RH56DFTP / D435 / TACTILE</small></div>
        </div>
        <nav className="workbench-switcher" aria-label={t('unified.workbench')}>
          <button type="button" aria-pressed={active === 'vision'} onClick={() => setActive('vision')}>
            <Camera size={14} />{t('unified.visionControl')}
          </button>
          <button type="button" aria-pressed={active === 'digital-twin'} onClick={() => setActive('digital-twin')}>
            <Boxes size={14} />{t('unified.digitalTwin')}
          </button>
        </nav>
        <div className="unified-status">
          <div className="control-owner-switcher" aria-label={t('unified.controlOwner')}>
            <span>{t('unified.owner')}</span>
            <button type="button" aria-pressed={owner === 'vision'} disabled={ownerBusy} onClick={() => void changeOwner('vision')} title={t('unified.ownerVision')}>
              <Camera size={12} />{t('unified.visionShort')}
            </button>
            <button type="button" aria-pressed={owner === 'manual'} disabled={ownerBusy} onClick={() => void changeOwner('manual')} title={t('unified.ownerManual')}>
              <SlidersHorizontal size={12} />{t('unified.manualShort')}
            </button>
          </div>
          <span className={`unified-signal tracking-${vision.status.toLowerCase()}`}><i />{t(TRACKING_STATUS_KEYS[vision.status])}</span>
          <span className={`unified-signal ${controlAlert ? 'signal-alert' : ''}`}><ShieldOff size={13} />{t(CONTROL_STATE_KEYS[vision.control.state])}</span>
          <button type="button" className="unified-language" onClick={toggleLocale} title={t('app.switchLanguage')}><Languages size={13} />{locale === 'en' ? '中文' : 'EN'}</button>
        </div>
      </header>
      {ownerError && <div className="control-owner-error" role="alert">{ownerError}</div>}
      <section className="unified-stage">
        <div className="unified-pane" data-active={active === 'vision'} aria-hidden={active !== 'vision'}>
          <VisionWorkbench snapshot={vision} controlEnabled={owner === 'vision'} />
        </div>
        <div className="unified-pane" data-active={active === 'digital-twin'} aria-hidden={active !== 'digital-twin'}>
          <DeviceWorkbench controlEnabled={owner === 'manual'} />
        </div>
      </section>
    </main>
  )
}
