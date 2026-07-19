import { Activity, Crosshair, Pause, Play, ScanLine, Waves } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import type { HandSide, HandSnapshot, TactileFrame } from '../app/types'
import { appendHistory, summarizeFrame, type TactileHistorySample } from './history'
import type { HeatStyle, TactileSelection } from './displayTypes'
import { regionKey, useI18n } from '../i18n/I18nProvider'

function HistoryPlot({ history, regionId }: { history: TactileHistorySample[]; regionId: string }) {
  const { t } = useI18n()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ratio = window.devicePixelRatio || 1
    const width = canvas.clientWidth
    const height = canvas.clientHeight
    canvas.width = Math.max(1, Math.round(width * ratio))
    canvas.height = Math.max(1, Math.round(height * ratio))
    const context = canvas.getContext('2d')
    if (!context) return
    context.scale(ratio, ratio)
    context.clearRect(0, 0, width, height)
    context.strokeStyle = '#273034'
    context.lineWidth = 1
    for (let line = 1; line < 4; line += 1) {
      const y = (height / 4) * line
      context.beginPath()
      context.moveTo(0, y)
      context.lineTo(width, y)
      context.stroke()
    }
    const values = history.map((sample) => sample.regions[regionId]).filter(Boolean)
    const maximum = Math.max(1, ...values.map((value) => value.peak))
    const draw = (key: 'mean' | 'peak', color: string) => {
      context.strokeStyle = color
      context.lineWidth = key === 'peak' ? 1.4 : 1
      context.beginPath()
      values.forEach((value, index) => {
        const x = values.length <= 1 ? width : (index / (values.length - 1)) * width
        const y = height - (value[key] / maximum) * (height - 5) - 2
        if (index === 0) context.moveTo(x, y)
        else context.lineTo(x, y)
      })
      context.stroke()
    }
    draw('mean', '#72afc0')
    draw('peak', '#f0c178')
  }, [history, regionId])
  return <canvas ref={canvasRef} className="tactile-history" aria-label={t('tactile.history')} />
}

interface TactilePanelProps {
  side: HandSide
  hand: HandSnapshot
  frame: TactileFrame | null
  selection: TactileSelection | null
  heatStyle: HeatStyle
  onHeatStyleChange: (style: HeatStyle) => void
  threshold: number
  onThresholdChange: (threshold: number) => void
  autoScale: boolean
  onAutoScaleChange: (enabled: boolean) => void
  scale: number
  onScaleChange: (scale: number) => void
  frozen: boolean
  onFrozenChange: (frozen: boolean) => void
  baselineReady: boolean
  zeroing: boolean
  onZero: () => void
  calibrationStatus?: string
  onStartCalibration?: () => void
}

export function TactilePanel({
  side,
  hand,
  frame,
  selection,
  heatStyle,
  onHeatStyleChange,
  threshold,
  onThresholdChange,
  autoScale,
  onAutoScaleChange,
  scale,
  onScaleChange,
  frozen,
  onFrozenChange,
  baselineReady,
  zeroing,
  onZero,
  calibrationStatus,
  onStartCalibration,
}: TactilePanelProps) {
  const { locale, t } = useI18n()
  const [history, setHistory] = useState<TactileHistorySample[]>([])
  useEffect(() => {
    if (!frame || frozen) return
    setHistory((current) => appendHistory(current, frame, threshold))
  }, [frame, frozen, threshold])

  const summary = useMemo(() => (frame ? summarizeFrame(frame, threshold) : null), [frame, threshold])
  const regions = summary ? Object.entries(summary.regions).sort((a, b) => b[1].peak - a[1].peak) : []
  const hottest = regions[0]
  const active = regions.reduce((total, [, region]) => total + region.active, 0)
  const selectedRegion = selection?.side === side ? selection.regionId : hottest?.[0] ?? 'palm'
  const selectedSummary = summary?.regions[selectedRegion]

  return (
    <aside className="control-panel tactile-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{t('app.tactile')} / {t(side === 'left' ? 'common.left' : 'common.right')}</span>
          <h2>{t('tactile.surfaceTelemetry')}</h2>
        </div>
        <span className={`connection-dot ${hand.tactile.state === 'live' ? 'online' : 'offline'}`}>
          {t(`common.${hand.tactile.state}` as import('../i18n/messages').MessageKey)}
        </span>
      </div>

      <div className="tactile-readout-grid">
        <div><span>{t('tactile.profile')}</span><strong>{hand.tactile.profile === 'piezoresistive_v1' ? 'PIEZO / 1062' : 'CAP / 5×8'}</strong></div>
        <div><span>{t('tactile.sample')}</span><strong>{hand.tactile.sample_hz.toFixed(1)} Hz</strong></div>
        <div><span>{t('tactile.peak')}</span><strong>{Math.round(hottest?.[1].peak ?? 0)}</strong></div>
        <div><span>{t('tactile.active')}</span><strong>{active}</strong></div>
      </div>

      <div className="segment-control" aria-label={t('tactile.heatRendering')}>
        <button type="button" className={heatStyle === 'raw' ? 'active' : ''} onClick={() => onHeatStyleChange('raw')}>{t('tactile.raw')}</button>
        <button type="button" className={heatStyle === 'smooth' ? 'active' : ''} onClick={() => onHeatStyleChange('smooth')}>{t('tactile.smooth')}</button>
      </div>

      <div className="tactile-actions">
        <button type="button" className={frozen ? 'active' : ''} onClick={() => onFrozenChange(!frozen)}>
          {frozen ? <Play size={15} /> : <Pause size={15} />}
          {t(frozen ? 'tactile.resume' : 'tactile.freeze')}
        </button>
        <button type="button" disabled={!frame || zeroing} onClick={onZero}>
          <Crosshair size={15} />
          {t(zeroing ? 'tactile.zeroing' : baselineReady ? 'tactile.rezero' : 'tactile.zero')}
        </button>
        <button type="button" disabled={!frame} onClick={onStartCalibration}>
          <ScanLine size={15} />
          {calibrationStatus ?? t('tactile.calibrate')}
        </button>
      </div>

      <div className="tactile-scale-controls">
        <label className="linked-toggle">
          <input type="checkbox" checked={autoScale} onChange={(event) => onAutoScaleChange(event.target.checked)} />
          {t('tactile.autoRange')}
        </label>
        <label>
          <span>{t('tactile.displayMax')}</span>
          <input type="number" min={1} max={65535} disabled={autoScale} value={Math.round(scale)} onChange={(event) => onScaleChange(Math.max(1, Number(event.target.value)))} />
        </label>
        <label>
          <span>{t('tactile.threshold')}</span>
          <input type="number" min={0} max={65535} value={threshold} onChange={(event) => onThresholdChange(Math.max(0, Number(event.target.value)))} />
        </label>
      </div>

      <section className="taxel-inspector">
        <header><span>{t('tactile.selectedSurface')}</span><Activity size={14} /></header>
        <div className="taxel-value">
          <strong>{selection?.side === side ? selection.value : Math.round(selectedSummary?.peak ?? 0)}</strong>
          <span>{t('tactile.counts')}</span>
        </div>
        <p>
          {t(regionKey(selectedRegion))}
          {selection?.side === side ? ` · R${selection.row + 1} C${selection.column + 1}` : ` · ${t('tactile.peakRegion')}`}
        </p>
        <HistoryPlot history={history} regionId={selectedRegion} />
        <div className="plot-key"><span><i className="mean" />{t('tactile.mean')}</span><span><i className="peak" />{t('tactile.peak')}</span><b>10 s</b></div>
      </section>

      <section className="region-table">
        <header><span>{t('tactile.contactRegions')}</span><Waves size={14} /></header>
        {regions.map(([regionId, region]) => (
          <div key={regionId} className={regionId === selectedRegion ? 'selected' : ''}>
            <span>{t(regionKey(regionId))}</span>
            <b>{Math.round(region.peak)}</b>
            <em>{region.active}/{region.total}</em>
          </div>
        ))}
      </section>

      {hand.tactile.error ? <p className="tactile-error">{locale === 'zh-CN' ? t('error.tactileSensor') : hand.tactile.error}</p> : null}
    </aside>
  )
}
