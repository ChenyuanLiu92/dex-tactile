import { Image, ScanLine } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useI18n } from '../../i18n/I18nProvider'
import type { DetectedHandSnapshot } from '../api'

const CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [17, 18], [18, 19], [19, 20], [0, 17],
]

export function containPoint(x: number, y: number, width: number, height: number) {
  const sourceAspect = 16 / 9
  const viewportAspect = width / height
  const drawnWidth = viewportAspect > sourceAspect ? height * sourceAspect : width
  const drawnHeight = viewportAspect > sourceAspect ? height : width / sourceAspect
  return [
    (width - drawnWidth) / 2 + x * drawnWidth,
    (height - drawnHeight) / 2 + y * drawnHeight,
  ]
}

export function CameraPanel({ landmarks, detectedHands = [] }: { landmarks: number[][] | null; detectedHands?: DetectedHandSnapshot[] }) {
  const { t } = useI18n()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [view, setView] = useState<'rgb' | 'keypoints'>('rgb')

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const scale = window.devicePixelRatio || 1
    canvas.width = Math.max(1, Math.round(rect.width * scale))
    canvas.height = Math.max(1, Math.round(rect.height * scale))
    const context = canvas.getContext('2d')
    if (!context) return
    context.scale(scale, scale)
    context.clearRect(0, 0, rect.width, rect.height)
    const hands = detectedHands.length > 0
      ? detectedHands
      : landmarks ? [{ handedness: 'Right' as const, confidence: 0, landmarks_2d: landmarks }] : []
    context.lineCap = 'round'
    context.lineJoin = 'round'
    for (const hand of hands) drawHand(context, hand, rect.width, rect.height)
  }, [detectedHands, landmarks, view])

  return (
    <div className={`camera-viewport camera-view-${view}`} data-testid="camera-viewport">
      <img className={view === 'keypoints' ? 'camera-source-hidden' : ''} src="/vision/api/video.mjpg" alt="D435 RGB stream" draggable={false} />
      <canvas ref={canvasRef} aria-hidden="true" />
      <span className="reticle reticle-nw" />
      <span className="reticle reticle-se" />
      <div className="camera-source">D435 / {view === 'rgb' ? 'RGB + TRACKING' : 'KEYPOINTS'} / CAM 00</div>
      {detectedHands.length > 0 ? <div className="camera-hand-legend">
        {detectedHands.map((hand, index) => <span className={hand.handedness.toLowerCase()} key={`${hand.handedness}-${index}`}><i />{t(hand.handedness === 'Right' ? 'common.right' : 'common.left')} <b>{Math.round(hand.confidence * 100)}%</b></span>)}
      </div> : null}
      <div className="camera-view-switch" aria-label={t('camera.viewMode')}>
        <button type="button" className={view === 'rgb' ? 'active' : ''} onClick={() => setView('rgb')}><Image size={13} />{t('camera.rgbTracking')}</button>
        <button type="button" className={view === 'keypoints' ? 'active' : ''} onClick={() => setView('keypoints')}><ScanLine size={13} />{t('camera.keypointsOnly')}</button>
      </div>
    </div>
  )
}

function drawHand(context: CanvasRenderingContext2D, hand: DetectedHandSnapshot, width: number, height: number) {
  const right = hand.handedness === 'Right'
  context.strokeStyle = right ? 'rgba(242,170,62,.9)' : 'rgba(74,200,215,.9)'
  context.fillStyle = right ? '#ffd089' : '#8cebf2'
  context.lineWidth = 1.7
  for (const [from, to] of CONNECTIONS) {
    const fromPoint = containPoint(hand.landmarks_2d[from][0], hand.landmarks_2d[from][1], width, height)
    const toPoint = containPoint(hand.landmarks_2d[to][0], hand.landmarks_2d[to][1], width, height)
    context.beginPath()
    context.moveTo(fromPoint[0], fromPoint[1])
    context.lineTo(toPoint[0], toPoint[1])
    context.stroke()
  }
  hand.landmarks_2d.forEach(([x, y], index) => {
    const point = containPoint(x, y, width, height)
    context.beginPath()
    context.arc(point[0], point[1], index === 0 ? 4 : 2.5, 0, Math.PI * 2)
    context.fill()
  })
}
