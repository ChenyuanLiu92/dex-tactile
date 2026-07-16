import { useEffect, useRef } from 'react'

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

export function CameraPanel({ landmarks }: { landmarks: number[][] | null }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

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
    if (!landmarks) return

    context.lineCap = 'round'
    context.lineJoin = 'round'
    context.strokeStyle = 'rgba(242, 170, 62, 0.88)'
    context.lineWidth = 1.6
    for (const [from, to] of CONNECTIONS) {
      const fromPoint = containPoint(landmarks[from][0], landmarks[from][1], rect.width, rect.height)
      const toPoint = containPoint(landmarks[to][0], landmarks[to][1], rect.width, rect.height)
      context.beginPath()
      context.moveTo(fromPoint[0], fromPoint[1])
      context.lineTo(toPoint[0], toPoint[1])
      context.stroke()
    }
    context.fillStyle = '#ffd089'
    landmarks.forEach(([x, y], index) => {
      const point = containPoint(x, y, rect.width, rect.height)
      context.beginPath()
      context.arc(point[0], point[1], index === 0 ? 4 : 2.5, 0, Math.PI * 2)
      context.fill()
    })
  }, [landmarks])

  return (
    <div className="camera-viewport" data-testid="camera-viewport">
      <img src="/api/video.mjpg" alt="D435 RGB stream" draggable={false} />
      <canvas ref={canvasRef} aria-hidden="true" />
      <span className="reticle reticle-nw" />
      <span className="reticle reticle-se" />
      <div className="camera-source">D435 / RGB / CAM 00</div>
    </div>
  )
}
