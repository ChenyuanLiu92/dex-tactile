import { Boxes, Camera, Languages, ShieldOff } from 'lucide-react'
import { useState } from 'react'

import DeviceWorkbench from './App'
import { EMPTY_SNAPSHOT, useTrackingSnapshot } from './vision/api'
import { VisionWorkbench } from './vision/VisionWorkbench'
import { useI18n } from './i18n/I18nProvider'
import { CONTROL_STATE_KEYS, TRACKING_STATUS_KEYS } from './vision/statusLabels'

type Workbench = 'vision' | 'digital-twin'

export function UnifiedApp() {
  const { locale, t, toggleLocale } = useI18n()
  const [active, setActive] = useState<Workbench>('vision')
  const vision = useTrackingSnapshot(true, EMPTY_SNAPSHOT)
  const controlAlert = ['ESTOPPED', 'FAULT', 'DISCONNECTED'].includes(vision.control.state)

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
          <span className={`unified-signal tracking-${vision.status.toLowerCase()}`}><i />{t(TRACKING_STATUS_KEYS[vision.status])}</span>
          <span className={`unified-signal ${controlAlert ? 'signal-alert' : ''}`}><ShieldOff size={13} />{t(CONTROL_STATE_KEYS[vision.control.state])}</span>
          <button type="button" className="unified-language" onClick={toggleLocale} title={t('app.switchLanguage')}><Languages size={13} />{locale === 'en' ? '中文' : 'EN'}</button>
        </div>
      </header>
      <section className="unified-stage">
        <div className="unified-pane" data-active={active === 'vision'} aria-hidden={active !== 'vision'}>
          <VisionWorkbench snapshot={vision} />
        </div>
        <div className="unified-pane" data-active={active === 'digital-twin'} aria-hidden={active !== 'digital-twin'}>
          <DeviceWorkbench controlEnabled={false} />
        </div>
      </section>
    </main>
  )
}
