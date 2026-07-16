import { Check, CircleDot, X } from 'lucide-react'
import { CALIBRATION_POINTS, type CalibrationPoint } from './spatialCalibration'
import { regionKey, useI18n } from '../i18n/I18nProvider'
import type { MessageKey } from '../i18n/messages'

const REGION_ORDER = ['little_tip_end','little_tip','little_pad','ring_tip_end','ring_tip','ring_pad','middle_tip_end','middle_tip','middle_pad','index_tip_end','index_tip','index_pad','thumb_tip_end','thumb_tip','thumb_middle','thumb_pad','palm']

interface Props {
  side: 'left' | 'right'
  regionId: string
  pointIndex: number
  onClose: () => void
  onRecord: () => void
}

export function CalibrationDialog({ side, regionId, pointIndex, onClose, onRecord }: Props) {
  const { t } = useI18n()
  const complete = pointIndex >= CALIBRATION_POINTS.length
  const point = CALIBRATION_POINTS[Math.min(pointIndex, CALIBRATION_POINTS.length - 1)] as CalibrationPoint
  return (
    <div className="dialog-backdrop calibration-backdrop" role="presentation">
      <section className="calibration-dialog" role="dialog" aria-modal="true" aria-labelledby="calibration-title">
        <header>
          <div><span className="eyebrow">{t('calibration.spatialMap', { side: t(side === 'left' ? 'common.left' : 'common.right') })}</span><h2 id="calibration-title">{t('calibration.title')}</h2></div>
          <button type="button" className="icon-button" title={t('calibration.exit')} onClick={onClose}><X size={18} /></button>
        </header>
        <div className="calibration-layout">
          <section className="calibration-guide">
            <span className="calibration-kicker">{t('calibration.currentSurface')}</span>
            <h3>{t(regionKey(regionId))}</h3>
            <p>{t(complete ? 'calibration.completeHelp' : 'calibration.pressHelp')}</p>
            <div className="calibration-target-map" aria-label={t('calibration.target', { point: t(`point.${point}` as MessageKey) })}>
              {CALIBRATION_POINTS.map((item, index) => <span key={item} className={`${index < pointIndex ? 'done' : ''} ${index === pointIndex && !complete ? 'current' : ''}`} title={t(`point.${item}` as MessageKey)}><CircleDot size={index === pointIndex ? 24 : 15} /></span>)}
            </div>
            <div className="calibration-step"><strong>{complete ? t('calibration.ready') : t('calibration.step', { current: pointIndex + 1, total: CALIBRATION_POINTS.length })}</strong><span>{complete ? t('calibration.previewReady') : t(`point.${point}` as MessageKey)}</span></div>
            <button type="button" className="primary-button calibration-record" onClick={onRecord}><Check size={16} />{t(complete ? 'calibration.apply' : 'calibration.record')}</button>
            <button type="button" className="calibration-cancel" onClick={onClose}>{t('calibration.cancel')}</button>
          </section>
          <section className="calibration-regions">
            <header><span>{t('calibration.regions')}</span><b>{REGION_ORDER.indexOf(regionId) + 1} / {REGION_ORDER.length}</b></header>
            <div className="calibration-region-list">{REGION_ORDER.map((id) => <div key={id} className={id === regionId ? 'active' : ''}><span className="region-status" />{t(regionKey(id))}</div>)}</div>
          </section>
        </div>
      </section>
    </div>
  )
}
