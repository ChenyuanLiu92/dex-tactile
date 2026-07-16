import { Activity, ChartNoAxesCombined, Grid3X3 } from 'lucide-react'
import { useEffect, useMemo, useRef, type CSSProperties } from 'react'

import type { HandSide, TactileFrame, TactileProfile, TactileRegionFrame } from '../app/types'
import { regionKey, useI18n } from '../i18n/I18nProvider'
import type { TactileBaseline } from './calibration'
import { heatColor, normalizedTactileValue } from './color'
import { tactilePatches, type TactilePatchLayout } from './layout'
import type { CalibrationPoint } from './spatialCalibration'
import type { HeatStyle, TactileSelection } from './TactileOverlay'

export type TactileAtlasView = 'heatmap' | 'surface'

interface AtlasGroup {
  id: 'little' | 'ring' | 'middle' | 'index' | 'thumb' | 'palm'
  patches: TactilePatchLayout[]
}

interface CalibrationGuide {
  regionId: string
  point: CalibrationPoint
  completedPoints: CalibrationPoint[]
  progress: number
  wrongRegionId: string | null
  focusToken: number
}

interface Props {
  side: HandSide
  frame: TactileFrame | null
  baseline?: TactileBaseline
  threshold: number
  scale: number
  heatStyle: HeatStyle
  selection: TactileSelection | null
  view: TactileAtlasView
  onViewChange?: (view: TactileAtlasView) => void
  onSelect?: (selection: TactileSelection) => void
  guide?: CalibrationGuide
  compact?: boolean
}

const GROUP_IDS = ['little', 'ring', 'middle', 'index', 'thumb', 'palm'] as const

export function atlasRegionGroups(
  side: HandSide,
  profile: Exclude<TactileProfile, 'disabled'>,
): AtlasGroup[] {
  const patches = tactilePatches(side, profile)
  return GROUP_IDS.map((id) => ({
    id,
    patches: patches.filter((patch) => id === 'palm' ? patch.id === 'palm' : patch.id.startsWith(`${id}_`)),
  }))
}

export function taxelAtPoint(
  x: number,
  y: number,
  width: number,
  height: number,
  rows: number,
  columns: number,
) {
  const column = Math.min(columns - 1, Math.max(0, Math.floor((x / Math.max(1, width)) * columns)))
  const row = Math.min(rows - 1, Math.max(0, Math.floor((y / Math.max(1, height)) * rows)))
  return { row, column }
}

function rgba(color: [number, number, number, number]) {
  return `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${color[3] / 255})`
}

function normalizedValues(region: TactileRegionFrame, baseline: number[] | undefined, threshold: number, scale: number) {
  return region.values.map((value, index) => normalizedTactileValue(value, baseline?.[index] ?? 0, threshold, scale))
}

function drawHeatmap(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  region: TactileRegionFrame,
  values: number[],
  smooth: boolean,
) {
  const cellWidth = width / region.columns
  const cellHeight = height / region.rows
  context.imageSmoothingEnabled = smooth
  context.fillStyle = '#081014'
  context.fillRect(0, 0, width, height)
  for (let row = 0; row < region.rows; row += 1) {
    for (let column = 0; column < region.columns; column += 1) {
      const value = values[row * region.columns + column] ?? 0
      context.fillStyle = rgba(heatColor(value))
      const gap = smooth ? 0 : Math.max(0.45, Math.min(1.25, cellWidth * 0.06))
      context.fillRect(column * cellWidth + gap / 2, row * cellHeight + gap / 2, cellWidth - gap, cellHeight - gap)
    }
  }
}

function drawSurface(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  region: TactileRegionFrame,
  values: number[],
) {
  context.fillStyle = '#081014'
  context.fillRect(0, 0, width, height)
  const left = width * 0.08
  const top = height * 0.16
  const planeWidth = width * 0.68
  const planeHeight = height * 0.58
  const depthX = width * 0.18
  const peakHeight = height * 0.38
  const point = (row: number, column: number) => {
    const rowUnit = row / Math.max(1, region.rows - 1)
    const columnUnit = column / Math.max(1, region.columns - 1)
    const value = values[row * region.columns + column] ?? 0
    return {
      x: left + columnUnit * planeWidth + rowUnit * depthX,
      y: top + rowUnit * planeHeight - value * peakHeight,
      value,
    }
  }
  for (let row = region.rows - 2; row >= 0; row -= 1) {
    for (let column = 0; column < region.columns - 1; column += 1) {
      const points = [point(row, column), point(row, column + 1), point(row + 1, column + 1), point(row + 1, column)]
      const peak = Math.max(...points.map((item) => item.value))
      context.beginPath()
      context.moveTo(points[0].x, points[0].y)
      for (const item of points.slice(1)) context.lineTo(item.x, item.y)
      context.closePath()
      context.fillStyle = rgba(heatColor(peak))
      context.fill()
      context.strokeStyle = peak > 0.62 ? 'rgba(255,255,255,.25)' : 'rgba(105,164,176,.18)'
      context.lineWidth = 0.7
      context.stroke()
    }
  }
}

function RegionPlot({ patch, region, baseline, threshold, scale, heatStyle, view, selected, guide, onSelect }: {
  patch: TactilePatchLayout
  region: TactileRegionFrame | undefined
  baseline: number[] | undefined
  threshold: number
  scale: number
  heatStyle: HeatStyle
  view: TactileAtlasView
  selected: TactileSelection | null
  guide: CalibrationGuide | undefined
  onSelect?: (row: number, column: number, value: number) => void
}) {
  const { t } = useI18n()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const normalized = useMemo(
    () => region ? normalizedValues(region, baseline, threshold, scale) : [],
    [baseline, region, scale, threshold],
  )
  const peak = normalized.length ? Math.max(...normalized) : 0

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !region) return
    const draw = () => {
      const rect = canvas.getBoundingClientRect()
      if (rect.width < 1 || rect.height < 1) return
      const ratio = Math.min(2, window.devicePixelRatio || 1)
      canvas.width = Math.round(rect.width * ratio)
      canvas.height = Math.round(rect.height * ratio)
      const context = canvas.getContext('2d')
      if (!context) return
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
      if (view === 'surface') drawSurface(context, rect.width, rect.height, region, normalized)
      else drawHeatmap(context, rect.width, rect.height, region, normalized, heatStyle === 'smooth')
      if (selected?.regionId === patch.id && view === 'heatmap') {
        const cellWidth = rect.width / region.columns
        const cellHeight = rect.height / region.rows
        context.strokeStyle = '#ffffff'
        context.lineWidth = 1.5
        context.strokeRect(selected.column * cellWidth + 1, selected.row * cellHeight + 1, cellWidth - 2, cellHeight - 2)
      }
    }
    draw()
    const observer = new ResizeObserver(draw)
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [heatStyle, normalized, patch.id, region, selected, view])

  const targetPositions: Record<CalibrationPoint, [number, number]> = {
    top_left: [12, 12], top_right: [88, 12], bottom_right: [88, 88], bottom_left: [12, 88], center: [50, 50],
  }
  const isGuide = guide?.regionId === patch.id
  const wrong = guide?.wrongRegionId === patch.id

  return (
    <button
      type="button"
      className={`tactile-region region-${patch.id} ${isGuide ? 'calibration-target' : ''} ${wrong ? 'wrong-target' : ''}`}
      aria-label={t(regionKey(patch.id))}
      onClick={(event) => {
        if (!region || !onSelect) return
        const rect = canvasRef.current?.getBoundingClientRect()
        if (!rect) return
        const { row, column } = taxelAtPoint(event.clientX - rect.left, event.clientY - rect.top, rect.width, rect.height, region.rows, region.columns)
        onSelect(row, column, region.values[row * region.columns + column] ?? 0)
      }}
    >
      <span className="tactile-region-label"><b>{t(regionKey(patch.id))}</b><i>{patch.rows}x{patch.columns}</i></span>
      <span className="tactile-plot"><canvas ref={canvasRef} />
        {isGuide ? <>
          {guide.completedPoints.map((point) => <i key={point} className="calibration-map-point done" style={{ left: `${targetPositions[point][0]}%`, top: `${targetPositions[point][1]}%` }} />)}
          <i key={`${guide.point}-${guide.focusToken}`} className="calibration-map-point current" style={{ left: `${targetPositions[guide.point][0]}%`, top: `${targetPositions[guide.point][1]}%`, '--capture': guide.progress } as CSSProperties} />
        </> : null}
      </span>
      <span className="tactile-region-peak"><i style={{ width: `${peak * 100}%` }} /><b>{Math.round(peak * 100)}%</b></span>
    </button>
  )
}

export function TactileAtlas2D(props: Props) {
  const { t } = useI18n()
  const profile = props.frame?.profile ?? 'piezoresistive_v1'
  const groups = useMemo(() => atlasRegionGroups(props.side, profile), [profile, props.side])
  const regions = useMemo(() => new Map(props.frame?.regions.map((region) => [region.id, region]) ?? []), [props.frame])
  const taxels = props.frame?.regions.reduce((total, region) => total + region.values.length, 0) ?? groups.flatMap((group) => group.patches).reduce((total, patch) => total + patch.rows * patch.columns, 0)
  const peakRaw = props.frame?.regions.reduce((peak, region) => Math.max(peak, ...region.values), 0) ?? 0

  return (
    <section className={`tactile-atlas side-${props.side} ${props.compact ? 'compact' : ''} view-${props.view}`} data-testid="tactile-atlas">
      <header className="tactile-atlas-header">
        <div><span className="eyebrow">RH56DFTP / {props.side.toUpperCase()}</span><h2>{t('tactile.sensorAtlas')}</h2></div>
        <div className="tactile-atlas-stats">
          <span><Activity size={13} />{props.frame ? t('common.live') : t('common.waiting')}</span>
          <span>{taxels} TAXELS</span><span>PK {peakRaw}</span>
        </div>
        {props.onViewChange ? <div className="tactile-view-switch" aria-label={t('tactile.viewMode')}>
          <button type="button" className={props.view === 'heatmap' ? 'active' : ''} onClick={() => props.onViewChange?.('heatmap')}><Grid3X3 size={14} />{t('tactile.heatmap')}</button>
          <button type="button" className={props.view === 'surface' ? 'active' : ''} onClick={() => props.onViewChange?.('surface')}><ChartNoAxesCombined size={14} />{t('tactile.surfacePlot')}</button>
        </div> : null}
      </header>
      <div className="tactile-atlas-body">
        <div className="tactile-groups">
          {groups.map((group) => <div key={group.id} className={`tactile-group group-${group.id}`}>
            {group.patches.map((patch) => <RegionPlot
              key={patch.id}
              patch={patch}
              region={regions.get(patch.id)}
              baseline={props.baseline?.[patch.id]}
              threshold={props.threshold}
              scale={props.scale}
              heatStyle={props.heatStyle}
              view={props.view}
              selected={props.selection}
              guide={props.guide}
              onSelect={props.onSelect ? (row, column, value) => props.onSelect?.({ side: props.side, regionId: patch.id, row, column, value }) : undefined}
            />)}
          </div>)}
        </div>
      </div>
      <footer className="tactile-atlas-legend"><span>{t('tactile.lowPressure')}</span><i /><span>{t('tactile.highPressure')}</span></footer>
    </section>
  )
}
