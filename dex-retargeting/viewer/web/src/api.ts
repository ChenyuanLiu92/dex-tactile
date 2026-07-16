import { useEffect, useState } from 'react'

export type TrackingStatus =
  | 'STARTING'
  | 'SEARCHING'
  | 'WRONG_HAND'
  | 'TRACKING'
  | 'LOST'
  | 'CAMERA_ERROR'

export type ControlState =
  | 'DISCONNECTED'
  | 'DISARMED'
  | 'ARMING'
  | 'ARMED'
  | 'POSITIONING'
  | 'HOLDING'
  | 'ESTOPPED'
  | 'FAULT'

export interface ControlSnapshot {
  state: ControlState
  connected: boolean
  host: string
  port: number
  actual: number[] | null
  targets: number[] | null
  commanded: number[] | null
  speeds: number[] | null
  last_write_at: number | null
  error: string | null
  preset: 'HOME' | 'OPEN' | null
  tracking_hold: boolean
  tracking_loss_ms: number | null
  modbus_output: boolean
  software_hold_only: boolean
}

export interface ContactSnapshot {
  state: 'NONE' | 'LOCKED'
  finger: 'index' | 'middle' | 'ring' | 'pinky' | null
  human_distance_mm: number | null
  projected_distance_mm: number
}

export interface TrackingSnapshot {
  type: 'tracking'
  status: TrackingStatus
  sequence: number
  captured_at: number
  published_at: number
  capture_fps: number
  tracking_fps: number
  latency_ms: number
  handedness: string | null
  confidence: number | null
  landmarks_2d: number[][] | null
  landmarks_3d: number[][] | null
  joints: Record<string, number> | null
  actuators: number[] | null
  contact: ContactSnapshot | null
  error: string | null
  dry_run: boolean
  modbus_output: boolean
  control: ControlSnapshot
}

export const EMPTY_CONTROL: ControlSnapshot = {
  state: 'DISCONNECTED',
  connected: false,
  host: '192.0.2.10',
  port: 6000,
  actual: null,
  targets: null,
  commanded: null,
  speeds: null,
  last_write_at: null,
  error: null,
  preset: null,
  tracking_hold: false,
  tracking_loss_ms: null,
  modbus_output: false,
  software_hold_only: true,
}

export const EMPTY_SNAPSHOT: TrackingSnapshot = {
  type: 'tracking',
  status: 'STARTING',
  sequence: 0,
  captured_at: 0,
  published_at: 0,
  capture_fps: 0,
  tracking_fps: 0,
  latency_ms: 0,
  handedness: null,
  confidence: null,
  landmarks_2d: null,
  landmarks_3d: null,
  joints: null,
  actuators: null,
  contact: null,
  error: null,
  dry_run: true,
  modbus_output: false,
  control: EMPTY_CONTROL,
}

export type ControlAction = 'arm' | 'disarm' | 'estop' | 'reset' | 'reconnect'

export async function requestControl(action: ControlAction): Promise<ControlSnapshot> {
  const response = await fetch(`/api/control/${action}`, {
    method: 'POST',
    headers: { 'X-RH56-Control': 'operator-confirmed' },
  })
  const payload = await response.json()
  if (!response.ok) throw new Error(payload.detail || `Control request failed (${response.status})`)
  return payload as ControlSnapshot
}

function websocketUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/ws`
}

export function useTrackingSnapshot(enabled = true, initial = EMPTY_SNAPSHOT) {
  const [snapshot, setSnapshot] = useState(initial)

  useEffect(() => {
    if (!enabled) return
    let socket: WebSocket | null = null
    let retry: number | undefined
    let active = true

    const connect = () => {
      socket = new WebSocket(websocketUrl())
      socket.onmessage = (event) => {
        try {
          setSnapshot(JSON.parse(event.data) as TrackingSnapshot)
        } catch {
          // Ignore malformed telemetry and retain the last coherent snapshot.
        }
      }
      socket.onclose = () => {
        if (active) retry = window.setTimeout(connect, 1000)
      }
    }
    connect()
    return () => {
      active = false
      if (retry !== undefined) window.clearTimeout(retry)
      socket?.close()
    }
  }, [enabled])

  return snapshot
}
