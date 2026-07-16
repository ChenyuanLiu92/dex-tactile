import { RefreshCw, Save, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import type { HandSide, HandsConfig, HandsSnapshot } from '../app/types'
import { useI18n } from '../i18n/I18nProvider'

interface ConfigDialogProps {
  open: boolean
  hands: HandsSnapshot
  onClose: () => void
  onSaved: () => Promise<void>
}

export function ConfigDialog({ open, hands, onClose, onSaved }: ConfigDialogProps) {
  const { t } = useI18n()
  const [config, setConfig] = useState<HandsConfig | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    setError(null)
    fetch('/api/config')
      .then(async (response) => {
        if (!response.ok) throw new Error(t('error.configLoad'))
        return (await response.json()) as HandsConfig
      })
      .then(setConfig)
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : t('error.configLoad')),
      )
  }, [open, t])

  if (!open) return null

  const updateEndpoint = (side: HandSide, patch: Partial<HandsConfig[HandSide]>) => {
    if (!config) return
    setConfig({ ...config, [side]: { ...config[side], ...patch } })
  }

  const save = async () => {
    if (!config) return
    setSaving(true)
    setError(null)
    try {
      const response = await fetch('/api/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      })
      if (!response.ok) {
        throw new Error(
          response.status === 422
            ? t('error.endpointConflict')
            : t('error.configSave'),
        )
      }
      await onSaved()
      onClose()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('error.configSave'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="config-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="config-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <span className="eyebrow">Modbus TCP</span>
            <h2 id="config-title">{t('config.title')}</h2>
          </div>
          <button type="button" className="icon-button" title={t('common.close')} onClick={onClose}>
            <X size={18} />
          </button>
        </header>
        <div className="endpoint-list">
          {(['left', 'right'] as const).map((side) => (
            <fieldset key={side}>
              <legend>
                <span>{t(side === 'left' ? 'common.leftHand' : 'common.rightHand')}</span>
                <span className={`connection-dot ${hands[side].connection}`}>
                  {t(hands[side].connection === 'online' ? 'common.online' : 'common.notConnected')}
                </span>
              </legend>
              <label className="enable-row">
                <input
                  type="checkbox"
                  checked={config?.[side].enabled ?? false}
                  onChange={(event) => updateEndpoint(side, { enabled: event.target.checked })}
                />
                {t('config.enable')}
              </label>
              <div className="endpoint-fields">
                <label>
                  {t('config.ip')}
                  <input
                    value={config?.[side].host ?? ''}
                    onChange={(event) => updateEndpoint(side, { host: event.target.value })}
                    placeholder={side === 'left' ? '192.0.2.11' : '192.0.2.10'}
                  />
                </label>
                <label>
                  {t('config.port')}
                  <input
                    type="number"
                    min={1}
                    max={65535}
                    value={config?.[side].port ?? 6000}
                    onChange={(event) => updateEndpoint(side, { port: Number(event.target.value) })}
                  />
                </label>
              </div>
              <div className="tactile-config-fields">
                <label>
                  {t('config.sensor')}
                  <select
                    value={config?.[side].tactile_profile ?? 'disabled'}
                    onChange={(event) =>
                      updateEndpoint(side, {
                        tactile_profile: event.target.value as HandsConfig[HandSide]['tactile_profile'],
                      })
                    }
                  >
                    <option value="disabled">{t('common.disabled')}</option>
                    <option value="piezoresistive_v1">{t('config.piezoresistive')}</option>
                    <option value="capacitive_v1">{t('config.capacitive')}</option>
                  </select>
                </label>
                <label>
                  {t('config.targetRate')}
                  <input
                    type="number"
                    min={1}
                    max={20}
                    disabled={config?.[side].tactile_profile === 'disabled'}
                    value={config?.[side].tactile_target_hz ?? 20}
                    onChange={(event) =>
                      updateEndpoint(side, { tactile_target_hz: Number(event.target.value) })
                    }
                  />
                </label>
              </div>
            </fieldset>
          ))}
        </div>
        {error ? <p className="dialog-error">{error}</p> : null}
        <footer>
          <button type="button" className="secondary-button" onClick={onSaved}>
            <RefreshCw size={16} />
            {t('config.scanAgain')}
          </button>
          <button type="button" className="primary-button" disabled={!config || saving} onClick={save}>
            <Save size={16} />
            {t(saving ? 'common.saving' : 'config.save')}
          </button>
        </footer>
      </section>
    </div>
  )
}
