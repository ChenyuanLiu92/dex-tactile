import { Check, Download, Pencil, Settings2, Trash2, Upload, UserRound, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { useI18n } from '../../i18n/I18nProvider'
import type {
  ControlState,
  DetectedHandSnapshot,
  OperatorProfileSummary,
  ProfileApi,
  ProfileCalibrationStatus,
  TrackingStatus,
} from '../api'
import { operatorProfileApi } from '../api'
import { ProfileCalibrationWorkspace } from './ProfileCalibrationWorkspace'


export function OperatorProfileControl({
  current,
  calibration,
  controlState,
  trackingStatus,
  detectedHands,
  landmarks,
  api = operatorProfileApi,
}: {
  current: OperatorProfileSummary
  calibration: ProfileCalibrationStatus | null
  controlState: ControlState
  trackingStatus: TrackingStatus
  detectedHands: DetectedHandSnapshot[]
  landmarks: number[][] | null
  api?: ProfileApi
}) {
  const { t } = useI18n()
  const [profiles, setProfiles] = useState<OperatorProfileSummary[]>([current])
  const [managerOpen, setManagerOpen] = useState(false)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [localCalibration, setLocalCalibration] = useState<ProfileCalibrationStatus | null>(null)
  const importRef = useRef<HTMLInputElement>(null)
  const disarmed = controlState === 'DISARMED'
  const session = calibration ?? localCalibration

  const refresh = async () => {
    const payload = await api.list()
    setProfiles(payload.profiles)
  }

  useEffect(() => { void refresh().catch((caught) => setError(String(caught))) }, [])
  useEffect(() => { if (calibration) setLocalCalibration(calibration) }, [calibration])

  const execute = async (action: () => Promise<unknown>, after?: () => void) => {
    setBusy(true)
    setError(null)
    try {
      await action()
      await refresh()
      after?.()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught))
    } finally {
      setBusy(false)
    }
  }

  const startCalibration = (profile: OperatorProfileSummary) => execute(
    async () => setLocalCalibration(await api.startCalibration(profile.id)),
    () => setManagerOpen(false),
  )

  const exportProfile = async (profile: OperatorProfileSummary) => {
    const document = await api.exportProfile(profile.id)
    const blob = new Blob([JSON.stringify(document, null, 2)], { type: 'application/json' })
    const link = window.document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `${profile.name.replace(/[^a-z0-9_-]+/gi, '-') || 'operator-profile'}.json`
    link.click()
    URL.revokeObjectURL(link.href)
  }

  const importFile = async (file: File | undefined) => {
    if (!file) return
    await execute(async () => {
      const document = JSON.parse(await file.text()) as Record<string, unknown>
      await api.importProfile(document)
    })
  }

  return (
    <div className="operator-profile-control">
      <UserRound size={13} />
      <select
        aria-label={t('profile.selector')}
        value={current.id}
        disabled={!disarmed || busy}
        title={!disarmed ? t('profile.disarmedOnly') : t('profile.selector')}
        onChange={(event) => void execute(() => api.activate(event.target.value))}
      >
        {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
      </select>
      <span className={`profile-state profile-${current.calibration_state.toLowerCase()}`}>
        {t(current.calibration_state === 'CALIBRATED' ? 'profile.calibrated' : current.calibration_state === 'DEFAULT' ? 'profile.default' : 'profile.uncalibrated')}
      </span>
      <button type="button" aria-label={t('profile.manage')} disabled={!disarmed} onClick={() => setManagerOpen(true)}><Settings2 size={14} /></button>
      {error && <span className="profile-inline-error">{error}</span>}

      {managerOpen && (
        <div className="modal-backdrop">
          <section className="profile-manager" role="dialog" aria-modal="true" aria-label={t('profile.managerTitle')}>
            <header><div><span>RH56 / VISION</span><strong>{t('profile.managerTitle')}</strong></div><button aria-label={t('profile.close')} onClick={() => setManagerOpen(false)}><X size={18} /></button></header>
            <div className="profile-create-row">
              <label><span>{t('profile.name')}</span><input aria-label={t('profile.name')} value={name} maxLength={40} onChange={(event) => setName(event.target.value)} /></label>
              <button disabled={busy || !name.trim()} onClick={() => void execute(() => api.create(name.trim()), () => setName(''))}>{t('profile.create')}</button>
              <button onClick={() => importRef.current?.click()}><Upload size={14} />{t('profile.import')}</button>
              <input ref={importRef} hidden type="file" accept="application/json" onChange={(event) => void importFile(event.target.files?.[0])} />
            </div>
            <div className="profile-list">
              {profiles.map((profile) => (
                <article key={profile.id} data-active={profile.id === current.id}>
                  <div className="profile-row-identity">
                    {renamingId === profile.id ? (
                      <input
                        autoFocus
                        aria-label={t('profile.rename')}
                        value={renameValue}
                        maxLength={40}
                        onChange={(event) => setRenameValue(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === 'Escape') setRenamingId(null)
                          if (event.key === 'Enter' && renameValue.trim()) void execute(
                            () => api.rename(profile.id, renameValue.trim()),
                            () => setRenamingId(null),
                          )
                        }}
                      />
                    ) : <strong>{profile.name}</strong>}
                    <span>{t(profile.calibration_state === 'CALIBRATED' ? 'profile.calibrated' : profile.calibration_state === 'DEFAULT' ? 'profile.default' : 'profile.uncalibrated')}</span>
                  </div>
                  <div className="profile-row-actions">
                    {profile.id !== 'default' && (renamingId === profile.id
                      ? <button title={t('profile.saveRename')} disabled={busy || !renameValue.trim()} onClick={() => void execute(() => api.rename(profile.id, renameValue.trim()), () => setRenamingId(null))}><Check size={14} /></button>
                      : <button title={t('profile.rename')} disabled={busy} onClick={() => { setRenamingId(profile.id); setRenameValue(profile.name) }}><Pencil size={14} /></button>)}
                    {profile.id !== current.id && <button disabled={busy} onClick={() => void execute(() => api.activate(profile.id))}>{t('profile.activate')}</button>}
                    {profile.id !== 'default' && <button aria-label={t('profile.calibrate', { name: profile.name })} disabled={busy || trackingStatus !== 'TRACKING'} onClick={() => void startCalibration(profile)}>{t('profile.calibrate', { name: profile.name })}</button>}
                    {profile.calibration_state === 'CALIBRATED' && <button title={t('profile.export')} onClick={() => void exportProfile(profile)}><Download size={14} /></button>}
                    {profile.id !== 'default' && <button title={t('profile.delete')} disabled={busy} onClick={() => void execute(() => api.remove(profile.id))}><Trash2 size={14} /></button>}
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>
      )}

      {session && !['CANCELED'].includes(session.state) && (
        <ProfileCalibrationWorkspace
          status={session}
          landmarks={landmarks}
          detectedHands={detectedHands}
          onRetry={() => void execute(async () => setLocalCalibration(await api.retryCalibration(session.profile_id)))}
          onCancel={() => void execute(async () => setLocalCalibration(await api.cancelCalibration(session.profile_id)), () => setLocalCalibration(null))}
        />
      )}
    </div>
  )
}
